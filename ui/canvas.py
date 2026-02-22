"""
ui/canvas.py
Phase 2 — The infinite grid workspace.

FactoryScene  – QGraphicsScene holding all nodes & connections.
FactoryView   – QGraphicsView with dot-grid background, zoom, and pan.
"""

from __future__ import annotations
import math
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
from PySide6.QtCore    import Qt, QPointF, QRectF
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QBrush, QWheelEvent,
    QMouseEvent, QKeyEvent,
)


# ---------------------------------------------------------------------------
# Colour palette (Satisfactory dark-amber theme)
# ---------------------------------------------------------------------------
BG_COLOR   = QColor("#1a1a2e")   # deep navy
GRID_COLOR = QColor("#44446a")   # more intense grid dots


class FactoryScene(QGraphicsScene):
    """
    Central scene.  All MachineNodes and ConnectionLines live here.
    The scene is logically infinite; the view clips to the viewport.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Give the scene a large bounding rect so scroll-bars behave sensibly
        self.setSceneRect(-10_000, -10_000, 20_000, 20_000)
        self.setBackgroundBrush(QBrush(BG_COLOR))

        # Runtime state shared across nodes/lines
        self._machines: list  = []   # all MachineNode instances
        self._connections: list = []  # all ConnectionLine instances

        # Drag-to-connect temporary state
        self._temp_line = None        # TempConnectionLine | None
        self._drag_src_port = None    # PortItem | None

    # ------------------------------------------------------------------
    # Drag-to-connect (initiated by PortItem.mousePressEvent)
    # ------------------------------------------------------------------
    def _start_connection_drag(self, src_port, scene_pos: "QPointF") -> None:
        from ui.connection_line import TempConnectionLine
        self._drag_src_port = src_port
        self._temp_line = TempConnectionLine()
        self.addItem(self._temp_line)
        self._temp_line.update_endpoints(src_port.center_scene_pos(), scene_pos)

    def _update_connection_drag(self, scene_pos: "QPointF") -> None:
        if self._temp_line and self._drag_src_port:
            self._temp_line.update_endpoints(
                self._drag_src_port.center_scene_pos(), scene_pos
            )

    def _end_connection_drag(self, scene_pos: "QPointF") -> None:
        from ui.connection_line import ConnectionLine
        from ui.port_item import PortItem

        try:
            if not (self._temp_line and self._drag_src_port):
                return

            # Find any PortItem under the release position
            target = None
            for item in self.items(scene_pos):
                if isinstance(item, PortItem) and item.port_type == "in":
                    # Cannot connect to own node
                    if item.parent_node is not self._drag_src_port.parent_node:
                        target = item
                        break

            if target is not None:
                # Determine material from output recipe
                src_node = self._drag_src_port.parent_node
                mat_id = None
                if src_node.current_recipe_id is not None:
                    from database.crud import get_recipe_by_id
                    recipe = get_recipe_by_id(src_node.current_recipe_id)
                    if recipe:
                        mat_id = recipe["output_material_id"]

                line = ConnectionLine(
                    self._drag_src_port, target,
                    material_id=mat_id,
                )
                self.add_connection(line)
                self._drag_src_port.connections.append(line)
                target.connections.append(line)
                self.recalculate()
        finally:
            # Always clean up temp line
            if self._temp_line:
                self.removeItem(self._temp_line)
                self._temp_line = None
            self._drag_src_port = None

    # ------------------------------------------------------------------
    # Accessors used by nodes / lines
    # ------------------------------------------------------------------
    def add_machine_node(self, node) -> None:
        self._machines.append(node)
        self.addItem(node)

    def remove_machine_node(self, node) -> None:
        if node in self._machines:
            self._machines.remove(node)
        self.removeItem(node)

    def add_connection(self, line) -> None:
        self._connections.append(line)
        self.addItem(line)

    def remove_connection(self, line) -> None:
        if line in self._connections:
            self._connections.remove(line)
        self.removeItem(line)

    def all_nodes(self):
        return list(self._machines)

    def all_connections(self):
        return list(self._connections)

    # ------------------------------------------------------------------
    # Scene-level mouse routing for drag-to-connect
    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        if self._drag_src_port is not None:
            self._update_connection_drag(event.scenePos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_src_port is not None:
            self._end_connection_drag(event.scenePos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Engine recalculation (called after any topology change)
    # ------------------------------------------------------------------
    def recalculate(self) -> None:
        """Run the production engine and push results to every node/line."""
        from engine.graph import build_graph, calculate_production
        from database.crud import (
            get_all_recipes, get_all_machines, get_all_materials,
            get_recipe_by_id,
        )

        placed = [n.to_db_dict() for n in self._machines]
        conns  = [c.to_db_dict() for c in self._connections]

        recipes   = get_all_recipes()
        machines  = get_all_machines()
        materials = get_all_materials()

        recipe_map = {r["id"]: r for r in recipes}

        graph  = build_graph(placed, conns)
        result = calculate_production(graph, recipes, machines, materials)

        for node in self._machines:
            lookup_id = node.node_db_id or id(node)
            nr = result.nodes.get(lookup_id)
            if nr:
                node.apply_result(nr)

        for conn in self._connections:
            # 1. Push flow/status from production engine
            lookup_id = conn.conn_db_id or id(conn)
            cr = result.connections.get(lookup_id)
            if cr:
                conn.apply_result(cr)

            # 2. Check material mismatch: source output ≠ target input
            src_node = conn.src_port.parent_node
            tgt_node = conn.tgt_port.parent_node
            mismatch = False
            src_rid = src_node.current_recipe_id
            tgt_rid = tgt_node.current_recipe_id
            if src_rid and tgt_rid:
                src_r = recipe_map.get(src_rid)
                tgt_r = recipe_map.get(tgt_rid)
                if src_r and tgt_r:
                    mismatch = (src_r["output_material_id"] != tgt_r["input_material_id"])
            conn.set_mismatch(mismatch)


# ---------------------------------------------------------------------------
# FactoryView
# ---------------------------------------------------------------------------

class FactoryView(QGraphicsView):
    """
    Viewport with:
      • dot-grid background
      • Ctrl+wheel (or plain wheel) zoom
      • middle-button drag to pan
      • right-click context for future use
    """

    _ZOOM_STEP  = 1.15
    _ZOOM_MIN   = 0.10
    _ZOOM_MAX   = 4.00
    _GRID_SIZE  = 32   # pixels between grid dots (scene-space)

    def __init__(self, scene: FactoryScene, parent=None):
        super().__init__(scene, parent)
        self._zoom = 1.0
        self._pan_active = False
        self._pan_start  = QPointF()

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.RubberBandDrag)  # left-drag on empty = select rect
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(self.Shape.NoFrame)

    # ------------------------------------------------------------------
    # Background: dot grid
    # ------------------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)

        gs = self._GRID_SIZE
        left   = int(math.floor(rect.left()   / gs) * gs)
        top    = int(math.floor(rect.top()    / gs) * gs)
        right  = int(math.ceil(rect.right()   / gs) * gs)
        bottom = int(math.ceil(rect.bottom()  / gs) * gs)

        painter.setPen(QPen(GRID_COLOR, 1.8))

        x = left
        while x <= right:
            y = top
            while y <= bottom:
                painter.drawPoint(x, y)
                y += gs
            x += gs

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:
        # Only block zoom if the mouse is over an OPEN dropdown list.
        # If it's closed, we should zoom normally.
        item = self.itemAt(event.position().toPoint())
        from PySide6.QtWidgets import QGraphicsProxyWidget, QComboBox
        
        target_combo = None
        if isinstance(item, QGraphicsProxyWidget):
            widget = item.widget()
            if isinstance(widget, QComboBox):
                target_combo = widget
        elif item and item.parentItem() and isinstance(item.parentItem(), QGraphicsProxyWidget):
            widget = item.parentItem().widget()
            if isinstance(widget, QComboBox):
                target_combo = widget

        if target_combo and target_combo.view().isVisible():
            # Dropdown is open, let standard scroll handle the list
            super().wheelEvent(event)
            return

        # Zoom on Ctrl+wheel OR plain wheel (no modifier)
        delta = event.angleDelta().y()
        if delta > 0:
            factor = self._ZOOM_STEP
        else:
            factor = 1.0 / self._ZOOM_STEP

        new_zoom = self._zoom * factor
        if self._ZOOM_MIN <= new_zoom <= self._ZOOM_MAX:
            self._zoom = new_zoom
            self.scale(factor, factor)

    # ------------------------------------------------------------------
    # Pan (middle mouse button)
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._pan_active = True
            self._pan_start  = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_active:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._pan_active = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Keyboard: Delete / Backspace removes all selected items
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            scene = self.scene()
            # Collect selected nodes and connections (copy list — deletion mutates it)
            from ui.machine_node import MachineNode
            from ui.connection_line import ConnectionLine
            selected_nodes = [
                item for item in scene.selectedItems()
                if isinstance(item, MachineNode)
            ]
            selected_conns = [
                item for item in scene.selectedItems()
                if isinstance(item, ConnectionLine)
            ]
            # Delete connections first, then nodes
            for conn in selected_conns:
                conn._delete_self()
            for node in selected_nodes:
                node._delete_self()
            event.accept()
        else:
            super().keyPressEvent(event)
