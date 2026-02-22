"""
ui/port_item.py
Phase 3 — Input/Output connector dots on machine nodes.

Each PortItem is a small coloured circle.  Dragging from an output port
to an input port creates a ConnectionLine.
"""

from __future__ import annotations
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtCore    import Qt, QPointF, QRectF
from PySide6.QtGui     import QPen, QBrush, QColor


# Colour constants
_OUT_COLOR    = QColor("#e87722")   # amber/orange  — output (produces)
_IN_COLOR     = QColor("#4a90d9")   # blue          — input  (consumes)
_HOVER_COLOR  = QColor("#ffffff")
_PORT_RADIUS  = 6


class PortItem(QGraphicsEllipseItem):
    """
    A small circle representing one connection point on a MachineNode.

    Attributes:
        port_type:    "in" | "out"
        parent_node:  The MachineNode that owns this port.
        connections:  List of ConnectionLine objects attached to this port.
    """

    def __init__(self, port_type: str, parent_node, parent_item: QGraphicsItem):
        r = _PORT_RADIUS
        super().__init__(-r, -r, r * 2, r * 2, parent_item)
        self.port_type   = port_type          # "in" or "out"
        self.parent_node = parent_node
        self.connections: list = []           # ConnectionLine objects

        color = _OUT_COLOR if port_type == "out" else _IN_COLOR
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#ffffff"), 1.2))
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)

        # Port items are children of the node item — no need for
        # ItemIsMovable; they follow their parent automatically.

    # ------------------------------------------------------------------
    # Hover glow
    # ------------------------------------------------------------------
    def hoverEnterEvent(self, event) -> None:
        self.setPen(QPen(_HOVER_COLOR, 2.5))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setPen(QPen(QColor("#ffffff"), 1.2))
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Drag-to-connect: handled at the scene level via mouse events
    # routed through FactoryView → FactoryScene.
    # Only output ports initiate drags.
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.port_type == "out":
            scene = self.scene()
            if hasattr(scene, "_start_connection_drag"):
                scene._start_connection_drag(self, event.scenePos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def center_scene_pos(self) -> QPointF:
        """Return the port's centre in scene coordinates."""
        return self.mapToScene(QPointF(0, 0))
