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

from ui.i18n import tr

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
    "Conveyor Splitter": "#ff6d00", # Vibrant Orange
    "Conveyor Merger":   "#00e5ff", # Vibrant Cyan/Teal
}
_DEFAULT_COLOR    = "#2a2a4a"
_HEADER_ALPHA     = 200          # header strip alpha
_BODY_ALPHA       = 180

# Default dimensions for standard machines
_STD_W = 230
_STD_H = 160
CORNER = 10
# Body starts below the header
_BODY_Y = 36


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
        group_id: int | None = None,
    ):
        super().__init__()
        self.machine_data       = machine_data
        self._m_id              = machine_data["id"] # Store machine_id internally
        self.db_id              = db_id # Renamed from node_db_id
        self.recipe_id          = recipe_id # Renamed from current_recipe_id
        self._clock_speed       = clock_speed # Renamed from clock_speed and made internal
        self.group_id           = group_id # New

        # Dimensions (Logistics are smaller)
        self.is_logistics = "Splitter" in machine_data["name"] or "Merger" in machine_data["name"]
        self.w = 120 if self.is_logistics else _STD_W
        self.h = 120 if self.is_logistics else _STD_H

        # Runtime production result (filled by apply_result())
        self._output_rate: float = 0.0
        self._inputs: list[dict] = []
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
        name = self.machine_data["name"]
        
        if "Splitter" in name:
            # 1 Input (Left: idx 0) -> 3 Outputs (Top: idx 0, Right: idx 1, Bottom: idx 2)
            self.input_ports = [self._make_directional_port("in", QPointF(0, self.h/2), index=0, side="left")]
            self.output_ports = [
                self._make_directional_port("out", QPointF(self.w / 2, 0),      index=0, side="top"),
                self._make_directional_port("out", QPointF(self.w, self.h / 2), index=1, side="right"),
                self._make_directional_port("out", QPointF(self.w / 2, self.h), index=2, side="bottom"),
            ]
        elif "Merger" in name:
            # 3 Inputs (Top: idx 0, Left: idx 1, Bottom: idx 2) -> 1 Output (Right: idx 0)
            self.input_ports = [
                self._make_directional_port("in", QPointF(self.w / 2, 0),      index=0, side="top"),
                self._make_directional_port("in", QPointF(0, self.h / 2),      index=1, side="left"),
                self._make_directional_port("in", QPointF(self.w / 2, self.h), index=2, side="bottom"),
            ]
            self.output_ports = [
                self._make_directional_port("out", QPointF(self.w, self.h / 2), index=0, side="right"),
            ]
        else:
            # Standard machines
            n_in  = self.machine_data.get("inputs_allowed",  1)
            n_out = self.machine_data.get("outputs_allowed", 1)
            self.input_ports  = self._make_standard_ports("in",  n_in,  x=0,      side="left")
            self.output_ports = self._make_standard_ports("out", n_out, x=self.w, side="right")

    def _make_directional_port(self, ptype: str, pos: QPointF, index: int, side: str) -> PortItem:
        port = PortItem(ptype, self, self, index=index, side=side)
        port.setPos(pos)
        return port

    def _make_standard_ports(self, ptype: str, count: int, x: float, side: str) -> list[PortItem]:
        ports = []
        if count == 0:
            return ports
        body_h = self.h - _BODY_Y
        spacing = body_h / (count + 1)
        for i in range(count):
            y = _BODY_Y + spacing * (i + 1)
            port = PortItem(ptype, self, self, index=i, side=side)
            port.setPos(x, y)
            ports.append(port)
        return ports

    # ------------------------------------------------------------------
    # Recipe combo
    # ------------------------------------------------------------------
    def _build_combo(self, scene) -> None:
        # Logistics nodes don't need a recipe combo
        is_logistics = "Splitter" in self.machine_data["name"] or "Merger" in self.machine_data["name"]
        if is_logistics:
            return

        from database.crud import get_recipes_for_machine
        recipes = get_recipes_for_machine(self.machine_data["id"])

        combo = QComboBox()
        # The patch implies self._combo might exist and need clearing,
        # but _build_combo is called during init when _combo is None.
        # Assuming the intent is to clear if this method were re-run,
        # or that self._combo is assigned earlier in a different flow.
        # For initial build, clear() is not strictly necessary on a new QComboBox.
        # However, to faithfully apply the patch, we'll add it, assuming
        # self._combo will be assigned later in this method.
        if self._combo: # Check if it's already assigned, though it shouldn't be here
            self._combo.clear()
        
        combo.addItem(tr("select_recipe"), None)
        for r in recipes:
            combo.addItem(r["name"], r["id"])
            if r["id"] == self.recipe_id: # Changed from current_recipe_id
                combo.setCurrentIndex(combo.count() - 1)

        combo.setStyleSheet("""
            QComboBox {
                background: #1a1a2e;
                color: #eaeaea;
                border: 1px solid #4a4a8a;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
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
        proxy.setPos(10, 44)
        proxy.resize(self.w - 20, 25)
        proxy.setZValue(100)  # Always stay on top for the dropdown

        self._combo = combo
        self._proxy = proxy

    def _on_recipe_changed(self, index: int) -> None:
        if self._combo is None:
            return
        self.recipe_id = self._combo.currentData() # Changed from current_recipe_id
        scene = self.scene()
        if not self.recipe_id: # Changed from current_recipe_id
            # Clear stats immediately if recipe deselected
            self._output_rate = 0.0
            self._inputs = []
            self._status = "no_recipe"
            self.update()
        
        if scene and hasattr(scene, "recalculate"):
            scene.recalculate()

    # ------------------------------------------------------------------
    # itemChange — auto-update connections on move
    # ------------------------------------------------------------------
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for conn in self.input_ports + self.output_ports:
                for c in conn.connections:
                    c.update_path()
            
            # Notify parent group to refresh its bounds
            if self.group_id is not None:
                scene = self.scene()
                if hasattr(scene, "_groups"):
                    # Find the group object
                    for g in scene._groups:
                        if g.group_id == self.group_id:
                            g.refresh_bounds()
                            break
            
            # Update scene if selected (to redraw orange selection box)
            if self.isSelected() and self.scene():
                self.scene().update()
                            
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Bounding rect (required by Qt)
    # ------------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, self.w + 4, self.h + 4)   # +2 for selection outline

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0, 0, self.w, self.h)

        # ── Body gradient ────────────────────────────────────────────────────────
        grad = QLinearGradient(0, 0, 0, self.h)
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

        # ── Header strip ───────────────────────────────────────────────────────────
        header_h = 24 if self.is_logistics else 36
        header_rect = QRectF(0, 0, self.w, header_h)
        hc = QColor(self._color_header); hc.setAlpha(_HEADER_ALPHA)
        painter.setBrush(QBrush(hc))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(header_rect, CORNER, CORNER)
        painter.drawRect(QRectF(0, header_h - 10, self.w, 10))   # fill bottom corners

        # ── Machine name ───────────────────────────────────────────────────────────
        painter.setPen(QPen(QColor("#ffffff")))
        font_size = 9 if self.is_logistics else 10
        name_font = QFont("Segoe UI", font_size, QFont.Bold)
        painter.setFont(name_font)
        painter.drawText(QRectF(10, 0, self.w - 20, header_h),
                         Qt.AlignVCenter | Qt.AlignLeft,
                         self.machine_data["name"].replace("Conveyor ", ""))

        # ── Stats ───────────────────────────────────────────────────────────────
        if self._status != "no_recipe" or self.is_logistics:
            stat_font = QFont("Segoe UI", 9)
            painter.setFont(stat_font)

            y = header_h + 8 if self.is_logistics else 84
            
            from database.crud import get_setting
            show_output = get_setting("show_output", "true") == "true"
            show_power  = get_setting("show_power", "true") == "true"
            show_inputs = get_setting("show_inputs", "true") == "true"

            # Output velocity
            if show_output:
                out_color = QColor("#aaffaa") if self._status == "ok" else QColor("#ffaaaa")
                painter.setPen(QPen(out_color))
                painter.drawText(QRectF(10, y, self.w - 20, 16),
                                 Qt.AlignVCenter | Qt.AlignLeft,
                                 f"OUT: {self._output_rate:.1f}{tr('items_min_short')}")
                y += 16

            # Energy
            if show_power:
                energy_mw = self._calc_energy_mw()
                painter.setPen(QPen(QColor("#ffd54f")))
                painter.drawText(QRectF(10, y, self.w - 20, 16),
                                 Qt.AlignVCenter | Qt.AlignLeft,
                                 f"⚡ {energy_mw:.1f} MW")
                y += 16

            # ── Inputs Section (with separator line) ─────────────────────
            if show_inputs and self._inputs:
                y += 4
                painter.setPen(QPen(QColor("#44446a"), 1))
                painter.drawLine(10, y, self.w - 10, y)
                y += 6
                
                inp_font = QFont("Segoe UI", 8)
                painter.setFont(inp_font)
                painter.setPen(QPen(QColor("#aaddff")))
                for inp in self._inputs:
                    painter.drawText(QRectF(10, y, self.w - 20, 14),
                                     Qt.AlignVCenter | Qt.AlignLeft,
                                     f"► {inp['rate']:.1f} {inp['material']}")
                    y += 14

        # ── Port labels (Hide IN/OUT if logistics to keep it clean) ──────
        if not self.is_logistics:
            port_font = QFont("Segoe UI", 8)
            painter.setFont(port_font)
            for port in self.input_ports:
                painter.setPen(QPen(QColor("#4a90d9")))
                painter.drawText(QRectF(8, port.pos().y() - 8, 40, 16),
                                 Qt.AlignVCenter | Qt.AlignLeft, "IN")
            for port in self.output_ports:
                painter.setPen(QPen(QColor("#e87722")))
                painter.drawText(QRectF(self.w - 48, port.pos().y() - 8, 40, 16),
                                 Qt.AlignVCenter | Qt.AlignRight, "OUT")

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu, QInputDialog
        from PySide6.QtGui import QAction
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background:#16213e; color:#eaeaea; border:1px solid #4a4a8a; }"
            "QMenu::item:selected { background:#0f3460; }"
        )

        # ── Group Actions ──
        if self.group_id is not None:
            # Find the group object
            scene = self.scene()
            group_node = None
            if hasattr(scene, "_groups"):
                for g in scene._groups:
                    if g.group_id == self.group_id:
                        group_node = g
                        break
            
            if group_node:
                group_menu = menu.addMenu("📦 " + group_node.name)
                
                toggle_txt = "Expand" if group_node.is_collapsed else "Collapse"
                act_toggle_grp = group_menu.addAction(toggle_txt)
                act_ungroup_grp = group_menu.addAction("Ungroup")
                
                menu.addSeparator()

        act_clock = menu.addAction(f"🕒 Change Clock Speed ({self._clock_speed*100:.1f}%)")
        act_del   = menu.addAction("🗑 Delete Machine")

        # In Qt, menu.exec expects a QPoint (global screen coordinates)
        # event.screenPos() returns a QPoint in PyQt6/PySide6
        chosen = menu.exec(event.screenPos())

        if self.group_id is not None and group_node:
            if chosen == act_toggle_grp:
                group_node._toggle_state()
                return
            elif chosen == act_ungroup_grp:
                group_node._ungroup()
                return

        if chosen == act_del:
            self._delete_self()
        elif chosen == act_clock:
            self._change_clock_speed()

    def _delete_self(self, recalculate: bool = True) -> None:
        from database.crud import delete_placed_node
        scene = self.scene()
        if scene is None:
            return

        print(f"[DEBUG] Deleting MachineNode {self.db_id} (Group: {self.group_id})")

        # 1. Remove from parent group list if applicable
        if self.group_id is not None:
            if hasattr(scene, "_groups"):
                for g in scene._groups:
                    if g.group_id == self.group_id:
                        if self in g.members:
                            g.members.remove(self)
                        # Avoid refresh_bounds during bulk deletion
                        if hasattr(g, "_is_deleting") and not g._is_deleting:
                            g.refresh_bounds()
                        break

        # 2. Remove all attached connections from scene
        for port in self.input_ports + self.output_ports:
            # list() copy because _delete_self modifies port.connections
            for conn in list(port.connections):
                conn._delete_self()
        
        # 3. Delete from DB
        if self.db_id:
            delete_placed_node(self.db_id)

        # 4. Remove from Scene
        scene.remove_machine_node(self)
        if recalculate:
            scene.recalculate()

    def _change_clock_speed(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getDouble(
            None, tr("set_clock"),
            "Multiplier (0.01 – 2.50):",
            self._clock_speed, 0.01, 2.50, 2 # Changed to _clock_speed
        )
        if ok:
            self._clock_speed = val # Changed to _clock_speed
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
        self._inputs      = result.inputs
        self._status      = result.status
        
        if self._status == "no_recipe":
            self._output_rate = 0.0
            self._inputs = []

        self.update()   # trigger repaint

    def _calc_energy_mw(self) -> float:
        """Energy consumption in MW using Satisfactory's overclocking formula."""
        base = self.machine_data.get("base_power", 0.0)
        # Formula: P = P_base * clock_speed ^ 1.321
        return base * (self._clock_speed ** 1.321) # Changed to _clock_speed

    def to_db_dict(self) -> dict:
        return {
            "id": self.db_id,
            "machine_id": self._m_id,
            "recipe_id": self.recipe_id,
            "group_id": self.group_id,
            "pos_x": self.pos().x(),
            "pos_y": self.pos().y(),
            "clock_speed": self._clock_speed,
        }
