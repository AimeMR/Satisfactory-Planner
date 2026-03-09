"""
ui/connection_line.py
Phase 4 — Bezier belt/pipe connection between two PortItems.

ConnectionLine    – persistent line saved to DB.
TempConnectionLine – rubber-band line shown while dragging.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PySide6.QtCore    import Qt, QPointF, QRectF, QSizeF
from PySide6.QtGui import (
    QPainterPath, QPen, QColor, QBrush, QFont,
    QPainter
)
from ui.i18n import tr


# Colour per material type
_BELT_COLOR  = QColor("#e87722")   # orange — solids (belts)
_PIPE_COLOR  = QColor("#4ab0d9")   # teal   — liquids/gases (pipes)
_TEMP_COLOR  = QColor("#ffffff")   # white dashed — while dragging
_LABEL_BG    = QColor(0, 0, 0, 160)

# Bezier control-point horizontal offset
_CTRL_OFFSET = 100

class ConnectionLabel(QGraphicsItem):
    """
    A text label with a semi-transparent 'pill' background for better readability.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setZValue(20)
        self.text1 = ""
        self.color1 = QColor("#ffffff")
        self.text2 = ""
        self.color2 = QColor("#ffffff")
        self._text_rect = QRectF(0, 0, 0, 0)
        self._font = QFont("Segoe UI", 8)
        self._font.setPixelSize(8)
        self._font.setBold(True)
        
    def set_data(self, t1: str, c1: QColor, t2: str, c2: QColor):
        changed = False
        if t1 != self.text1 or t2 != self.text2:
            changed = True
        self.text1 = t1
        self.color1 = c1 or QColor("#ffffff")
        self.text2 = t2
        self.color2 = c2 or QColor("#ffffff")
        
        if changed:
            self.prepareGeometryChange()
            from PySide6.QtGui import QFontMetricsF
            fmt = QFontMetricsF(self._font)
            w1 = fmt.horizontalAdvance(self.text1) if self.text1 else 0
            w2 = fmt.horizontalAdvance(" " + self.text2) if self.text2 else 0
            h = fmt.height()
            
            width = max(0.1, w1 + w2)
            height = max(0.1, h)
            self._text_rect = QRectF(0, 0, width, height)
            self.update()

    def boundingRect(self):
        if not self.text1 and not self.text2:
            return QRectF()
        r = self._text_rect
        return QRectF(r.x() - 6, r.y() - 2, r.width() + 12, r.height() + 4)

    def paint(self, painter, option, widget=None):
        if not self.text1 and not self.text2:
            return
            
        painter.setRenderHint(QPainter.Antialiasing)
        # ── Draw Background Pill ──
        rect = self.boundingRect()
        painter.setBrush(QBrush(QColor(0, 0, 0, 190))) # Dark semi-transparent
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1)) # Subtle border
        painter.drawRoundedRect(rect, 8, 8)
        
        # ── Draw Text ──
        painter.setFont(self._font)
        
        from PySide6.QtGui import QFontMetricsF
        fmt = QFontMetricsF(self._font)
        
        x = 0
        y = fmt.ascent()
        
        if self.text1:
            painter.setPen(QPen(self.color1))
            painter.drawText(QPointF(x, y), self.text1)
            x += fmt.horizontalAdvance(self.text1)
            
        if self.text2:
            x += fmt.horizontalAdvance(" ")
            painter.setPen(QPen(self.color2))
            painter.drawText(QPointF(x, y), self.text2)


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
        self._flow_rate:         float = 0.0
        self._mat_name:          str   = ""
        self._status:            str   = "ok"
        self._mat_type:          str   = "solid"   # "solid" | "liquid" | "gas"
        self._material_mismatch: bool  = False      # source output != target input

        # Original node refs — used when connection is proxied through a collapsed group
        self._original_src_node = src_port.parent_node
        self._original_tgt_node = tgt_port.parent_node

        # Fetch material type for colour
        if material_id is not None:
            self._load_material(material_id)

        # Label text item (child of this item)
        self._label = ConnectionLabel(self)
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
        try:
            p1 = self.src_port.center_scene_pos()
            p2 = self.tgt_port.center_scene_pos()
        except RuntimeError:
            return  # Port's C++ side already deleted

        path = QPainterPath(p1)
        
        style = "rounded"
        if self.scene() and hasattr(self.scene(), "line_style"):
            style = self.scene().line_style
            
        if style == "straight":
            path.lineTo(p2)
        elif style == "orthogonal":
            # Manhattan path with stubs to avoid machine overlap
            STUB = 20.0
            
            def get_stub(p, side):
                if side == "left":   return QPointF(p.x() - STUB, p.y())
                if side == "right":  return QPointF(p.x() + STUB, p.y())
                if side == "top":    return QPointF(p.x(), p.y() - STUB)
                if side == "bottom": return QPointF(p.x(), p.y() + STUB)
                return p
            
            s1 = get_stub(p1, getattr(self.src_port, "side", "right"))
            s2 = get_stub(p2, getattr(self.tgt_port, "side", "left"))
            
            path.lineTo(s1)
            
            # Midpoint-based routing between stubs
            # If ports are on opposite sides (e.g. right -> left), use S-shape
            # If they are perpendicular, use L-shape
            src_side = getattr(self.src_port, "side", "right")
            tgt_side = getattr(self.tgt_port, "side", "left")

            if src_side in ["left", "right"] and tgt_side in ["left", "right"]:
                # Horizontal ports: Step vertically at midpoint
                mid_x = (s1.x() + s2.x()) / 2
                path.lineTo(mid_x, s1.y())
                path.lineTo(mid_x, s2.y())
            elif src_side in ["top", "bottom"] and tgt_side in ["top", "bottom"]:
                # Vertical ports: Step horizontally at midpoint
                mid_y = (s1.y() + s2.y()) / 2
                path.lineTo(s1.x(), mid_y)
                path.lineTo(s2.x(), mid_y)
            else:
                # Perpendicular: Direct L between stubs
                # If s1 is horizontal, move horizontally then vertically
                if src_side in ["left", "right"]:
                    path.lineTo(s2.x(), s1.y())
                else:
                    path.lineTo(s1.x(), s2.y())

            path.lineTo(s2)
            path.lineTo(p2)
        else:
            # Rounded / Curved (Bezier)
            ctrl1 = QPointF(p1.x() + _CTRL_OFFSET, p1.y())
            ctrl2 = QPointF(p2.x() - _CTRL_OFFSET, p2.y())
            path.cubicTo(ctrl1, ctrl2, p2)
            
        self.prepareGeometryChange()
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
        # Center horizontally, slightly above point
        self._label.setPos(mid.x() - self._label.boundingRect().width() / 2,
                           mid.y() - 12)
        self._update_label()

    def _line_color(self) -> QColor:
        # Status-based coloring as requested:
        # Red: Mismatch | Orange: Deficit | Blue: Surplus | Green: Perfect
        if self._material_mismatch:
            return QColor("#ff1744")   # vivid red — wrong material
        
        if self._status == "deficit":
            return QColor("#ff9800")   # orange — less than needed
        elif self._status == "surplus":
            return QColor("#2196f3")   # blue — excess material
        elif self._status == "ok" and self._flow_rate > 0:
            return QColor("#4caf50")   # green — perfect quantity
        
        # Idle/Default
        return QColor("#555577")

    def _update_label(self) -> None:
        from ui.settings_cache import get_cached_setting
        show_belts = get_cached_setting("show_belts") == "true"
        
        if not show_belts:
            self._label.setVisible(False)
            return

        if self._material_mismatch:
            self._label.set_data(tr('mat_mismatch'), QColor("#ff1744"), "", None)
        elif self._mat_name:
            self._label.set_data(
                self._mat_name, 
                QColor("#ffffff"), 
                f"{self._flow_rate:.1f}{tr('items_min_short')}", 
                QColor("#ffd54f")
            )
        else:
            self._label.set_data("", None, "", None)
        
        if not self._label.text1 and not self._label.text2:
            self._label.setVisible(False)
        else:
            self._label.setVisible(True)

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
        action_del = menu.addAction(tr("delete_conn"))
        chosen = menu.exec(event.screenPos())
        if chosen == action_del:
            scene = self.scene()
            self._delete_self()
            if scene:
                scene.recalculate()

    def _delete_self(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        try:
            self.src_port.connections = [c for c in self.src_port.connections if c is not self]
        except RuntimeError:
            pass
        try:
            self.tgt_port.connections = [c for c in self.tgt_port.connections if c is not self]
        except RuntimeError:
            pass
        scene.remove_connection(self)

    # ------------------------------------------------------------------
    # Apply engine result
    # ------------------------------------------------------------------
    def apply_result(self, result) -> None:
        self._flow_rate = result.flow_rate
        self._status    = result.status
        if result.material_name:
            self._mat_name = result.material_name
        self.update_path()

    def set_mismatch(self, mismatch: bool) -> None:
        """Called by FactoryScene.recalculate() to flag material incompatibility."""
        if self._material_mismatch != mismatch:
            self._material_mismatch = mismatch
            self.update_path()   # repaint with new colour + label

    # ------------------------------------------------------------------
    # DB serialisation
    # ------------------------------------------------------------------
    def to_db_dict(self) -> dict:
        # Use original node refs (set at creation time) which survive proxy rerouting
        src_node = self._original_src_node
        tgt_node = self._original_tgt_node
        return {
            "id":             self.conn_db_id or id(self),
            "source_node_id": getattr(src_node, "db_id", None) or id(src_node),
            "target_node_id": getattr(tgt_node, "db_id", None) or id(tgt_node),
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
