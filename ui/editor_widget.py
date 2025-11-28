from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsItem, QPushButton, QDoubleSpinBox, QLabel, QHBoxLayout, QCheckBox, QMenu
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QBrush, QAction, QPainterPath
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from .view_utils import ZoomPanView

class HandleItem(QGraphicsEllipseItem):
    def __init__(self, x, y, r, parent=None):
        super().__init__(-r, -r, r*2, r*2, parent)
        self.setPos(x, y)
        self.setPen(QPen(Qt.yellow))
        self.setBrush(QBrush(Qt.red))
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.radius = r

    def shape(self):
        # Larger hit area
        path = QPainterPath()
        path.addEllipse(-self.radius*2, -self.radius*2, self.radius*4, self.radius*4)
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            # Snap logic
            if hasattr(self.scene(), 'snap_enabled') and self.scene().snap_enabled:
                 # Check for Shift key? Or just always snap if enabled?
                 # User asked for "snap ... for example when button pressed".
                 # Let's check modifiers.
                 modifiers = self.scene().views()[0].modifiers() if self.scene().views() else Qt.NoModifier
                 # Wait, accessing views from item is risky.
                 # Better: Scene stores state.
                 # Let's assume snap is always on if checkbox checked, OR if Shift held.
                 # Let's implement Shift key snap.
                 pass # Logic moved to scene or handled here if we can access modifiers.
            
            # Simple grid snap if Shift is held
            # We can't easily access keyboard state here without passing it.
            # Let's try QGuiApplication.keyboardModifiers()
            from PySide6.QtGui import QGuiApplication
            if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier:
                grid_size = 20.0 # Configurable?
                x = round(new_pos.x() / grid_size) * grid_size
                y = round(new_pos.y() / grid_size) * grid_size
                new_pos = QPointF(x, y)
                return new_pos

            if hasattr(self.scene(), 'update_polygon_callback'):
                self.scene().update_polygon_callback()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction("Delete Point")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            if hasattr(self.scene(), 'delete_point_callback'):
                self.scene().delete_point_callback(self)

class EditorWidget(QWidget):
    mask_applied = Signal(str, list, float, int, object) # filepath, points, real_width, original_width, item_ref

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Toolbar
        tools_widget = QWidget()
        tools_layout = QHBoxLayout(tools_widget)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        
        self.apply_btn = QPushButton("Apply Mask")
        self.apply_btn.clicked.connect(self.apply_mask)
        tools_layout.addWidget(self.apply_btn)
        
        self.clear_btn = QPushButton("Clear Mask")
        self.clear_btn.clicked.connect(self.clear_mask)
        tools_layout.addWidget(self.clear_btn)

        self.rect_mode_chk = QCheckBox("Rect Mode")
        tools_layout.addWidget(self.rect_mode_chk)
        
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(0.1, 1000.0)
        self.width_input.setValue(1.0)
        self.width_input.setSuffix(" m")
        self.width_input.setPrefix("Width: ")
        tools_layout.addWidget(self.width_input)
        
        tools_layout.addStretch()
        layout.addWidget(tools_widget)

        self.scene = QGraphicsScene()
        self.scene.update_polygon_callback = self.update_polygon 
        self.scene.delete_point_callback = self.delete_point
        
        self.view = ZoomPanView(self.scene, self)
        layout.addWidget(self.view)
        
        self.current_image_item = None
        self.current_image_path = None
        self.points = [] 
        self.polygon_item = None
        self.is_closed = False
        self.editing_item = None 

        self.view.clicked.connect(self.on_view_clicked)

    def load_image(self, filepath, existing_points=None, existing_width=None, item_ref=None):
        self.current_image_path = filepath
        self.editing_item = item_ref
        self.clear_mask()
        
        pixmap = QPixmap(filepath)
        self.current_image_item = self.scene.addPixmap(pixmap)
        self.view.fitInView(self.current_image_item, Qt.KeepAspectRatio)
        
        if existing_width:
            self.width_input.setValue(existing_width)
            
        if existing_points:
            for p in existing_points:
                self.add_point(QPointF(p[0], p[1]))

    def clear_mask(self):
        self.scene.clear()
        self.points = []
        self.polygon_item = None
        self.is_closed = False
        self.scene.update_polygon_callback = self.update_polygon
        self.scene.delete_point_callback = self.delete_point
        
        if self.current_image_path:
            pixmap = QPixmap(self.current_image_path)
            self.current_image_item = self.scene.addPixmap(pixmap)

    def on_view_clicked(self, pos):
        if self.rect_mode_chk.isChecked():
            self.handle_rect_click(pos)
        else:
            self.add_point(pos)

    def handle_rect_click(self, pos):
        if len(self.points) >= 4 and self.is_closed:
            self.clear_mask() 
            
        if len(self.points) == 0:
            self.add_point(pos)
        elif len(self.points) == 1:
            p1 = self.points[0].pos()
            p2 = pos
            x1, y1 = p1.x(), p1.y()
            x2, y2 = p2.x(), p2.y()
            
            self.add_point(QPointF(x2, y1))
            self.add_point(QPointF(x2, y2))
            self.add_point(QPointF(x1, y2))
            
            self.is_closed = True
            self.update_polygon()

    def add_point(self, pos):
        if self.is_closed:
            return

        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier:
            grid_size = 20.0
            x = round(pos.x() / grid_size) * grid_size
            y = round(pos.y() / grid_size) * grid_size
            pos = QPointF(x, y)

        radius = 5.0 
        handle = HandleItem(pos.x(), pos.y(), radius)
        self.scene.addItem(handle)
        
        self.points.append(handle)
        self.update_polygon()

    def delete_point(self, handle_item):
        if handle_item in self.points:
            self.points.remove(handle_item)
            self.scene.removeItem(handle_item)
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
        
        # Calculate width of the mask itself
        poly = QPolygonF([p.pos() for p in self.points])
        original_width = poly.boundingRect().width()
        
        self.mask_applied.emit(self.current_image_path, points, real_width, original_width, self.editing_item)
