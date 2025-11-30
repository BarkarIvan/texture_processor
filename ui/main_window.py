from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QToolBar, QFileDialog, QDoubleSpinBox, QCheckBox, QComboBox, QSizePolicy
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QRadioButton, QSpinBox, QDialogButtonBox, QFormLayout, QDoubleSpinBox as QDoubleSpinBoxWidget, QProgressDialog, QApplication, QVBoxLayout as QVBoxLayoutWidget
from .browser_widget import BrowserWidget
from .editor_widget import EditorWidget
from .canvas_widget import CanvasWidget, AtlasItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Texture Atlas Editor")
        self.resize(1280, 720)

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # File/Project group
        file_group = QActionGroup(self)
        open_folder_action = QAction("Open", self)
        open_folder_action.triggered.connect(self.open_folder)
        self.toolbar.addAction(open_folder_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_project)
        self.toolbar.addAction(save_action)

        load_action = QAction("Load", self)
        load_action.triggered.connect(self.load_project)
        self.toolbar.addAction(load_action)

        self.toolbar.addSeparator()

        # Atlas group
        self.density_input = QDoubleSpinBox()
        self.density_input.setRange(1.0, 4096.0)
        self.density_input.setValue(512.0)
        self.density_input.setKeyboardTracking(False) # Apply on Enter/finish editing
        self.density_input.setPrefix("Density ")
        self.density_input.setSuffix(" px/m")
        self.density_input.setFixedWidth(160)
        self.density_input.setStyleSheet("font-size: 11px;")
        self.density_input.valueChanged.connect(self.on_density_changed)
        self.toolbar.addWidget(self.density_input)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["1024", "2048", "3072", "4096"])
        self.size_combo.setCurrentText("2048")
        self.size_combo.currentTextChanged.connect(self.on_size_changed)
        self.size_combo.setFixedWidth(90)
        self.size_combo.setStyleSheet("font-size: 11px;")
        self.toolbar.addWidget(self.size_combo)

        self.grid_chk = QCheckBox("Grid")
        self.grid_chk.stateChanged.connect(self.on_grid_toggled)
        self.toolbar.addWidget(self.grid_chk)

        self.toolbar.addSeparator()

        # Resample/Export
        resample_action = QAction("Resample", self)
        resample_action.triggered.connect(self.open_resample_settings)
        self.toolbar.addAction(resample_action)

        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(self.duplicate_selected_items)
        self.toolbar.addAction(duplicate_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_selected_items)
        self.toolbar.addAction(delete_action)

        export_action = QAction("Export PNG", self)
        export_action.triggered.connect(self.export_atlas)
        self.toolbar.addAction(export_action)
        self.toolbar.addSeparator()
        # Mip Flood toggle
        self.mip_flood_chk = QCheckBox("Mip Flood")
        self.mip_flood_chk.setToolTip("Replace alpha outside mask with downscaled mips on export")
        self.mip_flood_chk.stateChanged.connect(self.on_mip_flood_toggled)
        self.toolbar.addWidget(self.mip_flood_chk)
        self.mip_levels_spin = QSpinBox()
        self.mip_levels_spin = QSpinBox()
        self.mip_levels_spin.setRange(1, 16)
        self.mip_levels_spin.setValue(6)
        self.mip_levels_spin.setPrefix("Levels ")
        self.mip_levels_spin.setStyleSheet("font-size: 11px;")
        self.mip_levels_spin.valueChanged.connect(self.on_mip_levels_changed)
        self.toolbar.addWidget(self.mip_levels_spin)
        self.mip_levels_auto = QCheckBox("Auto")
        self.mip_levels_auto.setToolTip("Auto levels until 1x1")
        self.mip_levels_auto.stateChanged.connect(self.on_mip_auto_toggled)
        self.toolbar.addWidget(self.mip_levels_auto)
        self.toolbar.addSeparator()
        # Fit/Center actions will be wired after canvas is created
        self.fit_action = QAction("Fit", self)
        self.center_action = QAction("Center", self)

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Widgets
        self.browser = BrowserWidget()
        self.editor = EditorWidget()
        self.canvas = CanvasWidget()
        # Wire Fit/Center actions now
        self.fit_action.triggered.connect(self.canvas.fit_to_atlas)
        self.center_action.triggered.connect(self.canvas.center_on_atlas)
        self.toolbar.addAction(self.fit_action)
        self.toolbar.addAction(self.center_action)
        # Size policies
        self.browser.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        splitter.addWidget(self.browser)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.canvas)

        # Set initial sizes (approx 20%, 40%, 40%)
        splitter.setSizes([220, 520, 640])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        main_layout.addWidget(splitter)

        # Connections
        self.browser.image_selected.connect(self.on_image_selected)
        self.editor.mask_applied.connect(self.on_mask_applied)
        self.canvas.item_edit_requested.connect(self.on_item_edit_requested)
        
        # Data
        self.project_data = {
            'textures': {},
            'items': [],
            'resample_mode': 'lanczos',
            'kaiser_beta': 3.0,
            'kaiser_radius': 2,
            'atlas_density': 512.0,
            'atlas_size': 2048,
            'mip_flood': False,
            'mip_flood_levels': 6,
            'mip_flood_auto': True
        }
        self.apply_dark_theme()
        self.statusBar().showMessage("Ready")
        self.canvas.hover_changed.connect(self.update_status)
        self.mip_flood_chk.setChecked(False)

    def apply_dark_theme(self):
        # Simple dark palette
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background: #1e1f24;
            color: #e8e8ea;
            font-family: 'Segoe UI', 'Inter', sans-serif;
            font-size: 11px;
        }
        QToolBar {
            background: #2a2c32;
            spacing: 6px;
            padding: 4px;
            border: 0px;
        }
        QToolBar QToolButton, QToolBar QLabel {
            color: #f0f0f2;
        }
        QToolBar QToolButton:hover {
            background: #3a3c44;
        }
        QToolBar QToolButton:pressed {
            background: #444650;
        }
        QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
            background: #2f3138;
            border: 1px solid #3f414a;
            padding: 2px 6px;
            color: #f0f0f2;
            border-radius: 4px;
        }
        QCheckBox { color: #f0f0f2; }
        QListWidget, QGraphicsView {
            background: #22242a;
            border: 1px solid #31343c;
        }
        QPushButton {
            background: #3a7ca5;
            border: 1px solid #3a7ca5;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
        }
        QPushButton:hover { background: #4492c1; }
        QPushButton:pressed { background: #377192; }
        QMenu {
            background: #2a2c32;
            color: #f0f0f2;
            border: 1px solid #3f414a;
        }
        QMenu::item:selected { background: #3a3c44; }
        QStatusBar {
            background: #2a2c32;
            color: #f0f0f2;
        }
        """)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.browser.load_images(folder)

    def on_density_changed(self, value):
        self.project_data['atlas_density'] = value
        self.canvas.set_atlas_density(value, show_progress=True)
        
    def on_size_changed(self, text):
        size = int(text)
        self.canvas.set_canvas_size(size)
        self.project_data['atlas_size'] = size

    def on_grid_toggled(self, state):
        checked = Qt.CheckState(state) == Qt.CheckState.Checked
        self.canvas.set_grid_visible(checked)
        self.project_data['show_grid'] = checked
        self.grid_chk.setChecked(checked)

    def on_mip_flood_toggled(self, state):
        enabled = Qt.CheckState(state) == Qt.CheckState.Checked
        self.canvas.enable_mip_flood = enabled
        self.canvas.mip_flood_levels = 0 if self.mip_levels_auto.isChecked() else self.mip_levels_spin.value()
        self.project_data['mip_flood'] = enabled

    def on_mip_levels_changed(self, value):
        if not self.mip_levels_auto.isChecked():
            self.canvas.mip_flood_levels = value
        self.project_data['mip_flood_levels'] = value

    def on_mip_auto_toggled(self, state):
        auto = Qt.CheckState(state) == Qt.CheckState.Checked
        self.mip_levels_spin.setEnabled(not auto)
        self.canvas.mip_flood_levels = 0 if auto else self.mip_levels_spin.value()
        self.project_data['mip_flood_auto'] = auto

    def on_image_selected(self, filepath):
        print(f"Selected: {filepath}")
        data = self.project_data['textures'].setdefault(filepath, {'px_per_meter': None, 'masks': []})
        px_per_meter = data.get('px_per_meter')
        # For new mask creation, start blank but keep scale info if available
        self.editor.load_image(filepath, None, None, px_per_meter=px_per_meter) # Clears editing_item
        
    def on_item_edit_requested(self, item):
        # Load item into editor
        data = self.project_data['textures'].setdefault(item.filepath, {'px_per_meter': None, 'masks': []})
        px_per_meter = data.get('px_per_meter')
        mask_entry = None
        for m in data.get('masks', []):
            if m.get('id') == getattr(item, 'mask_id', None):
                mask_entry = m
                break
        points = mask_entry.get('points') if mask_entry else item.points
        real_width = mask_entry.get('real_width') if mask_entry else item.real_width
        original_width = mask_entry.get('original_width') if mask_entry else item.original_width
        self.editor.load_image(item.filepath, points, real_width, item, px_per_meter, getattr(item, 'mask_id', None))
        
    def on_mask_applied(self, filepath, points, real_width, original_width, item_ref, mask_id):
        # Ensure texture entry
        tex_entry = self.project_data['textures'].setdefault(filepath, {
            'px_per_meter': self.editor.px_per_meter,
            'masks': []
        })
        if self.editor.px_per_meter:
            tex_entry['px_per_meter'] = self.editor.px_per_meter

        if mask_id is None:
            if item_ref:
                mask_id = getattr(item_ref, 'mask_id', None)
            else:
                mask_id = self.editor.current_mask_id

        # Update existing mask or create new
        existing = None
        for m in tex_entry['masks']:
            if m.get('id') == mask_id:
                existing = m
                break

        if existing:
            existing['points'] = points
            existing['real_width'] = real_width
            existing['original_width'] = original_width
        else:
            # Assign new id
            next_id = max([m.get('id', 0) for m in tex_entry['masks']] + [0]) + 1
            mask_id = next_id
            tex_entry['masks'].append({
                'id': mask_id,
                'points': points,
                'real_width': real_width,
                'original_width': original_width
            })

        if item_ref:
            item_ref.mask_id = mask_id
            self.canvas.update_item(item_ref, points, real_width, original_width, mask_id=mask_id, show_progress=True)
        else:
            # Add new item
            self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=mask_id, show_progress=True)

    def duplicate_selected_items(self):
        selected = [it for it in self.canvas.scene.selectedItems() if isinstance(it, AtlasItem)]
        if not selected:
            return
        offset = QPointF(20, 20)
        for it in selected:
            tex_entry = self.project_data['textures'].setdefault(it.filepath, {'px_per_meter': None, 'masks': []})
            if tex_entry.get('px_per_meter') is None and self.editor.px_per_meter:
                tex_entry['px_per_meter'] = self.editor.px_per_meter
            next_id = max([m.get('id', 0) for m in tex_entry['masks']] + [0]) + 1
            tex_entry['masks'].append({
                'id': next_id,
                'points': it.points,
                'real_width': it.real_width,
                'original_width': it.original_width
            })
            new_item = self.canvas.add_fragment(it.filepath, it.points, it.real_width, it.original_width, mask_id=next_id, show_progress=True)
            if new_item:
                new_item.setPos(it.pos() + offset)
                if self.canvas.scene.snap_items_to_pixel:
                    pos = new_item.pos()
                    new_item.setPos(round(pos.x()), round(pos.y()))

    def delete_selected_items(self):
        selected = [it for it in self.canvas.scene.selectedItems() if isinstance(it, AtlasItem)]
        if not selected:
            return
        for it in selected:
            tex_entry = self.project_data['textures'].get(it.filepath)
            if tex_entry:
                masks = tex_entry.get('masks', [])
                tex_entry['masks'] = [m for m in masks if m.get('id') != it.mask_id]
            self.canvas.scene.removeItem(it)

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filepath:
            import json
            self.project_data['base_path'] = self.browser.current_folder
            self.project_data['atlas_density'] = self.density_input.value()
            self.project_data['show_grid'] = self.grid_chk.isChecked()
            self.project_data['mip_flood'] = self.mip_flood_chk.isChecked()
            self.project_data['mip_flood_levels'] = self.mip_levels_spin.value()
            # Capture item positions
            items_data = []
            for it in self.canvas.scene.items():
                if isinstance(it, AtlasItem):
                    items_data.append({
                        'filepath': it.filepath,
                        'mask_id': getattr(it, 'mask_id', None),
                        'x': it.pos().x(),
                        'y': it.pos().y()
                    })
            self.project_data['items'] = items_data
            with open(filepath, 'w') as f:
                json.dump(self.project_data, f, indent=4)

    def load_project(self, filepath=None):
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON Files (*.json)")
        
        if filepath:
            import json
            import os
            with open(filepath, 'r') as f:
                self.project_data = json.load(f)

            # Normalize legacy texture data to new masks list
            textures = self.project_data.get('textures', {})
            for tex_path, data in list(textures.items()):
                if 'masks' not in data:
                    textures[tex_path] = {
                        'px_per_meter': data.get('px_per_meter'),
                        'masks': [{
                            'id': 1,
                            'points': data.get('points'),
                            'real_width': data.get('real_width'),
                            'original_width': data.get('original_width')
                        }]
                    }
            
            base_path = self.project_data.get('base_path')
            if base_path and os.path.exists(base_path):
                self.browser.load_images(base_path)
            
            # Restore settings
            self.density_input.setValue(self.project_data.get('atlas_density', 512.0))
            
            atlas_size = self.project_data.get('atlas_size', 2048)
            self.size_combo.setCurrentText(str(atlas_size))
            self.canvas.set_canvas_size(atlas_size)
            self.grid_chk.setChecked(self.project_data.get('show_grid', False))
            self.mip_flood_chk.setChecked(self.project_data.get('mip_flood', False))
            self.mip_levels_spin.setValue(int(self.project_data.get('mip_flood_levels', 6)))
            self.canvas.mip_flood_levels = self.mip_levels_spin.value() if not self.project_data.get('mip_flood_auto', True) else 0
            self.mip_levels_auto.setChecked(self.project_data.get('mip_flood_auto', True))

            # Resample settings
            mode = self.project_data.get('resample_mode', 'lanczos')
            beta = self.project_data.get('kaiser_beta', 3.0)
            radius = self.project_data.get('kaiser_radius', 2)
            self.canvas.set_resample_settings(mode, beta, radius)
            # Ensure density applied (valueChanged will fire, but be explicit)
            self.canvas.set_atlas_density(self.density_input.value(), show_progress=False)
            self.canvas.set_grid_visible(self.project_data.get('show_grid', False))
            # Restore canvas
            self.canvas.scene.clear()
            tex_items = list(self.project_data.get('textures', {}).items())
            use_progress = len(tex_items) > 0
            dlg = None
            if use_progress:
                dlg = QProgressDialog("Resampling textures...", None, 0, len(tex_items), self)
                dlg.setWindowModality(Qt.ApplicationModal)
                dlg.setMinimumDuration(0)
                dlg.show()
            item_map = {}
            for idx, (filepath, data) in enumerate(tex_items, start=1):
                masks = data.get('masks')
                if masks:
                    for m in masks:
                        points = m.get('points')
                        real_width = m.get('real_width')
                        original_width = m.get('original_width')
                        mask_id = m.get('id')
                        if points:
                            item = self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=mask_id, show_progress=True)
                            if item:
                                item_map[(filepath, mask_id)] = item
                else:
                    # Legacy single mask structure
                    points = data.get('points')
                    real_width = data.get('real_width')
                    original_width = data.get('original_width')
                    if points:
                        item = self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=1, show_progress=True)
                        if item:
                            item_map[(filepath, 1)] = item
                if dlg:
                    dlg.setValue(idx)
                    QApplication.processEvents()
                    if dlg.wasCanceled():
                        break
            if dlg:
                dlg.close()

            # Restore positions
            for entry in self.project_data.get('items', []):
                key = (entry.get('filepath'), entry.get('mask_id'))
                item = item_map.get(key)
                if item:
                    item.setPos(entry.get('x', 0), entry.get('y', 0))
            if self.canvas.scene.snap_items_to_pixel:
                self.canvas.snap_items_to_pixel()

    def export_atlas(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Atlas", "", "PNG Files (*.png)")
        if filepath:
            self.canvas.export_atlas(filepath)

    def open_resample_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Resample Settings")
        layout = QVBoxLayout(dialog)

        lanczos_radio = QRadioButton("Lanczos (default)")
        kaiser_radio = QRadioButton("Kaiser (windowed sinc)")
        nearest_radio = QRadioButton("Pixel (Nearest)")
        mode_current = self.project_data.get('resample_mode', 'lanczos')
        if mode_current == 'kaiser':
            kaiser_radio.setChecked(True)
        elif mode_current == 'nearest':
            nearest_radio.setChecked(True)
        else:
            lanczos_radio.setChecked(True)

        layout.addWidget(lanczos_radio)
        layout.addWidget(kaiser_radio)
        layout.addWidget(nearest_radio)

        form = QFormLayout()
        beta_spin = QDoubleSpinBoxWidget()
        beta_spin.setRange(0.1, 20.0)
        beta_spin.setValue(self.project_data.get('kaiser_beta', 3.0))
        beta_spin.setSingleStep(0.1)
        form.addRow("Kaiser beta", beta_spin)

        radius_spin = QSpinBox()
        radius_spin.setRange(1, 8)
        radius_spin.setValue(int(self.project_data.get('kaiser_radius', 2)))
        form.addRow("Kaiser radius", radius_spin)
        layout.addLayout(form)

        def update_enabled():
            enabled = kaiser_radio.isChecked()
            beta_spin.setEnabled(enabled)
            radius_spin.setEnabled(enabled)
        kaiser_radio.toggled.connect(update_enabled)
        update_enabled()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def accept():
            if kaiser_radio.isChecked():
                mode = 'kaiser'
            elif nearest_radio.isChecked():
                mode = 'nearest'
            else:
                mode = 'lanczos'
            beta = beta_spin.value()
            radius = radius_spin.value()
            self.project_data['resample_mode'] = mode
            self.project_data['kaiser_beta'] = beta
            self.project_data['kaiser_radius'] = radius
            self.canvas.set_resample_settings(mode, beta, radius)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def update_status(self, x, y, zoom):
        self.statusBar().showMessage(f"Pos: ({x:.1f}, {y:.1f}) | Zoom: {zoom:.2f} | Density: {self.density_input.value():.0f} px/m")
