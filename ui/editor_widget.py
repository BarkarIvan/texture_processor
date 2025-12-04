import math
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsItem, QPushButton, QDoubleSpinBox, QLabel, QHBoxLayout, QCheckBox, QMenu, QToolButton, QButtonGroup, QSizePolicy, QComboBox, QGraphicsLineItem
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QBrush, QAction, QPainterPath, QPainterPathStroker, QGuiApplication
from PySide6.QtCore import Qt, QPointF, Signal, QRectF, QLineF
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
            from PySide6.QtGui import QGuiApplication
            modifiers = QGuiApplication.keyboardModifiers()
            if modifiers & Qt.ShiftModifier:
                points_list = getattr(self.scene(), 'points_ref', [])
                anchor = None
                if self in points_list:
                    idx = points_list.index(self)
                    # choose nearest neighbor (prev/next)
                    prev_pt = points_list[idx - 1].pos() if idx > 0 else None
                    next_pt = points_list[idx + 1].pos() if idx + 1 < len(points_list) else None
                    if prev_pt and next_pt:
                        if (prev_pt - new_pos).manhattanLength() <= (next_pt - new_pos).manhattanLength():
                            anchor = prev_pt
                        else:
                            anchor = next_pt
                    else:
                        anchor = prev_pt or next_pt
                if anchor:
                    dx = new_pos.x() - anchor.x()
                    dy = new_pos.y() - anchor.y()
                    # Snap to axis relative to nearest neighbor
                    if abs(dx) > abs(dy):
                        new_pos = QPointF(new_pos.x(), anchor.y())
                    else:
                        new_pos = QPointF(anchor.x(), new_pos.y())

            # Snap to guides (vertical/horizontal)
            scene = self.scene()
            if scene:
                threshold = getattr(scene, 'guide_snap_threshold', None)
                guides_v = getattr(scene, 'guides_v', [])
                guides_h = getattr(scene, 'guides_h', [])
                if threshold is not None:
                    closest_v = min(guides_v, key=lambda g: abs(g - new_pos.x()), default=None) if guides_v else None
                    if closest_v is not None and abs(closest_v - new_pos.x()) <= threshold:
                        new_pos = QPointF(closest_v, new_pos.y())
                    closest_h = min(guides_h, key=lambda g: abs(g - new_pos.y()), default=None) if guides_h else None
                    if closest_h is not None and abs(closest_h - new_pos.y()) <= threshold:
                        new_pos = QPointF(new_pos.x(), closest_h)
                if hasattr(scene, 'update_polygon_callback'):
                    scene.update_polygon_callback()
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

    def mousePressEvent(self, event):
        # Capture state before move for undo
        if hasattr(self.scene(), 'push_state_callback'):
            self.scene().push_state_callback()
        super().mousePressEvent(event)

class EditablePolygonItem(QGraphicsPolygonItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dragging = False
        self.drag_last = None

    def mousePressEvent(self, event):
        if getattr(self.scene(), 'scale_mode_active', False):
            event.ignore()
            return
        # Drag polygon only when Ctrl held; otherwise let click pass through for adding points
        if not (event.modifiers() & Qt.ControlModifier):
            self.dragging = False
            event.ignore()
            return
        if hasattr(self.scene(), 'push_state_callback'):
            self.scene().push_state_callback()
        self.dragging = True
        self.drag_last = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and self.drag_last is not None:
            delta = event.scenePos() - self.drag_last
            points_list = getattr(self.scene(), 'points_ref', [])
            for h in points_list:
                h.setPos(h.pos() + delta)
            self.drag_last = event.scenePos()
            # Update polygon in place
            if hasattr(self.scene(), 'points_ref'):
                poly_points = [h.pos() for h in points_list]
                self.setPolygon(QPolygonF(poly_points))
            if hasattr(self.scene(), 'update_polygon_callback'):
                self.scene().update_polygon_callback()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.drag_last = None
        event.accept()


class GuideLineItem(QGraphicsLineItem):
    def __init__(self, orientation, x_or_y, rect, owner, index):
        if orientation == 'v':
            line = QLineF(0, rect.top(), 0, rect.bottom())
            super().__init__(line)
            self.setPos(x_or_y, 0)
        else:
            line = QLineF(rect.left(), 0, rect.right(), 0)
            super().__init__(line)
            self.setPos(0, x_or_y)
        self.orientation = orientation
        self.owner = owner
        self.index = index
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setCursor(Qt.SizeHorCursor if orientation == 'v' else Qt.SizeVerCursor)
        self.dragging = False
        self.drag_offset = 0.0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_offset = 0.0
            if self.orientation == 'v':
                self.drag_offset = self.pos().x() - event.scenePos().x()
            else:
                self.drag_offset = self.pos().y() - event.scenePos().y()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging and (event.buttons() & Qt.LeftButton):
            if self.orientation == 'v':
                new_x = event.scenePos().x() + self.drag_offset
                self.setPos(new_x, 0)
                if 0 <= self.index < len(self.owner.guides_v):
                    self.owner.guides_v[self.index] = new_x
            else:
                new_y = event.scenePos().y() + self.drag_offset
                self.setPos(0, new_y)
                if 0 <= self.index < len(self.owner.guides_h):
                    self.owner.guides_h[self.index] = new_y
            self.owner.scene.guides_h = self.owner.guides_h
            self.owner.scene.guides_v = self.owner.guides_v
            self.owner.scene.guide_snap_threshold = self.owner.guide_snap_threshold
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
        super().mouseReleaseEvent(event)

    def shape(self):
        # Make picking area thicker for easier dragging
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(super().shape())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.owner:
            pos = value
            if self.orientation == 'v':
                pos = QPointF(pos.x(), 0)
                if 0 <= self.index < len(self.owner.guides_v):
                    self.owner.guides_v[self.index] = pos.x()
            else:
                pos = QPointF(0, pos.y())
                if 0 <= self.index < len(self.owner.guides_h):
                    self.owner.guides_h[self.index] = pos.y()
            # Propagate to scene for snapping
            self.owner.scene.guides_h = self.owner.guides_h
            self.owner.scene.guides_v = self.owner.guides_v
            self.owner.scene.guide_snap_threshold = self.owner.guide_snap_threshold
            return pos
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        add_action = None
        menu = QMenu()
        add_action = menu.addAction("Add Point Here")
        action = menu.exec(event.screenPos())
        if action == add_action:
            if hasattr(self.scene(), 'insert_point_callback'):
                self.scene().insert_point_callback(event.scenePos())
        else:
            super().contextMenuEvent(event)

class EditorWidget(QWidget):
    mask_applied = Signal(str, list, float, int, object, object) # filepath, points, real_width, original_width, item_ref, mask_id

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
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

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo)
        tools_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.clicked.connect(self.redo)
        tools_layout.addWidget(self.redo_btn)

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

        # Mask selector (shows all masks of current texture)
        self.mask_combo = QComboBox()
        self.mask_combo.setMinimumWidth(140)
        self.mask_combo.currentIndexChanged.connect(self.on_mask_selected)
        tools_layout.addWidget(self.mask_combo)

        # Guide controls
        self.add_h_guide_btn = QToolButton()
        self.add_h_guide_btn.setText("+H guide")
        self.add_h_guide_btn.clicked.connect(self.add_horizontal_guide)
        tools_layout.addWidget(self.add_h_guide_btn)

        self.add_v_guide_btn = QToolButton()
        self.add_v_guide_btn.setText("+V guide")
        self.add_v_guide_btn.clicked.connect(self.add_vertical_guide)
        tools_layout.addWidget(self.add_v_guide_btn)

        self.clear_guides_btn = QToolButton()
        self.clear_guides_btn.setText("Clear guides")
        self.clear_guides_btn.clicked.connect(self.clear_guides)
        tools_layout.addWidget(self.clear_guides_btn)
        
        tools_layout.addStretch()
        layout.addWidget(tools_widget)

        # Tool button styles for selected state
        btn_style = """
        QToolButton {
            background: #131722;
            color: #e7e9ef;
            border: 1px solid #242a3a;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 9pt;
        }
        QToolButton:checked {
            background: #2d76ff;
            border: 1px solid #2d76ff;
            color: #f7f8fb;
        }
        QToolButton:hover {
            background: #202534;
        }
        """
        self.poly_tool.setStyleSheet(btn_style)
        self.rect_tool.setStyleSheet(btn_style)
        self.scale_btn.setStyleSheet(btn_style)

        btn_normal_style = """
        QPushButton {
            background: #1b2030;
            border: 1px solid #242a3a;
            color: #e7e9ef;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 9pt;
        }
        QPushButton:hover { background: #202534; }
        QPushButton:pressed { background: #2d76ff; border-color: #2d76ff; }
        """
        for b in (self.apply_btn, self.clear_btn, self.undo_btn, self.redo_btn):
            b.setStyleSheet(btn_normal_style)

        # Mask management
        self.masks_data = []  # list of dicts with id, points, real_width, original_width, color
        self.current_mask_color = QColor(0, 255, 0, 120)

        # Overlay/guide storage
        self.overlay_items = []
        self.guides_h = []
        self.guides_v = []
        self.guide_items = []
        self.guide_snap_threshold = 8.0
        self.last_hover_pos = None
        self.dragging_guide = None

        self.scene = QGraphicsScene()
        self.scene.update_polygon_callback = self.update_polygon 
        self.scene.delete_point_callback = self.delete_point
        self.scene.insert_point_callback = self.insert_point_at
        self.scene.push_state_callback = self.push_state
        self.scene.scale_mode_active = False
        self.scene.guides_h = self.guides_h
        self.scene.guides_v = self.guides_v
        self.scene.guide_snap_threshold = self.guide_snap_threshold
        
        self.view = ZoomPanView(self.scene, self)
        layout.addWidget(self.view)
        
        self.current_image_item = None
        self.current_image_path = None
        self.points = [] 
        self.scene.points_ref = self.points
        self.polygon_item = None
        # Polygon mode is never auto-closed; Rect mode sets is_closed explicitly
        self.is_closed = False
        self.editing_item = None 
        self.rect_preview = None
        self.px_per_meter = None
        self.scale_mode_active = False
        self.scale_points = []
        self.scale_line = None
        self.current_mask_id = None
        self.undo_stack = []
        self.redo_stack = []
        self.applying_state = False

        self.view.clicked.connect(self.on_view_clicked)
        # Track mouse move for Rect Mode preview
        self.view.mouseMoved.connect(self.on_view_mouse_moved)
        self.view.leftReleased.connect(self.on_view_left_released)
        self.view.hoverMoved.connect(self.on_view_hovered)
    def on_view_hovered(self, pos, zoom):
        self.last_hover_pos = pos

    def add_horizontal_guide(self):
        if not self.current_image_item and not self.current_image_path:
            return
        y = self.last_hover_pos.y() if self.last_hover_pos else 0.0
        self.guides_h.append(y)
        self.render_guides()

    def add_vertical_guide(self):
        if not self.current_image_item and not self.current_image_path:
            return
        x = self.last_hover_pos.x() if self.last_hover_pos else 0.0
        self.guides_v.append(x)
        self.render_guides()

    def clear_guides(self):
        # Items might already be deleted if scene was cleared earlier
        for item in list(self.guide_items):
            try:
                if item.scene():
                    self.scene.removeItem(item)
            except RuntimeError:
                pass
        self.guide_items = []
        self.guides_h = []
        self.guides_v = []
        self.scene.guides_h = self.guides_h
        self.scene.guides_v = self.guides_v
        self.scene.guide_snap_threshold = self.guide_snap_threshold

    def render_guides(self):
        for item in self.guide_items:
            self.scene.removeItem(item)
        self.guide_items = []
        if not self.current_image_item:
            return
        self.scene.guides_h = self.guides_h
        self.scene.guides_v = self.guides_v
        self.scene.guide_snap_threshold = self.guide_snap_threshold
        rect = self.current_image_item.boundingRect()
        pen = QPen(QColor(120, 180, 255, 180), 2, Qt.DashLine)
        for idx, y in enumerate(self.guides_h):
            line = GuideLineItem('h', y, rect, self, idx)
            line.setPen(pen)
            line.setZValue(2.0)
            self.scene.addItem(line)
            self.guide_items.append(line)
        for idx, x in enumerate(self.guides_v):
            line = GuideLineItem('v', x, rect, self, idx)
            line.setPen(pen)
            line.setZValue(2.0)
            self.scene.addItem(line)
            self.guide_items.append(line)

    def try_start_drag_guide(self, pos):
        if not self.current_image_item:
            return False
        thresh = self.guide_snap_threshold
        # Check vertical guides
        for idx, x in enumerate(self.guides_v):
            if abs(pos.x() - x) <= thresh:
                self.dragging_guide = ('v', idx)
                return True
        for idx, y in enumerate(self.guides_h):
            if abs(pos.y() - y) <= thresh:
                self.dragging_guide = ('h', idx)
                return True
        return False

    def _snap_guide_to_points(self, kind, cursor_pos):
        """Find nearest point to cursor within snap threshold and return axis value."""
        threshold = self.guide_snap_threshold
        if threshold is None:
            return None
        best_val = None
        best_dist = threshold + 1.0

        def consider_point(px, py, current_best_dist, current_best_val):
            dist = math.hypot(px - cursor_pos.x(), py - cursor_pos.y())
            if dist <= threshold and dist < current_best_dist:
                return dist, (px if kind == 'v' else py)
            return current_best_dist, current_best_val

        # Active mask points
        for handle in self.points:
            pt = handle.pos()
            best_dist, best_val = consider_point(pt.x(), pt.y(), best_dist, best_val)

        # Other masks (including current mask if saved)
        for m in self.masks_data:
            for px, py in m.get('points') or []:
                best_dist, best_val = consider_point(px, py, best_dist, best_val)

        return best_val

    def load_image(self, filepath, existing_points=None, existing_width=None, item_ref=None, px_per_meter=None, mask_id=None, masks=None):
        # Full reset for new texture
        self.clear_guides()
        self.scene.clear()
        # Restore callbacks lost after clear()
        self.scene.update_polygon_callback = self.update_polygon 
        self.scene.delete_point_callback = self.delete_point
        self.scene.insert_point_callback = self.insert_point_at
        self.scene.push_state_callback = self.push_state
        self.scene.scale_mode_active = False

        self.overlay_items = []
        self.points = []
        self.scene.points_ref = self.points
        self.polygon_item = None
        self.is_closed = False
        self.rect_preview = None
        self.scale_mode_active = False
        self.scale_points = []
        self.scale_line = None
        self.current_image_item = None
        self.current_image_path = filepath
        self.editing_item = item_ref
        self.current_mask_id = mask_id
        self.undo_stack = []
        self.redo_stack = []
        self.applying_state = False
        self.px_per_meter = px_per_meter
        self.last_hover_pos = None

        pixmap = QPixmap(filepath)
        self.current_image_item = self.scene.addPixmap(pixmap)
        self.current_image_item.setAcceptedMouseButtons(Qt.NoButton)
        self.current_image_item.setZValue(-1)
        self.scene.setSceneRect(self.current_image_item.boundingRect())
        self.view.fitInView(self.current_image_item, Qt.KeepAspectRatio)

        # Load all masks for this texture
        self.set_masks_data(masks or [], active_id=mask_id)

        # Legacy direct points fallback (if active mask not found)
        active_mask = self.get_mask_entry(self.current_mask_id)
        if not active_mask and existing_points:
            self.current_mask_id = None
            self.current_mask_color = QColor(0, 255, 0, 120)
            self._load_points_into_scene(existing_points, existing_width)

        self.render_guides()

    def _remove_edit_items(self):
        if self.polygon_item:
            self.scene.removeItem(self.polygon_item)
            self.polygon_item = None
        if self.rect_preview:
            self.scene.removeItem(self.rect_preview)
            self.rect_preview = None
        if self.scale_line:
            self.scene.removeItem(self.scale_line)
            self.scale_line = None
        for h in self.points:
            self.scene.removeItem(h)
        self.points = []
        self.scene.points_ref = self.points

    def clear_mask(self, reset_history=False):
        if not reset_history:
            self.push_state()
        self._remove_edit_items()
        self.is_closed = False
        self.scale_mode_active = False
        self.scale_points = []
        self.scene.scale_mode_active = False
        if reset_history:
            self.undo_stack = []
            self.redo_stack = []
        # Keep background/overlays/guides; refresh overlays for clarity
        self.refresh_mask_overlays()

    def set_masks_data(self, masks, active_id=None):
        # Ensure colors and store
        self.masks_data = []
        for m in masks:
            entry = dict(m) if isinstance(m, dict) else {}
            if 'color' not in entry or not entry.get('color'):
                entry['color'] = self._generated_color(entry.get('id'))
            self.masks_data.append(entry)
        self.masks_data.sort(key=lambda m: m.get('id', 0) or 0)
        if active_id is None and self.masks_data:
            active_id = self.masks_data[0].get('id')
        self.current_mask_id = active_id
        self.refresh_mask_combo()
        self.refresh_mask_overlays()
        if self.current_mask_id is not None:
            mask = self.get_mask_entry(self.current_mask_id)
            if mask:
                self.current_mask_color = self._color_from_value(mask.get('color'))
                self._load_points_into_scene(mask.get('points') or [], mask.get('real_width'))
        else:
            self.current_mask_color = QColor(0, 255, 0, 120)

    def refresh_mask_combo(self):
        self.mask_combo.blockSignals(True)
        self.mask_combo.clear()
        self.mask_combo.addItem("New mask", None)
        for m in self.masks_data:
            label = f"Mask {m.get('id', '?')}"
            self.mask_combo.addItem(label, m.get('id'))
        idx = self.mask_combo.findData(self.current_mask_id)
        if idx != -1:
            self.mask_combo.setCurrentIndex(idx)
        else:
            self.current_mask_id = None
            self.mask_combo.setCurrentIndex(0)
        self.mask_combo.blockSignals(False)

    def refresh_mask_overlays(self):
        for item in self.overlay_items:
            self.scene.removeItem(item)
        self.overlay_items = []
        if not self.current_image_item:
            return
        for m in self.masks_data:
            if m.get('id') == self.current_mask_id:
                continue
            pts = m.get('points') or []
            if len(pts) >= 3:
                poly = QPolygonF([QPointF(p[0], p[1]) for p in pts])
                outline_color = self._color_from_value(m.get('color'), alpha_override=150)
                fill_color = QColor(outline_color)
                fill_color.setAlpha(70)
                pen = QPen(outline_color, 0)
                ghost_brush = QBrush(fill_color)
                item = self.scene.addPolygon(poly, pen, ghost_brush)
                item.setZValue(0.3)
                item.setAcceptedMouseButtons(Qt.NoButton)
                self.overlay_items.append(item)

            # Show ghost vertices for clarity
            if pts:
                point_color = self._color_from_value(m.get('color'), alpha_override=220)
                for px, py in pts:
                    marker = self.scene.addEllipse(-3.0, -3.0, 6.0, 6.0, QPen(point_color, 0), QBrush(point_color))
                    marker.setPos(px, py)
                    marker.setZValue(0.35)
                    marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                    marker.setAcceptedMouseButtons(Qt.NoButton)
                    self.overlay_items.append(marker)

    def on_mask_selected(self, index):
        mask_id = self.mask_combo.currentData()
        if mask_id == self.current_mask_id:
            return
        # New mask request
        if mask_id is None:
            next_id = max([m.get('id', 0) for m in self.masks_data] + [0]) + 1
            new_color = self._generated_color(next_id)
            self.masks_data.append({
                'id': next_id,
                'points': [],
                'real_width': None,
                'original_width': None,
                'color': new_color
            })
            self.current_mask_id = next_id
            self.current_mask_color = self._color_from_value(new_color)
            # New mask means we start fresh, no bound atlas item
            self.editing_item = None
            self.refresh_mask_combo()
            self._remove_edit_items()
            self.is_closed = False
            self.scale_mode_active = False
            self.scene.scale_mode_active = False
            self.scale_points = []
            self.scale_line = None
            self.width_input.setValue(self.width_input.minimum())
            self.refresh_mask_overlays()
            return

        # Switching to an existing mask: drop atlas linkage if it doesn't match
        if self.editing_item and getattr(self.editing_item, 'mask_id', None) != mask_id:
            self.editing_item = None

        self.current_mask_id = mask_id
        self._remove_edit_items()
        self.is_closed = False
        self.rect_preview = None
        self.scale_mode_active = False
        self.scene.scale_mode_active = False
        self.scale_points = []
        self.scale_line = None
        mask = self.get_mask_entry(mask_id)
        if not mask:
            return
        self.current_mask_color = self._color_from_value(mask.get('color'))
        width_val = mask.get('real_width')
        if width_val:
            self.width_input.setValue(width_val)
        self._load_points_into_scene(mask.get('points') or [], width_val)
        self.refresh_mask_overlays()

    def refresh_masks_view(self, filepath, masks, active_id=None):
        if filepath != self.current_image_path:
            return
        self.set_masks_data(masks, active_id or self.current_mask_id)

    def _load_points_into_scene(self, points, width_value=None):
        self._remove_edit_items()
        self.applying_state = True
        for p in points:
            handle = HandleItem(p[0], p[1], 4.0)
            self.scene.addItem(handle)
            self.points.append(handle)
        self.scene.points_ref = self.points
        if width_value:
            self.width_input.setValue(width_value)
        self.is_closed = len(self.points) >= 3
        self.update_polygon()
        self.applying_state = False
        self.update_width_from_scale()

    def get_mask_entry(self, mask_id):
        for m in self.masks_data:
            if m.get('id') == mask_id:
                return m
        return None

    def _generated_color(self, seed):
        # Deterministic bright-ish color from seed
        hue = ((seed or 1) * 73) % 360
        c = QColor()
        c.setHsv(hue, 200, 255, 160)
        return c.name()

    def _color_from_value(self, value, alpha_override=None):
        if value:
            color = QColor(value)
        else:
            color = QColor(0, 255, 0)
        if alpha_override is not None:
            color.setAlpha(int(alpha_override))
        elif color.alpha() == 255:
            color.setAlpha(120)
        return color

    def on_view_clicked(self, pos):
        # Drag guide if near
        if self.try_start_drag_guide(pos):
            return
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
        self.scene.scale_mode_active = True
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
                self.push_state()
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
            self.scene.scale_mode_active = False
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
        # Dragging guide
        if self.dragging_guide:
            kind, idx = self.dragging_guide
            rect = self.current_image_item.boundingRect() if self.current_image_item else QRectF(0, 0, 0, 0)
            if kind == 'h' and 0 <= idx < len(self.guides_h):
                y = max(rect.top(), min(rect.bottom(), pos.y()))
                snap_y = self._snap_guide_to_points('h', pos)
                if snap_y is not None:
                    y = max(rect.top(), min(rect.bottom(), snap_y))
                self.guides_h[idx] = y
            elif kind == 'v' and 0 <= idx < len(self.guides_v):
                x = max(rect.left(), min(rect.right(), pos.x()))
                snap_x = self._snap_guide_to_points('v', pos)
                if snap_x is not None:
                    x = max(rect.left(), min(rect.right(), snap_x))
                self.guides_v[idx] = x
            self.scene.guides_h = self.guides_h
            self.scene.guides_v = self.guides_v
            self.render_guides()
            return
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
        if self.dragging_guide:
            self.dragging_guide = None
            return
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
            
            self.push_state()
            self.add_point(QPointF(x2, y1))
            self.add_point(QPointF(x2, y2))
            self.add_point(QPointF(x1, y2))
            
            self.is_closed = True
            # Remove preview once finalized
            if self.rect_preview:
                self.scene.removeItem(self.rect_preview)
                self.rect_preview = None
            self.update_polygon()

    def push_state(self):
        if self.applying_state:
            return
        state = {
            'points': [(p.pos().x(), p.pos().y()) for p in self.points],
            'width': self.width_input.value(),
            'px_per_meter': self.px_per_meter,
            'scale_line': None  # not restoring line for simplicity
        }
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        state = self.undo_stack.pop()
        self.redo_stack.append({
            'points': [(p.pos().x(), p.pos().y()) for p in self.points],
            'width': self.width_input.value(),
            'px_per_meter': self.px_per_meter,
            'scale_line': None
        })
        self.apply_state(state)

    def redo(self):
        if not self.redo_stack:
            return
        state = self.redo_stack.pop()
        self.undo_stack.append({
            'points': [(p.pos().x(), p.pos().y()) for p in self.points],
            'width': self.width_input.value(),
            'px_per_meter': self.px_per_meter,
            'scale_line': None
        })
        self.apply_state(state)

    def apply_state(self, state):
        self.applying_state = True
        self._remove_edit_items()
        self.is_closed = False
        self.rect_preview = None
        self.scale_mode_active = False
        self.scale_points = []
        self.scene.scale_mode_active = False

        for x, y in state.get('points', []):
            handle = HandleItem(x, y, 4.0)
            self.scene.addItem(handle)
            self.points.append(handle)
        self.scene.points_ref = self.points
        self.width_input.setValue(state.get('width', self.width_input.value()))
        self.px_per_meter = state.get('px_per_meter')
        self.is_closed = False
        self.update_polygon()
        self.update_width_from_scale()
        self.applying_state = False

    def add_point(self, pos):
        if self.is_closed:
            return
        self.push_state()

        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier:
            if self.points:
                last = self.points[-1].pos()
                dx = pos.x() - last.x()
                dy = pos.y() - last.y()
                if dx != 0 or dy != 0:
                    # Snap direction to nearest axis/diagonal
                    dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
                    best_dir = None
                    best_dot = -1.0
                    for vx, vy in dirs:
                        norm = math.hypot(vx, vy)
                        ux, uy = vx / norm, vy / norm
                        dot = abs(dx * ux + dy * uy)
                        if dot > best_dot:
                            best_dot = dot
                            best_dir = (ux, uy)
                    if best_dir:
                        ux, uy = best_dir
                        length = dx * ux + dy * uy  # no extra rounding
                        pos = QPointF(last.x() + ux * length, last.y() + uy * length)
            else:
                # First point: keep as is
                pass

        radius = 4.0 
        handle = HandleItem(pos.x(), pos.y(), radius)
        self.scene.addItem(handle)
        
        self.points.append(handle)
        self.update_polygon()
        self.update_width_from_scale()

    def delete_point(self, handle_item):
        if handle_item in self.points:
            self.push_state()
            self.points.remove(handle_item)
            self.scene.removeItem(handle_item)
            self.update_polygon()
            self.update_width_from_scale()

    def insert_point_at(self, scene_pos):
        if len(self.points) < 2:
            return
        self.push_state()
        # Find closest segment
        min_dist = float('inf')
        best_point = None
        best_idx = None
        n = len(self.points)
        for i in range(n):
            p1 = self.points[i].pos()
            p2 = self.points[(i + 1) % n].pos()
            v = p2 - p1
            seg_len_sq = v.x()*v.x() + v.y()*v.y()
            if seg_len_sq == 0:
                continue
            t = ((scene_pos.x() - p1.x()) * v.x() + (scene_pos.y() - p1.y()) * v.y()) / seg_len_sq
            t = max(0.0, min(1.0, t))
            proj = QPointF(p1.x() + v.x() * t, p1.y() + v.y() * t)
            dist_sq = (scene_pos.x() - proj.x())**2 + (scene_pos.y() - proj.y())**2
            if dist_sq < min_dist:
                min_dist = dist_sq
                best_point = proj
                best_idx = i
        if best_point is None or best_idx is None:
            return

        radius = 4.0
        handle = HandleItem(best_point.x(), best_point.y(), radius)
        self.scene.addItem(handle)
        self.points.insert(best_idx + 1, handle)
        self.scene.points_ref = self.points
        self.update_polygon()
        self.update_width_from_scale()

    def update_polygon(self):
        if not self.points:
            if self.polygon_item:
                self.scene.removeItem(self.polygon_item)
                self.polygon_item = None
            return
            
        poly_points = [h.pos() for h in self.points]
        
        if self.polygon_item:
            self.polygon_item.setPolygon(QPolygonF(poly_points))
        else:
            poly_item = EditablePolygonItem(QPolygonF(poly_points))
            poly_item.setZValue(0.5)
            self.scene.addItem(poly_item)
            self.polygon_item = poly_item

        # Refresh colors on every update in case active mask changed
        base_color = QColor(self.current_mask_color)
        outline_color = QColor(base_color)
        outline_color.setAlpha(220)
        fill_color = QColor(base_color)
        if fill_color.alpha() < 40:
            fill_color.setAlpha(60)
        self.polygon_item.setPen(QPen(outline_color, 0))
        self.polygon_item.setBrush(QBrush(fill_color))

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
