# Texture Atlas Editor — шпаргалка для агента

## Назначение
PySide6-приложение для вырезки масок из исходных текстур, их раскладки на атласе и экспорта в PNG/OBJ. Тёмная тема, предпросмотр, сетка плотности и управляемый ресемплинг.

## Запуск
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Архитектура
- main.py: создаёт QApplication, задаёт дефолтный шрифт, показывает MainWindow.
- core/: простые dataclass’ы `Mask/Texture/AtlasItem/Project` для сериализации (UI сейчас хранит состояние в dict `project_data`).
- ui/view_utils.py: `ZoomPanView` (колёсико = zoom, middle drag = pan, сигналы clicked/mouseMoved/leftReleased/hoverMoved).
- ui/browser_widget.py: список изображений из выбранной папки (png/jpg/jpeg/tga/bmp) с превью 64×64; сигнал `image_selected(filepath)`.
- ui/editor_widget.py: канва для разметки маски.
  - Инструменты: Polygon (по умолчанию), Rect (Shift делает квадрат), Set Scale (2 клика — задаёт px_per_meter).
  - Точки — `HandleItem` с контекстным Delete, Shift при добавлении/движении выравнивает по соседям/осям; Ctrl+drag на многоугольнике двигает маску целиком; контекст на полигонах — Add Point Here.
  - Undo/Redo стеками точек/ширины; линия масштаба не восстанавливается.
  - `mask_applied` сигнал: filepath, points, real_width, original_width (ширина bbox), item_ref, mask_id.
  - Показывает все маски текстуры сразу: активная редактируется, остальные — “призраки” с ослабленной альфой; у каждой маски цвет (хранится в данных). Выпадающий список для выбора маски; пункт “New mask” создаёт новую.
  - Направляющие (H/V) с кнопками `+H guide/+V guide/Clear guides`; снап точек к ближайшей направляющей при перетаскивании (порог ~8px). Shift‑снап по соседям работает вместе с гидами.
- ui/canvas_widget.py: поле атласа.
    - `CanvasScene` рисует рамку размера атласа, опциональную сетку по плотности; `exporting` флаг скрывает оверлеи.
    - `AtlasItem` - вырезка, перемещаемая/выделяемая; в pixel режиме снапит позицию к целым. Контекстное меню: Lock/Unlock movement (включает/отключает перемещение элемента; пока не сохраняется в проект).
    - Ресемплинг: Lanczos (по умолчанию), Kaiser (собственный фильтр на numpy, beta/radius), Nearest (отключает сглаживание, включает снап к пикселю). Кэш `_lanczos_cache` (32 записи), сбрасывается при смене режима.
  - `add_fragment`/`update_item` строят QPixmap по маске: bbox полигона → ресемплинг с масштабом `(atlas_density * real_width) / original_width` → клип по полигона.
  - `export_atlas` сохраняет PNG без сетки/фона/selection, опционально `apply_mip_flood` (заливка цветных каналов вне маски из mips, альфа неизменна; уровни 1–16 или auto до 1×1).
  - `generate_obj` собирает OBJ: один объект на маску, вершины в метрах (px/atlas_density) с +Y вверх, UV нормализованы к атласу с origin снизу-слева, сортировка по mask_id/пути/позиции для детерминизма.
- ui/main_window.py: соединяет все виджеты, хранит `project_data`, тулбар с плотностью/размером/сеткой, ресемплингом, Duplicate/Delete, Export PNG/OBJ, Path Aliases, Mip Flood, Fit/Center.
  - Выбор изображения -> editor (с сохранением px_per_meter).
  - Apply/Update маски: создаёт/обновляет mask_id на текстуре, кладёт фрагмент на атлас.
  - Duplicate создаёт новый mask_id и элемент со смещением; Delete убирает элемент и маску.
  - Сохранение проекта в JSON: base_path, atlas_density/size/show_grid/resample/mip_flood/settings, textures{} с masks[], items[] с позициями. Перед перезаписью делает ротацию бэкапов `*_back_1..4.json` рядом с файлом. При загрузке нормализует legacy поля, пересэмпливает элементы (прогрессбар), восстанавливает позиции.
  - Path Aliases: файл `~/.texture_processor_aliases.json`, формат `{stored_prefix: local_prefix}`; resolve_path сначала разворачивает переменные окружения, затем пытается заменить самый длинный подходящий префикс на локальный.
- ui/browser_widget.py: список изображений из выбранной папки (png/jpg/jpeg/tga/bmp) с превью 64×64; сигнал `image_selected(filepath)`.
- ui/browser_widget.py и редактор/канва используют `QGraphicsView` для интерактивной работы; статус-бар показывает координаты/zoom/плотность.

## Поток работы (UI)
1) Open папку → список превью.
2) Выбор изображения → редактор.
3) Маска Polygon/Rect (Shift выравнивает, Ctrl+drag двигает всю маску, контекстное Add/Delete Point). При необходимости выбрать существующую маску в списке или создать новую.
4) Set Scale: 2 точки + длина в метрах → обновляет px_per_meter и width_input.
5) Опционально добавить направляющие (H/V); точки маски снапятся к ближайшим.
6) Apply Mask → сохраняет в textures[filepath].masks и добавляет/обновляет элемент на атласе.
7) Настроить плотность/размер/ресемплинг, при необходимости Duplicate/Delete.
8) Экспорт: PNG (с mip flood) или OBJ (многоугольники масок в метрах с UV).
9) Save/Load проекта (JSON) при необходимости.

## Экспорт OBJ
- Тулбар → Export OBJ.
- Один объект (o mask_<id>) на маску, грань — n-gon по точкам маски.
- Вершины: метры (px / atlas_density), координатная система с +Y вверх (atlas origin вверху-слева, при экспорте разворот по Y и реверс порядка точек).
- UV: нормализованы к размеру атласа, origin снизу-слева (Blender-friendly), порядок совпадает с вершинами.

## Формат данных
- `project_data`:
  - `textures`: {filepath: {px_per_meter, masks:[{id, points, real_width, original_width, color}]}}
  - `items`: [{filepath, mask_id, x, y}]
  - `atlas_density`, `atlas_size`, `show_grid`, `resample_mode`, `kaiser_beta`, `kaiser_radius`,
    `mip_flood`, `mip_flood_levels`, `mip_flood_auto`, `base_path`
- Алиасы путей: `~/.texture_processor_aliases.json`, плюс подстановка env vars (например `$DROPBOX`).

## Заметки для доработок
- В UI используется dict-состояние, а dataclass’ы из core пока не задействованы; можно свести к одной модели.
- Pixel/Nearest включает `snap_items_to_pixel`, ставит FastTransformation на элементы.
- Undo/Redo в редакторе не сохраняет линию масштаба и историю точки привязки.
- Кэш ресемплинга зависит от пути/rect/размера/режима/beta/radius; сбрасывайте при смене фильтра/плотности.
- Mip flood: уровни 0 или auto → высчитываются до 1×1; работает только с альфа-маской готового атласа.
