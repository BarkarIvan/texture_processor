import math
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsItem, QPushButton, QDoubleSpinBox, QLabel, QHBoxLayout, QCheckBox, QMenu, QToolButton, QButtonGroup
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QBrush, QAction, QPainterPath, QGuiApplication
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from .view_utils import ZoomPanView

class HandleItem(QGraphicsEllipseItem):
    def __init__(self, x, y, r, parent=None):
        super().__init__(-r, -r, r*2, r*2, parent)
        self.setPos(x, y)
        self.setPen(QPen(Qt.yellow, 0))  # Cosmetic width
        self.setBrush(QBrush(Qt.red))
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)  # Keep marker size constant on zoom
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
    mask_applied = Signal(str, list, float, int, object, object) # filepath, points, real_width, original_width, item_ref, mask_id

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

        # Tool buttons
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        self.poly_tool = QToolButton()
        self.poly_tool.setText("Polygon")
        self.poly_tool.setCheckable(True)
        self.poly_tool.setChecked(True)
        tools_layout.addWidget(self.poly_tool)
        self.tool_group.addButton(self.poly_tool)

        self.rect_tool = QToolButton()
        self.rect_tool.setText("Rect")
        self.rect_tool.setCheckable(True)
        tools_layout.addWidget(self.rect_tool)
        self.tool_group.addButton(self.rect_tool)

        self.scale_btn = QToolButton()
        self.scale_btn.setText("Set Scale")
        self.scale_btn.setCheckable(True)
        self.scale_btn.clicked.connect(self.start_scale_mode)
        tools_layout.addWidget(self.scale_btn)

        self.scale_length_input = QDoubleSpinBox()
        self.scale_length_input.setRange(0.01, 10000.0)
        self.scale_length_input.setValue(1.0)
        self.scale_length_input.setPrefix("Len: ")
        self.scale_length_input.setSuffix(" m")
        tools_layout.addWidget(self.scale_length_input)
        
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
        self.rect_preview = None
        self.px_per_meter = None
        self.scale_mode_active = False
        self.scale_points = []
        self.scale_line = None
        self.current_mask_id = None

        self.view.clicked.connect(self.on_view_clicked)
        # Track mouse move for Rect Mode preview
        self.view.mouseMoved.connect(self.on_view_mouse_moved)
        self.view.leftReleased.connect(self.on_view_left_released)

    def load_image(self, filepath, existing_points=None, existing_width=None, item_ref=None, px_per_meter=None, mask_id=None):
        self.current_image_path = filepath
        self.editing_item = item_ref
        self.clear_mask()
        self.current_mask_id = mask_id
        
        pixmap = QPixmap(filepath)
        self.current_image_item = self.scene.addPixmap(pixmap)
        self.view.fitInView(self.current_image_item, Qt.KeepAspectRatio)

        self.px_per_meter = px_per_meter
        
        if existing_width:
            self.width_input.setValue(existing_width)
            
        if existing_points:
            for p in existing_points:
                self.add_point(QPointF(p[0], p[1]))

        # If scale known and points exist, recompute width automatically
        self.update_width_from_scale()

    def clear_mask(self):
        self.scene.clear()
        self.points = []
        self.polygon_item = None
        self.is_closed = False
        self.rect_preview = None
        self.scale_mode_active = False
        self.scale_points = []
        self.scale_line = None
        self.current_mask_id = None
        self.scene.update_polygon_callback = self.update_polygon
        self.scene.delete_point_callback = self.delete_point
        
        if self.current_image_path:
            pixmap = QPixmap(self.current_image_path)
            self.current_image_item = self.scene.addPixmap(pixmap)

    def on_view_clicked(self, pos):
        # If we are setting scale, handle separately
        if self.scale_mode_active:
            self.handle_scale_click(pos)
            return

        if self.rect_tool.isChecked():
            self.handle_rect_click(pos)
        else:
            self.add_point(pos)

    def start_scale_mode(self):
        # User will click two points that represent 1 meter on the texture
        if not self.current_image_path:
            return
        self.scale_mode_active = True
        self.scale_points = []
        self.scale_btn.setChecked(True)
        if self.scale_line:
            self.scene.removeItem(self.scale_line)
            self.scale_line = None

    def handle_scale_click(self, pos):
        if not self.scale_mode_active:
            return
        self.scale_points.append(pos)
        if len(self.scale_points) == 2:
            p1, p2 = self.scale_points
            length_px = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
            if length_px > 0:
                ref_m = max(0.01, self.scale_length_input.value())
                self.px_per_meter = length_px / ref_m
                # Visual line
                if self.scale_line:
                    self.scene.removeItem(self.scale_line)
                pen = QPen(QColor(255, 0, 255), 0, Qt.DashLine)  # Cosmetic
                self.scale_line = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
            self.scale_line.setZValue(0.6)
            self.update_width_from_scale()
            self.scale_mode_active = False
            self.scale_points = []
            self.scale_btn.setChecked(False)
        else:
            # show a temporary dot/line start
            if self.scale_line:
                self.scene.removeItem(self.scale_line)
            pen = QPen(QColor(255, 0, 255), 0, Qt.DashLine)  # Cosmetic
            self.scale_line = self.scene.addLine(pos.x(), pos.y(), pos.x(), pos.y(), pen)
            self.scale_line.setZValue(0.6)

    def on_view_mouse_moved(self, pos):
        # Live preview only in Rect Mode after first point
        if self.scale_mode_active:
            return
        if not self.rect_tool.isChecked():
            return
        if len(self.points) != 1 or self.is_closed:
            return

        p1 = self.points[0].pos()
        p2 = pos
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()

        # Enforce square when Shift held
        if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier:
            dx = x2 - x1
            dy = y2 - y1
            size = max(abs(dx), abs(dy))
            sign_x = 1 if dx >= 0 else -1
            sign_y = 1 if dy >= 0 else -1
            x2 = x1 + size * sign_x
            y2 = y1 + size * sign_y

        preview_poly = QPolygonF([
            QPointF(x1, y1),
            QPointF(x2, y1),
            QPointF(x2, y2),
            QPointF(x1, y2)
        ])

        if self.rect_preview:
            self.scene.removeItem(self.rect_preview)

        pen = QPen(Qt.green, 0, Qt.DashLine)  # Cosmetic width
        brush = QBrush(QColor(0, 255, 0, 40))
        self.rect_preview = self.scene.addPolygon(preview_poly, pen, brush)
        self.rect_preview.setZValue(0.4)

    def on_view_left_released(self, pos):
        # Clear preview if user cancels rect creation (e.g., deselects mode)
        if self.rect_preview and (not self.rect_tool.isChecked() or self.is_closed or len(self.points) != 1):
            self.scene.removeItem(self.rect_preview)
            self.rect_preview = None

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

            # If Shift is held, enforce a square (use the larger delta)
            if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier:
                dx = x2 - x1
                dy = y2 - y1
                size = max(abs(dx), abs(dy))
                sign_x = 1 if dx >= 0 else -1
                sign_y = 1 if dy >= 0 else -1
                x2 = x1 + size * sign_x
                y2 = y1 + size * sign_y
            
            self.add_point(QPointF(x2, y1))
            self.add_point(QPointF(x2, y2))
            self.add_point(QPointF(x1, y2))
            
            self.is_closed = True
            # Remove preview once finalized
            if self.rect_preview:
                self.scene.removeItem(self.rect_preview)
                self.rect_preview = None
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

        radius = 4.0 
        handle = HandleItem(pos.x(), pos.y(), radius)
        self.scene.addItem(handle)
        
        self.points.append(handle)
        self.update_polygon()
        self.update_width_from_scale()

    def delete_point(self, handle_item):
        if handle_item in self.points:
            self.points.remove(handle_item)
            self.scene.removeItem(handle_item)
            self.update_polygon()
            self.update_width_from_scale()

    def update_polygon(self):
        if not self.points:
            return
            
        poly_points = [h.pos() for h in self.points]
        
        if self.polygon_item:
            self.scene.removeItem(self.polygon_item)
            
        self.polygon_item = self.scene.addPolygon(QPolygonF(poly_points), QPen(Qt.green, 0), QBrush(QColor(0, 255, 0, 50)))
        self.polygon_item.setZValue(0.5)
        
        for h in self.points:
            h.setZValue(1)
        
        # If scale known, refresh real width automatically
        self.update_width_from_scale()

    def update_width_from_scale(self):
        if not self.px_per_meter or not self.points:
            return
        poly = QPolygonF([p.pos() for p in self.points])
        width_px = poly.boundingRect().width()
        if width_px <= 0:
            return
        real_width = width_px / self.px_per_meter
        self.width_input.setValue(real_width)

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
        
        self.mask_applied.emit(self.current_image_path, points, real_width, original_width, self.editing_item, self.current_mask_id)
