from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QVBoxLayout, QGraphicsPixmapItem, QGraphicsItem
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QPolygonF, QColor, QBrush, QImage
from PySide6.QtCore import Qt, QPointF, QRectF

class AtlasItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, parent=None):
        super().__init__(pixmap, parent)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.scene = QGraphicsScene(0, 0, 2048, 2048) # Default size
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        layout.addWidget(self.view)
        
        # Draw background grid
        self.scene.setBackgroundBrush(QBrush(Qt.darkGray, Qt.Dense7Pattern))
        
        self.atlas_density = 512.0

    def set_atlas_density(self, density):
        self.atlas_density = density
        for item in self.scene.items():
            if isinstance(item, AtlasItem):
                self.update_item_scale(item)

    def update_item_scale(self, item):
        real_width = item.data(Qt.UserRole + 1)
        original_width = item.data(Qt.UserRole + 2)
        if real_width and original_width:
            texture_density = original_width / real_width
            scale = texture_density / self.atlas_density
            item.setScale(scale)

    def add_fragment(self, image_path, points, real_width, original_width):
        # 1. Load original image
        src_pixmap = QPixmap(image_path)
        if src_pixmap.isNull():
            return

        # 2. Create Masked Pixmap
        poly = QPolygonF([QPointF(x, y) for x, y in points])
        bounding_rect = poly.boundingRect().toRect()
        
        # Create target image of bounding rect size
        target_image = QImage(bounding_rect.size(), QImage.Format_ARGB32)
        target_image.fill(Qt.transparent)
        
        painter = QPainter(target_image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create path for the polygon, translated to (0,0) of the new image
        path = QPainterPath()
        translated_poly = poly.translated(-bounding_rect.topLeft())
        path.addPolygon(translated_poly)
        
        # Set clip path
        painter.setClipPath(path)
        
        # Draw original image, translated so the correct part is visible
        painter.drawPixmap(-bounding_rect.x(), -bounding_rect.y(), src_pixmap)
        painter.end()
        
        # 3. Add to Scene
        item = AtlasItem(QPixmap.fromImage(target_image))
        item.setPos(0, 0) # Default pos
        item.setData(Qt.UserRole + 1, real_width)
        item.setData(Qt.UserRole + 2, original_width)
        self.scene.addItem(item)
        self.update_item_scale(item)

    def export_atlas(self, filename):
        # Create image of scene size (or fixed 2048x2048 for now)
        rect = self.scene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()
        image.save(filename)
