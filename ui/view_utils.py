from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter

class ZoomPanView(QGraphicsView):
    clicked = Signal(QPointF) # Emits scene pos on left click
    mouseMoved = Signal(QPointF) # Emits scene pos on move with left button
    leftReleased = Signal(QPointF) # Emits scene pos on left release

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform) # High-quality image scaling
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # Full viewport updates prevent paint trails when dragging items
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._last_pan_pos = None

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.LeftButton:
            # Propagate to items first (e.g. handles)
            super().mousePressEvent(event)
            # If no item handled it, emit clicked
            if not event.isAccepted():
                 self.clicked.emit(self.mapToScene(event.pos()))
            # Note: super().mousePressEvent(event) accepts the event if an item is clicked.
            # If we want to detect if an item was clicked, we can check if scene item at pos exists.
            # But simpler: check if event is accepted? QGraphicsView implementation details vary.
            # Let's rely on the fact that if we are here, we want to handle it.
            # Actually, standard QGraphicsView logic:
            # If item clicked, it grabs mouse.
            # We want to emit 'clicked' only if NO item was clicked (background).
            item = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
            if not item:
                self.clicked.emit(self.mapToScene(event.pos()))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MiddleButton:
            if self._last_pan_pos:
                delta = event.pos() - self._last_pan_pos
                self._last_pan_pos = event.pos()
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                event.accept()
        elif event.buttons() & Qt.LeftButton:
            # Propagate movement for background interactions (e.g., rect preview)
            scene_pos = self.mapToScene(event.pos())
            self.mouseMoved.emit(scene_pos)
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setCursor(Qt.ArrowCursor)
            self._last_pan_pos = None
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self.leftReleased.emit(scene_pos)
        super().mouseReleaseEvent(event)
