from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsItem, QPushButton, QDoubleSpinBox, QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QBrush
from PySide6.QtCore import Qt, QPointF, Signal, QRectF

class HandleItem(QGraphicsEllipseItem):
    def __init__(self, x, y, r, parent=None):
        super().__init__(-r, -r, r*2, r*2, parent)
        self.setPos(x, y)
        self.setPen(QPen(Qt.yellow))
        self.setBrush(QBrush(Qt.red))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            if hasattr(self.scene(), 'update_polygon_callback'):
                self.scene().update_polygon_callback()
        return super().itemChange(change, value)

class EditorView(QGraphicsView):
    point_added = Signal(QPointF)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            # Create a dummy event to start dragging immediately if needed, or just let super handle it
            # QGraphicsView handles ScrollHandDrag on left click usually, but we want middle.
            # Actually, standard behavior is often left click drag for hand.
            # But we want left click for drawing.
            # So we set ScrollHandDrag only when Middle is pressed.
            # But we need to pass the press event to the view to start the drag.
            
            # Trick: Create a LeftButton event? No, QGraphicsView supports ScrollHandDrag with LeftButton.
            # If we want MiddleButton to drag, we might need to map it.
            # Simpler: Just use Space+Left or just Middle.
            # Let's try standard ScrollHandDrag behavior: it works with Left Button.
            # But we want Left Button for drawing.
            
            # Implementation:
            # If Middle Button: set DragMode, simulate LeftButton press?
            pass # Let's stick to basic logic first.
            
            # Actually, let's implement manual panning for Middle Button
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.LeftButton:
            item = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
            if isinstance(item, HandleItem):
                super().mousePressEvent(event) # Allow moving handle
            else:
                self.point_added.emit(self.mapToScene(event.pos()))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MiddleButton:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

class EditorWidget(QWidget):
    mask_applied = Signal(str, list, float, int) # filepath, points, real_width, original_width

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Toolbar for editor
        toolbar_layout = QVBoxLayout() # Or QHBoxLayout if we want them side by side
        # Actually let's make a small toolbar area
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget) # Vertical for now
        
        self.apply_btn = QPushButton("Apply Mask")
        self.apply_btn.clicked.connect(self.apply_mask)
        tools_layout.addWidget(self.apply_btn)
        
        # Real Width Input
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(0.1, 1000.0)
        self.width_input.setValue(1.0)
        self.width_input.setSuffix(" m")
        self.width_input.setPrefix("Width: ")
        tools_layout.addWidget(self.width_input)
        
        layout.addWidget(tools_widget)

        self.scene = QGraphicsScene()
        self.scene.update_polygon_callback = self.update_polygon 
        
        self.view = EditorView(self.scene, self)
        layout.addWidget(self.view)
        
        self.current_image_item = None
        self.current_image_path = None
        self.points = [] 
        self.polygon_item = None
        self.is_closed = False

        self.view.point_added.connect(self.add_point)

    def load_image(self, filepath, existing_points=None, existing_width=None):
        self.current_image_path = filepath
        self.scene.clear()
        self.points = []
        self.polygon_item = None
        self.is_closed = False
        self.scene.update_polygon_callback = self.update_polygon 
        
        pixmap = QPixmap(filepath)
        self.current_image_item = self.scene.addPixmap(pixmap)
        self.view.fitInView(self.current_image_item, Qt.KeepAspectRatio)
        
        if existing_width:
            self.width_input.setValue(existing_width)
            
        if existing_points:
            for p in existing_points:
                self.add_point(QPointF(p[0], p[1]))

    def add_point(self, pos):
        if self.is_closed:
            return

        # Create handle
        radius = 5.0 
        handle = HandleItem(pos.x(), pos.y(), radius)
        self.scene.addItem(handle)
        
        self.points.append(handle)
        self.update_polygon()

    def update_polygon(self):
        if not self.points:
            return
            
        poly_points = [h.pos() for h in self.points]
        
        if self.polygon_item:
            self.scene.removeItem(self.polygon_item)
            
        self.polygon_item = self.scene.addPolygon(QPolygonF(poly_points), QPen(Qt.green, 2), QBrush(QColor(0, 255, 0, 50)))
        self.polygon_item.setZValue(0.5)
        
        for h in self.points:
            h.setZValue(1)

    def apply_mask(self):
        if len(self.points) < 3:
            return
        
        if not self.current_image_path or not self.current_image_item:
            return

        points = [(p.pos().x(), p.pos().y()) for p in self.points]
        real_width = self.width_input.value()
        original_width = self.current_image_item.pixmap().width()
        
        self.mask_applied.emit(self.current_image_path, points, real_width, original_width)
