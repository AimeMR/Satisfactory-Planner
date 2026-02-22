"""
ui/machine_node.py
Phase 3 — Visual machine node on the canvas.

MachineNode is a fully custom QGraphicsItem that draws itself:
  • Rounded-rect body coloured by machine type
  • Machine name (bold header)
  • Recipe combo-box (embedded via QGraphicsProxyWidget)
  • Velocity / rate label
  • Input ports (left edge) and output ports (right edge)
  • Drag-to-move with auto-refresh of attached ConnectionLines
  • Right-click context: Delete, Set Clock Speed
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsProxyWidget, QComboBox,
    QMenu, QInputDialog,
)
from PySide6.QtCore    import Qt, QRectF, QPointF
from PySide6.QtGui     import (
    QPainter, QPen, QBrush, QColor, QFont,
    QFontMetrics, QLinearGradient,
)

from ui.port_item import PortItem


# ---------------------------------------------------------------------------
# Per-machine colour palette  (Satisfactory amber/dark theme)
# ---------------------------------------------------------------------------
_MACHINE_COLORS: dict[str, str] = {
    "Smelter":          "#7a3e00",
    "Foundry":          "#6b3520",
    "Constructor":      "#1a4a1a",
    "Assembler":        "#1a3a5c",
    "Manufacturer":     "#3d1a5c",
    "Refinery":         "#4a2a00",
    "Packager":         "#2a3a20",
    "Miner Mk.1":       "#3a3a3a",
    "Miner Mk.2":       "#2a4a2a",
    "Miner Mk.3":       "#1a6a1a",
    "Water Extractor":  "#003a5c",
    "Oil Extractor":    "#3a1a00",
}
_DEFAULT_COLOR    = "#2a2a4a"
_HEADER_ALPHA     = 200          # header strip alpha
_BODY_ALPHA       = 180

NODE_W = 230
NODE_H = 120
CORNER = 10


class MachineNode(QGraphicsItem):
    """
    One machine instance placed on the canvas.

    Args:
        machine_data:  Dict from DB (id, name, inputs_allowed, outputs_allowed, …)
        pos:           Initial scene position (QPointF).
        scene:         The FactoryScene — used for recalculate after recipe change.
        db_id:         Existing DB id (if loading from DB). None = not yet persisted.
        recipe_id:     Pre-selected recipe DB id (when loading).
        clock_speed:   Overclock multiplier (0.01–2.5).
    """

    def __init__(
        self,
        machine_data: dict,
        pos: QPointF,
        scene,
        db_id: int | None = None,
        recipe_id: int | None = None,
        clock_speed: float = 1.0,
    ):
        super().__init__()
        self.machine_data       = machine_data
        self.node_db_id         = db_id
        self.current_recipe_id  = recipe_id
        self.clock_speed        = clock_speed

        # Runtime production result (filled by apply_result())
        self._output_rate: float = 0.0
        self._input_rate:  float = 0.0
        self._status: str        = "no_recipe"

        self.setPos(pos)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(1)

        # Colours
        base = _MACHINE_COLORS.get(machine_data["name"], _DEFAULT_COLOR)
        self._color_base   = QColor(base)
        self._color_header = QColor(base).darker(130)

        # Ports
        self.input_ports:  list[PortItem] = []
        self.output_ports: list[PortItem] = []
        self._build_ports()

        # Recipe combo (embedded widget)
        self._proxy: QGraphicsProxyWidget | None = None
        self._combo: QComboBox | None = None
        self._build_combo(scene)

    # ------------------------------------------------------------------
    # Port construction
    # ------------------------------------------------------------------
    def _build_ports(self) -> None:
        n_in  = self.machine_data.get("inputs_allowed",  1)
        n_out = self.machine_data.get("outputs_allowed", 1)

        self.input_ports  = self._make_ports("in",  n_in,  x=0)
        self.output_ports = self._make_ports("out", n_out, x=NODE_W)

    def _make_ports(self, ptype: str, count: int, x: float) -> list[PortItem]:
        ports = []
        if count == 0:
            return ports
        spacing = NODE_H / (count + 1)
        for i in range(count):
            y = spacing * (i + 1)
            port = PortItem(ptype, self, self)
            port.setPos(x, y)
            ports.append(port)
        return ports

    # ------------------------------------------------------------------
    # Recipe combo
    # ------------------------------------------------------------------
    def _build_combo(self, scene) -> None:
        from database.crud import get_recipes_for_machine
        recipes = get_recipes_for_machine(self.machine_data["id"])
        if not recipes:
            return

        combo = QComboBox()
        combo.addItem("— select recipe —", None)
        for r in recipes:
            combo.addItem(r["name"], r["id"])
            if r["id"] == self.current_recipe_id:
                combo.setCurrentIndex(combo.count() - 1)

        combo.setStyleSheet("""
            QComboBox {
                background: #1a1a2e;
                color: #eaeaea;
                border: 1px solid #4a4a8a;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background: #16213e;
                color: #eaeaea;
                selection-background-color: #0f3460;
            }
        """)
        combo.currentIndexChanged.connect(self._on_recipe_changed)

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(combo)
        proxy.setPos(10, 52)
        proxy.resize(NODE_W - 20, 28)

        self._combo = combo
        self._proxy = proxy

    def _on_recipe_changed(self, index: int) -> None:
        if self._combo is None:
            return
        self.current_recipe_id = self._combo.currentData()
        # Trigger engine recalc through the scene
        scene = self.scene()
        if scene and hasattr(scene, "recalculate"):
            scene.recalculate()

    # ------------------------------------------------------------------
    # itemChange — auto-update connections on move
    # ------------------------------------------------------------------
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_path()
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Bounding rect (required by Qt)
    # ------------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, NODE_W + 4, NODE_H + 4)   # +2 for selection outline

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0, 0, NODE_W, NODE_H)

        # ── Body gradient ──────────────────────────────────────────────
        grad = QLinearGradient(0, 0, 0, NODE_H)
        c1 = QColor(self._color_base); c1.setAlpha(_BODY_ALPHA)
        c2 = QColor(self._color_base).darker(160); c2.setAlpha(_BODY_ALPHA)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.setBrush(QBrush(grad))

        # Border colour reflects production status
        border_color = {
            "ok":        QColor("#4caf50"),
            "deficit":   QColor("#f44336"),
            "surplus":   QColor("#ff9800"),
            "no_recipe": QColor("#555577"),
        }.get(self._status, QColor("#555577"))

        pen_width = 2.5 if self.isSelected() else 1.5
        painter.setPen(QPen(border_color, pen_width))
        painter.drawRoundedRect(rect, CORNER, CORNER)

        # ── Header strip ───────────────────────────────────────────────
        header_rect = QRectF(0, 0, NODE_W, 36)
        hc = QColor(self._color_header); hc.setAlpha(_HEADER_ALPHA)
        painter.setBrush(QBrush(hc))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(header_rect, CORNER, CORNER)
        # Fill bottom corners of header (so body joins cleanly)
        painter.drawRect(QRectF(0, 26, NODE_W, 10))

        # ── Machine name ───────────────────────────────────────────────
        painter.setPen(QPen(QColor("#ffffff")))
        name_font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(name_font)
        painter.drawText(QRectF(14, 6, NODE_W - 28, 24),
                         Qt.AlignVCenter | Qt.AlignLeft,
                         self.machine_data["name"])

        # ── Rate label (below combo) ────────────────────────────────────
        if self._status != "no_recipe":
            rate_font = QFont("Segoe UI", 9)
            painter.setFont(rate_font)
            rate_color = QColor("#aaffaa") if self._status == "ok" else QColor("#ffaaaa")
            painter.setPen(QPen(rate_color))
            label = f"{self._output_rate:.1f} items/min"
            painter.drawText(QRectF(14, 86, NODE_W - 28, 20),
                             Qt.AlignVCenter | Qt.AlignLeft, label)

        # ── Port labels ────────────────────────────────────────────────
        port_font = QFont("Segoe UI", 8)
        painter.setFont(port_font)
        for port in self.input_ports:
            painter.setPen(QPen(QColor("#4a90d9")))
            painter.drawText(QRectF(8, port.pos().y() - 8, 40, 16),
                             Qt.AlignVCenter | Qt.AlignLeft, "IN")
        for port in self.output_ports:
            painter.setPen(QPen(QColor("#e87722")))
            painter.drawText(QRectF(NODE_W - 48, port.pos().y() - 8, 40, 16),
                             Qt.AlignVCenter | Qt.AlignRight, "OUT")

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#16213e; color:#eaeaea; border:1px solid #4a4a8a; }
            QMenu::item:selected { background:#0f3460; }
        """)
        action_delete = menu.addAction("Delete Node")
        action_clock  = menu.addAction("Set Clock Speed…")

        chosen = menu.exec(event.screenPos())

        if chosen == action_delete:
            self._delete_self()
        elif chosen == action_clock:
            self._change_clock_speed()

    def _delete_self(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        # Remove all attached connections first
        for port in self.input_ports + self.output_ports:
            for conn in list(port.connections):
                scene.remove_connection(conn)
        scene.remove_machine_node(self)
        scene.recalculate()

    def _change_clock_speed(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getDouble(
            None, "Clock Speed",
            "Enter overclock multiplier (0.01 – 2.50):",
            self.clock_speed, 0.01, 2.50, 2
        )
        if ok:
            self.clock_speed = val
            scene = self.scene()
            if scene:
                scene.recalculate()
            self.update()

    # ------------------------------------------------------------------
    # Apply production engine result
    # ------------------------------------------------------------------
    def apply_result(self, result) -> None:
        """Called by FactoryScene.recalculate() with a NodeResult object."""
        self._output_rate = result.output_rate
        self._input_rate  = result.input_rate_required
        self._status      = result.status
        self.update()   # trigger repaint

    # ------------------------------------------------------------------
    # DB serialisation helper
    # ------------------------------------------------------------------
    def to_db_dict(self) -> dict:
        return {
            "id":          self.node_db_id or id(self),
            "machine_id":  self.machine_data["id"],
            "recipe_id":   self.current_recipe_id,
            "pos_x":       self.pos().x(),
            "pos_y":       self.pos().y(),
            "clock_speed": self.clock_speed,
        }
