"""
ui/connection_line.py
Phase 4 — Bezier belt/pipe connection between two PortItems.

ConnectionLine    – persistent line saved to DB.
TempConnectionLine – rubber-band line shown while dragging.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QGraphicsItem
from PySide6.QtCore    import Qt, QPointF, QRectF
from PySide6.QtGui     import (
    QPainterPath, QPen, QColor, QBrush, QFont,
    QPainter,
)


# Colour per material type
_BELT_COLOR  = QColor("#e87722")   # orange — solids (belts)
_PIPE_COLOR  = QColor("#4ab0d9")   # teal   — liquids/gases (pipes)
_TEMP_COLOR  = QColor("#ffffff")   # white dashed — while dragging
_LABEL_BG    = QColor(0, 0, 0, 160)

# Bezier control-point horizontal offset
_CTRL_OFFSET = 100


class ConnectionLine(QGraphicsPathItem):
    """
    A cubic Bezier curve connecting an output port to an input port.

    The line colour is orange for solids, teal for liquids/gases.
    A small text label at the midpoint shows material name + rate.
    """

    def __init__(
        self,
        src_port,
        tgt_port,
        db_id: int | None = None,
        material_id: int | None = None,
    ):
        super().__init__()
        self.src_port    = src_port
        self.tgt_port    = tgt_port
        self.conn_db_id  = db_id
        self.material_id = material_id

        # Runtime result from engine
        self._flow_rate:   float = 0.0
        self._mat_name:    str   = ""
        self._status:      str   = "ok"
        self._mat_type:    str   = "solid"   # "solid" | "liquid" | "gas"

        # Fetch material type for colour
        if material_id is not None:
            self._load_material(material_id)

        # Label text item (child of this item)
        self._label = QGraphicsTextItem(self)
        self._label.setDefaultTextColor(QColor("#ffffff"))
        self._label.setFont(QFont("Segoe UI", 8))
        self._label.setZValue(20)

        self.setZValue(0)   # below nodes
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        self.update_path()

    def _load_material(self, mat_id: int) -> None:
        from database.crud import get_material_by_id
        mat = get_material_by_id(mat_id)
        if mat:
            self._mat_name = mat["name"]
            self._mat_type = mat["type"]

    # ------------------------------------------------------------------
    # Path computation
    # ------------------------------------------------------------------
    def update_path(self) -> None:
        """Recompute the Bezier curve and reposition the label."""
        p1 = self.src_port.center_scene_pos()
        p2 = self.tgt_port.center_scene_pos()

        ctrl1 = QPointF(p1.x() + _CTRL_OFFSET, p1.y())
        ctrl2 = QPointF(p2.x() - _CTRL_OFFSET, p2.y())

        path = QPainterPath(p1)
        path.cubicTo(ctrl1, ctrl2, p2)
        self.setPath(path)

        # Update pen based on material type + status
        color = self._line_color()
        width = 3.0 if self._status == "ok" else 2.5
        pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        if self._status == "deficit":
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)

        # Position label at the midpoint of the Bezier
        mid = path.pointAtPercent(0.5)
        self._label.setPos(mid.x() - self._label.boundingRect().width() / 2,
                           mid.y() - 18)
        self._update_label()

    def _line_color(self) -> QColor:
        if self._status == "deficit":
            return QColor("#f44336")
        if self._mat_type in ("liquid", "gas"):
            return _PIPE_COLOR
        return _BELT_COLOR

    def _update_label(self) -> None:
        if self._mat_name:
            text = f"{self._mat_name}  {self._flow_rate:.1f}/min"
        else:
            text = ""
        self._label.setPlainText(text)

    # ------------------------------------------------------------------
    # Hover highlight
    # ------------------------------------------------------------------
    def hoverEnterEvent(self, event) -> None:
        pen = self.pen()
        pen.setWidth(int(pen.width()) + 2)
        self.setPen(pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.update_path()
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Right-click delete
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background:#16213e; color:#eaeaea; border:1px solid #4a4a8a; }"
            "QMenu::item:selected { background:#0f3460; }"
        )
        action_del = menu.addAction("Delete Connection")
        chosen = menu.exec(event.screenPos())
        if chosen == action_del:
            self._delete_self()

    def _delete_self(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        self.src_port.connections = [c for c in self.src_port.connections if c is not self]
        self.tgt_port.connections = [c for c in self.tgt_port.connections if c is not self]
        scene.remove_connection(self)
        scene.recalculate()

    # ------------------------------------------------------------------
    # Apply engine result
    # ------------------------------------------------------------------
    def apply_result(self, result) -> None:
        self._flow_rate = result.flow_rate
        self._status    = result.status
        if result.material_name:
            self._mat_name = result.material_name
        self.update_path()

    # ------------------------------------------------------------------
    # DB serialisation
    # ------------------------------------------------------------------
    def to_db_dict(self) -> dict:
        return {
            "id":             self.conn_db_id or id(self),
            "source_node_id": self.src_port.parent_node.node_db_id or id(self.src_port.parent_node),
            "target_node_id": self.tgt_port.parent_node.node_db_id or id(self.tgt_port.parent_node),
            "material_id":    self.material_id,
            "current_velocity": self._flow_rate,
        }


# ---------------------------------------------------------------------------
# Temporary rubber-band line (while dragging from a port)
# ---------------------------------------------------------------------------
class TempConnectionLine(QGraphicsPathItem):
    """White dashed line shown during a drag-to-connect operation."""

    def __init__(self):
        super().__init__()
        pen = QPen(_TEMP_COLOR, 2, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(100)

    def update_endpoints(self, p1: QPointF, p2: QPointF) -> None:
        ctrl1 = QPointF(p1.x() + _CTRL_OFFSET, p1.y())
        ctrl2 = QPointF(p2.x() - _CTRL_OFFSET, p2.y())
        path = QPainterPath(p1)
        path.cubicTo(ctrl1, ctrl2, p2)
        self.setPath(path)
