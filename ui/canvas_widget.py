from collections import OrderedDict
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QVBoxLayout, QGraphicsPixmapItem, QGraphicsItem
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QPolygonF, QColor, QBrush, QImage, QPen
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PIL import Image
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

        # Use Cyan for better visibility
        pen = QPen(QColor(0, 255, 255, 200), 0) 
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

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
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
        
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def set_atlas_density(self, density):
        self.atlas_density = density
        self.scene.grid_step = density
        self.scene.update() # Redraw grid
        for item in self.scene.items():
            if isinstance(item, AtlasItem):
                self.regenerate_item_pixmap(item)

    def set_canvas_size(self, size):
        self.scene.setSceneRect(0, 0, size, size)
        self.scene.update() # Redraw border

    def set_grid_visible(self, visible):
        self.scene.grid_enabled = visible
        self.scene.update()

    def regenerate_item_pixmap(self, item):
        if item.filepath and item.points and item.real_width and item.original_width:
            pixmap = self.create_masked_pixmap(item.filepath, item.points, item.real_width, item.original_width)
            if pixmap:
                item.setPixmap(pixmap)
                item.setScale(1.0)

    def on_selection_changed(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], AtlasItem):
            self.item_edit_requested.emit(selected[0])

    def _get_lanczos_crop(self, image_path, rect, target_size):
        key = (image_path, rect.left(), rect.top(), rect.width(), rect.height(), target_size[0], target_size[1])
        if key in self._lanczos_cache:
            self._lanczos_cache.move_to_end(key)
            return self._lanczos_cache[key]
        
        try:
            img = Image.open(image_path).convert("RGBA")
            box = (rect.left(), rect.top(), rect.left() + rect.width(), rect.top() + rect.height())
            cropped = img.crop(box)
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
        
        # Get Lanczos-resized crop
        src_qimage = self._get_lanczos_crop(image_path, bounding_rect, (target_w, target_h))
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

    def add_fragment(self, image_path, points, real_width, original_width):
        pixmap = self.create_masked_pixmap(image_path, points, real_width, original_width)
        if not pixmap: return

        item = AtlasItem(pixmap)
        item.setPos(0, 0) 
        
        # Store metadata
        item.filepath = image_path
        item.points = points
        item.real_width = real_width
        item.original_width = original_width
        
        # Legacy support for scale logic (using data)
        item.setData(Qt.UserRole + 1, real_width)
        item.setData(Qt.UserRole + 2, original_width)
        
        self.scene.addItem(item)
        item.setScale(1.0)

    def update_item(self, item, points, real_width, original_width):
        pixmap = self.create_masked_pixmap(item.filepath, points, real_width, original_width)
        if not pixmap: return
        
        item.setPixmap(pixmap)
        item.points = points
        item.real_width = real_width
        item.original_width = original_width
        
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
        
        # Restore
        self.scene.setBackgroundBrush(old_bg)
        self.scene.grid_enabled = old_grid
        self.scene.exporting = old_exporting
        for item in selected_items:
            item.setSelected(True)
            
        image.save(filename)
