from collections import OrderedDict
import math
import numpy as np
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QVBoxLayout, QGraphicsPixmapItem, QGraphicsItem, QProgressDialog, QApplication, QSizePolicy, QLabel
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QPolygonF, QColor, QBrush, QImage, QPen
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PIL import Image, ImageChops
from PIL.ImageQt import ImageQt
from .view_utils import ZoomPanView

class AtlasItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, parent=None):
        super().__init__(pixmap, parent)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setTransformationMode(Qt.SmoothTransformation) # Better scaling quality
        
        # Metadata
        self.filepath = None
        self.points = None
        self.real_width = None
        self.original_width = None
        self.mask_id = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            scene = self.scene()
            if scene and getattr(scene, "snap_items_to_pixel", False):
                pos = value
                return QPointF(round(pos.x()), round(pos.y()))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)

        # Skip overlays during export to avoid artifacts on the final image
        scene = self.scene()
        if scene and getattr(scene, "exporting", False):
            return

        # Draw border in editor view
        pen = QPen(Qt.blue, 0, Qt.DashLine) # Width 0 = Cosmetic (1px on screen)
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
        
        if self.isSelected():
            pen = QPen(Qt.red, 0, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())

class CanvasScene(QGraphicsScene):
    def __init__(self, x, y, w, h, parent=None):
        super().__init__(x, y, w, h, parent)
        self.grid_enabled = False
        self.grid_step = 512.0 # Default density
        self.exporting = False

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)

        # Hide all overlays during export
        if self.exporting:
            return
        
        scene_rect = self.sceneRect()
        
        # Draw Atlas Border (The 4k/2k limit)
        border_pen = QPen(Qt.red, 0, Qt.SolidLine) # Cosmetic red line
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(scene_rect)

        if not self.grid_enabled:
            return

        # Draw grid
        # Intersect exposed rect with scene rect to only draw grid on the canvas
        draw_rect = rect.intersected(scene_rect)
        
        left = int(draw_rect.left())
        top = int(draw_rect.top())
        right = int(draw_rect.right())
        bottom = int(draw_rect.bottom())
        
        step = self.grid_step
        if step <= 0: return

        # Subtle light grid
        pen = QPen(QColor(200, 200, 200, 120), 0) 
        painter.setPen(pen)
        
        # print(f"Drawing grid: step={step}, rect={draw_rect}") # Debug
        
        # Vertical lines
        # Align to scene_rect origin (0,0)
        start_x = int(left - (left % step))
        if start_x < scene_rect.left(): start_x = int(scene_rect.left())
        
        for x in range(start_x, right + 1, int(step)):
            if x < scene_rect.left() or x > scene_rect.right(): continue
            painter.drawLine(x, max(top, int(scene_rect.top())), x, min(bottom, int(scene_rect.bottom())))
            
        # Horizontal lines
        start_y = int(top - (top % step))
        if start_y < scene_rect.top(): start_y = int(scene_rect.top())
        
        for y in range(start_y, bottom + 1, int(step)):
            if y < scene_rect.top() or y > scene_rect.bottom(): continue
            painter.drawLine(max(left, int(scene_rect.left())), y, min(right, int(scene_rect.right())), y)

class CanvasWidget(QWidget):
    item_edit_requested = Signal(object) # AtlasItem
    hover_changed = Signal(float, float, float) # x, y, zoom

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setMinimumWidth(400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scene = CanvasScene(0, 0, 2048, 2048) 
        self.view = ZoomPanView(self.scene, self)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        layout.addWidget(self.view)
        
        # Solid dark gray background, no pattern
        self.scene.setBackgroundBrush(QBrush(Qt.darkGray))
        
        self.atlas_density = 512.0
        self.scene.grid_step = self.atlas_density
        self._lanczos_cache = OrderedDict() # (path, rect, target_size) -> QImage
        self._cache_limit = 32
        self.resample_mode = "lanczos" # "lanczos", "kaiser", "nearest"
        self.kaiser_beta = 3.0
        self.kaiser_radius = 2
        self.scene.snap_items_to_pixel = False
        self.enable_mip_flood = False
        self.mip_flood_threshold = 1
        self.mip_flood_levels = 6
        
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.view.viewport().setMouseTracking(True)
        self.view.setMouseTracking(True)
        self.view.hoverMoved.connect(self.forward_hover)

    def set_atlas_density(self, density, show_progress=False):
        self.atlas_density = density
        self.scene.grid_step = density
        self.scene.update() # Redraw grid
        if show_progress:
            self.rebuild_items_with_progress("Updating density...")
        else:
            for item in self.scene.items():
                if isinstance(item, AtlasItem):
                    self.regenerate_item_pixmap(item)

    def set_resample_settings(self, mode, beta=None, radius=None):
        if mode not in ("lanczos", "kaiser", "nearest"):
            return
        self.resample_mode = mode
        # Toggle view smoothing for pixel art
        if self.view:
            self.view.setRenderHint(QPainter.SmoothPixmapTransform, mode != "nearest")
        self.scene.snap_items_to_pixel = (mode == "nearest")
        if beta is not None:
            self.kaiser_beta = beta
        if radius is not None:
            self.kaiser_radius = radius
        # Clear cache and rebuild items to apply new filter
        self._lanczos_cache.clear()
        self.rebuild_items_with_progress("Resampling items...")
        if self.scene.snap_items_to_pixel:
            self.snap_items_to_pixel()

    def set_canvas_size(self, size):
        self.scene.setSceneRect(0, 0, size, size)
        self.scene.update() # Redraw border

    def set_grid_visible(self, visible):
        self.scene.grid_enabled = visible
        self.scene.update()

    def fit_to_atlas(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def center_on_atlas(self):
        self.view.centerOn(self.scene.sceneRect().center())

    def snap_items_to_pixel(self):
        for item in self.scene.items():
            if isinstance(item, AtlasItem):
                pos = item.pos()
                item.setPos(round(pos.x()), round(pos.y()))

    def forward_hover(self, scene_pos, zoom):
        self.hover_changed.emit(scene_pos.x(), scene_pos.y(), zoom)

    def regenerate_item_pixmap(self, item):
        if item.filepath and item.points and item.real_width and item.original_width:
            pixmap = self.create_masked_pixmap(item.filepath, item.points, item.real_width, item.original_width)
            if pixmap:
                item.setPixmap(pixmap)
                item.setScale(1.0)
                # Respect pixel mode transform
                if self.resample_mode == "nearest":
                    item.setTransformationMode(Qt.FastTransformation)
                else:
                    item.setTransformationMode(Qt.SmoothTransformation)

    def _run_single_with_progress(self, title, func):
        dlg = QProgressDialog(title, None, 0, 0, self)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setStyleSheet("QProgressDialog { background: #2a2c32; color: #f0f0f2; } QProgressBar { background: #22242a; border: 1px solid #3f414a; }")
        dlg.show()
        QApplication.processEvents()
        func()
        dlg.close()

    def rebuild_items_with_progress(self, title):
        items = [i for i in self.scene.items() if isinstance(i, AtlasItem)]
        total = len(items)
        if total == 0:
            return
        dlg = QProgressDialog(title, None, 0, total, self)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setStyleSheet("QProgressDialog { background: #2a2c32; color: #f0f0f2; } QProgressBar { background: #22242a; border: 1px solid #3f414a; }")
        dlg.show()
        for idx, item in enumerate(items, start=1):
            QApplication.processEvents()
            self.regenerate_item_pixmap(item)
            dlg.setValue(idx)
            if dlg.wasCanceled():
                break
        dlg.close()

    def on_selection_changed(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], AtlasItem):
            self.item_edit_requested.emit(selected[0])

    def _get_resampled_crop(self, image_path, rect, target_size):
        key = (
            image_path,
            rect.left(),
            rect.top(),
            rect.width(),
            rect.height(),
            target_size[0],
            target_size[1],
            self.resample_mode,
            round(self.kaiser_beta, 3),
            int(self.kaiser_radius),
        )
        if key in self._lanczos_cache:
            self._lanczos_cache.move_to_end(key)
            return self._lanczos_cache[key]
        
        try:
            img = Image.open(image_path).convert("RGBA")
            box = (rect.left(), rect.top(), rect.left() + rect.width(), rect.top() + rect.height())
            cropped = img.crop(box)
            if self.resample_mode == "kaiser":
                resized = self._kaiser_resize(cropped, target_size, self.kaiser_radius, self.kaiser_beta)
            elif self.resample_mode == "nearest":
                resized = cropped.resize(target_size, Image.NEAREST)
            else:
                resized = cropped.resize(target_size, Image.LANCZOS)
            qimg = ImageQt(resized).copy() # Detach from PIL buffer
        except Exception:
            return None

        self._lanczos_cache[key] = qimg
        if len(self._lanczos_cache) > self._cache_limit:
            self._lanczos_cache.popitem(last=False)
        return qimg

    def create_masked_pixmap(self, image_path, points, real_width, original_width):
        poly = QPolygonF([QPointF(x, y) for x, y in points])
        bounding_rect = poly.boundingRect().toAlignedRect()
        
        if bounding_rect.width() <= 0 or bounding_rect.height() <= 0:
            return None
        
        # Compute target size on atlas using density
        scale_factor = (self.atlas_density * real_width) / original_width
        target_w = max(1, int(round(bounding_rect.width() * scale_factor)))
        target_h = max(1, int(round(bounding_rect.height() * scale_factor)))
        
        # Get resampled crop (Lanczos or Kaiser)
        src_qimage = self._get_resampled_crop(image_path, bounding_rect, (target_w, target_h))
        if src_qimage is None:
            return None

        src_pixmap = QPixmap.fromImage(src_qimage)
        target_image = QImage(target_w, target_h, QImage.Format_ARGB32)
        target_image.fill(Qt.transparent)
        
        painter = QPainter(target_image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        # Scale polygon to the target size
        scaled_points = [
            QPointF((x - bounding_rect.left()) * scale_factor, (y - bounding_rect.top()) * scale_factor)
            for x, y in points
        ]
        path.addPolygon(QPolygonF(scaled_points))
        
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src_pixmap)
        painter.end()

        return QPixmap.fromImage(target_image)

    def _kaiser_resize(self, image: Image.Image, target_size, radius: int, beta: float) -> Image.Image:
        """Resize using separable Kaiser-windowed sinc filter."""
        src = np.array(image, dtype=np.float32)
        if src.ndim == 2:
            src = src[:, :, None]
        src_h, src_w, channels = src.shape
        tgt_w, tgt_h = target_size
        if tgt_w <= 0 or tgt_h <= 0:
            return image
        if tgt_w == src_w and tgt_h == src_h:
            return image

        taps = 2 * radius + 1

        def kaiser_weight(dist):
            """dist: array, |dist| <= radius."""
            mask = np.abs(dist) <= radius
            out = np.zeros_like(dist, dtype=np.float32)
            # Kaiser window
            ratio = np.zeros_like(dist, dtype=np.float32)
            ratio[mask] = dist[mask] / radius
            window = np.zeros_like(dist, dtype=np.float32)
            window[mask] = np.i0(beta * np.sqrt(1 - ratio[mask] ** 2)) / np.i0(beta)
            out[mask] = np.sinc(dist[mask]) * window[mask]
            return out

        # Horizontal weights/indices
        src_x = (np.arange(tgt_w) + 0.5) * src_w / tgt_w - 0.5
        offsets = np.arange(-radius, radius + 1)
        idx_x = np.floor(src_x[:, None] + offsets).astype(int)
        idx_x = np.clip(idx_x, 0, src_w - 1)
        dist_x = src_x[:, None] - idx_x
        w_x = kaiser_weight(dist_x)
        w_x_sum = w_x.sum(axis=1, keepdims=True)
        w_x = np.divide(w_x, w_x_sum, out=np.zeros_like(w_x), where=w_x_sum != 0)

        # Horizontal resample
        tmp = np.empty((src_h, tgt_w, channels), dtype=np.float32)
        for y in range(src_h):
            row = src[y]  # (src_w, ch)
            gathered = row[idx_x]  # (tgt_w, taps, ch)
            tmp[y] = np.sum(gathered * w_x[:, :, None], axis=1)

        # Vertical weights/indices
        src_y = (np.arange(tgt_h) + 0.5) * src_h / tgt_h - 0.5
        idx_y = np.floor(src_y[:, None] + offsets).astype(int)
        idx_y = np.clip(idx_y, 0, src_h - 1)
        dist_y = src_y[:, None] - idx_y
        w_y = kaiser_weight(dist_y)
        w_y_sum = w_y.sum(axis=1, keepdims=True)
        w_y = np.divide(w_y, w_y_sum, out=np.zeros_like(w_y), where=w_y_sum != 0)

        # Vertical resample
        out = np.empty((tgt_h, tgt_w, channels), dtype=np.float32)
        for x in range(tgt_w):
            col = tmp[:, x, :]  # (src_h, ch)
            gathered = col[idx_y]  # (tgt_h, taps, ch)
            out[:, x, :] = np.sum(gathered * w_y[:, :, None], axis=1)

        out = np.clip(out, 0, 255).astype(np.uint8)
        if channels == 1:
            out = out[:, :, 0]
        return Image.fromarray(out, mode=image.mode)

    def add_fragment(self, image_path, points, real_width, original_width, mask_id=None, show_progress=False):
        def build():
            return self.create_masked_pixmap(image_path, points, real_width, original_width)

        if show_progress:
            container = {}
            def work():
                container['pixmap'] = build()
            self._run_single_with_progress("Resampling fragment...", work)
            pixmap = container.get('pixmap')
        else:
            pixmap = build()

        if not pixmap:
            return

        item = AtlasItem(pixmap)
        item.setPos(0, 0) 
        if self.scene.snap_items_to_pixel:
            pos = item.pos()
            item.setPos(round(pos.x()), round(pos.y()))
        
        # Store metadata
        item.filepath = image_path
        item.points = points
        item.real_width = real_width
        item.original_width = original_width
        item.mask_id = mask_id
        
        # Legacy support for scale logic (using data)
        item.setData(Qt.UserRole + 1, real_width)
        item.setData(Qt.UserRole + 2, original_width)
        
        self.scene.addItem(item)
        item.setScale(1.0)
        if self.resample_mode == "nearest":
            item.setTransformationMode(Qt.FastTransformation)
        else:
            item.setTransformationMode(Qt.SmoothTransformation)
        return item

    def update_item(self, item, points, real_width, original_width, mask_id=None, show_progress=False):
        def build():
            return self.create_masked_pixmap(item.filepath, points, real_width, original_width)

        if show_progress:
            container = {}
            def work():
                container['pixmap'] = build()
            self._run_single_with_progress("Resampling fragment...", work)
            pixmap = container.get('pixmap')
        else:
            pixmap = build()

        if not pixmap:
            return
        
        item.setPixmap(pixmap)
        item.points = points
        item.real_width = real_width
        item.original_width = original_width
        if mask_id is not None:
            item.mask_id = mask_id
        if self.scene.snap_items_to_pixel:
            pos = item.pos()
            item.setPos(round(pos.x()), round(pos.y()))
        if self.resample_mode == "nearest":
            item.setTransformationMode(Qt.FastTransformation)
        else:
            item.setTransformationMode(Qt.SmoothTransformation)
        
        item.setData(Qt.UserRole + 1, real_width)
        item.setData(Qt.UserRole + 2, original_width)
        
        item.setScale(1.0)

    def export_atlas(self, filename):
        rect = self.scene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        # Hide background, selection, and grid
        old_bg = self.scene.backgroundBrush()
        self.scene.setBackgroundBrush(Qt.NoBrush)
        old_grid = self.scene.grid_enabled
        self.scene.grid_enabled = False
        # Hide overlays while exporting
        old_exporting = self.scene.exporting
        self.scene.exporting = True
        
        selected_items = self.scene.selectedItems()
        for item in selected_items:
            item.setSelected(False)
            
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()

        # Optional mip flood (color only, alpha untouched)
        if self.enable_mip_flood:
            image = self.apply_mip_flood(image, self.mip_flood_threshold, self.mip_flood_levels)
        
        # Restore
        self.scene.setBackgroundBrush(old_bg)
        self.scene.grid_enabled = old_grid
        self.scene.exporting = old_exporting
        for item in selected_items:
            item.setSelected(True)
            
        image.save(filename)

    def apply_mip_flood(self, qimage, alpha_threshold=1, levels=4):
        """Apply mip flooding based on alpha mask (color channels only, alpha untouched)."""
        rgba_img = qimage.convertToFormat(QImage.Format_RGBA8888)
        buffer = rgba_img.bits().tobytes()
        w, h = rgba_img.width(), rgba_img.height()
        if w == 0 or h == 0:
            return qimage

        # Convert to numpy
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((h, w, 4))
        alpha = arr[..., 3]
        mask = (alpha > alpha_threshold).astype(np.uint8)
        color = arr[..., :3].astype(np.float32) / 255.0

        def pad_even(img_arr, mask_arr):
            h, w = img_arr.shape[:2]
            pad_h = h % 2
            pad_w = w % 2
            if pad_h or pad_w:
                img_arr = np.pad(img_arr, ((0, pad_h), (0, pad_w), (0, 0)), mode='edge')
                mask_arr = np.pad(mask_arr, ((0, pad_h), (0, pad_w)), mode='edge')
            return img_arr, mask_arr

        # Auto levels to reach 1x1
        if levels is None or levels <= 0:
            levels = int(math.ceil(math.log2(max(w, h)))) if max(w, h) > 0 else 1

        colors = [color]
        masks = [mask]
        for _ in range(levels):
            img_arr, mask_arr = pad_even(colors[-1], masks[-1])
            h2, w2 = img_arr.shape[0] // 2, img_arr.shape[1] // 2
            # Downscale mask by OR
            mask_blocks = mask_arr.reshape(h2, 2, w2, 2)
            mask_ds = mask_blocks.max(axis=(1, 3))
            # Downscale color weighted by coverage
            color_blocks = img_arr.reshape(h2, 2, w2, 2, 3)
            coverage = mask_blocks.sum(axis=(1, 3)).reshape(h2, w2, 1)
            summed = (color_blocks * mask_blocks[..., None]).sum(axis=(1, 3))
            color_ds = np.where(coverage > 0, summed / coverage, 0.0)
            colors.append(color_ds)
            masks.append(mask_ds)
            if h2 == 1 and w2 == 1:
                break

        # Flood from smallest to largest
        for i in range(len(colors) - 2, -1, -1):
            small_c = colors[i + 1]
            big_c = colors[i]
            big_mask = masks[i]
            # Upscale small to big via nearest
            up = small_c.repeat(2, axis=0).repeat(2, axis=1)
            up = up[: big_c.shape[0], : big_c.shape[1], :]
            # Fill only where mask==0
            fill_mask = (big_mask == 0)[..., None]
            colors[i] = np.where(fill_mask, up, big_c)

        final_color = (colors[0] * 255.0).clip(0, 255).astype(np.uint8)
        out_arr = np.concatenate([final_color, alpha[..., None]], axis=2)
        out = QImage(out_arr.data, out_arr.shape[1], out_arr.shape[0], QImage.Format_RGBA8888).copy()
        return out
