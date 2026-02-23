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
        self._groups: list = []      # all SubFactoryNode instances

        self.project_id = 1 # updated by MainWindow

        # Drag-to-connect temporary state
        self._temp_line = None        # TempConnectionLine | None
        self._drag_src_port = None    # PortItem | None
        
        # Visual settings
        self.line_style = "rounded"   # "rounded" | "straight"

        # Copy/Paste clipboard — stores 'nodes', 'connections', and 'groups'
        self._clipboard: dict = {"nodes": [], "connections": [], "groups": []}
        
        # Redraw foreground when selection changes
        self.selectionChanged.connect(self.update)

    def set_line_style(self, style: str) -> None:
        """Update the connection line style and refresh all lines."""
        if style not in ("rounded", "straight", "orthogonal"):
            return
        self.line_style = style
        for conn in self._connections:
            conn.update_path()

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
                rid = getattr(src_node, "recipe_id", None)
                if rid is not None:
                    from database.crud import get_recipe_by_id
                    recipe = get_recipe_by_id(rid)
                    if recipe and "materials" in recipe:
                        # Find the first output component
                        outputs = [m for m in recipe["materials"] if not m["is_input"]]
                        if outputs:
                            mat_id = outputs[0]["material_id"]

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

    def remove_group(self, group) -> None:
        """Correctly remove a group from the scene and internal tracking."""
        if group in self._groups:
            self._groups.remove(group)
        self.removeItem(group)

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

    def drawForeground(self, painter, rect):
        """Draw a dashed bounding box around multiple selected items."""
        super().drawForeground(painter, rect)
        
        from ui.machine_node import MachineNode
        from ui.sub_factory_node import SubFactoryNode
        
        # Filter selected items that are still in a scene
        selected = [i for i in self.selectedItems() if i.scene() and isinstance(i, (MachineNode, SubFactoryNode))]
        if len(selected) >= 2:
            # Calculate total bounding box in scene coords
            rects = [s.sceneBoundingRect() for s in selected]
            if not rects: return
            
            min_x = min(r.left() for r in rects)
            min_y = min(r.top() for r in rects)
            max_x = max(r.right() for r in rects)
            max_y = max(r.bottom() for r in rects)
            
            total_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y).adjusted(-10, -10, 10, 10)
            
            painter.setPen(QPen(QColor("#ff9a00"), 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(total_rect)

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
            lookup_id = node.db_id or id(node)
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
            src_rid = getattr(src_node, "recipe_id", None)
            tgt_rid = getattr(tgt_node, "recipe_id", None)
            if src_rid and tgt_rid:
                src_r = recipe_map.get(src_rid)
                tgt_r = recipe_map.get(tgt_rid)
                if src_r and tgt_r:
                    # Check if any output of src matches any input of tgt
                    src_outs = {m["material_id"] for m in src_r.get("materials", []) if not m["is_input"]}
                    tgt_ins  = {m["material_id"] for m in tgt_r.get("materials", []) if m["is_input"]}
                    mismatch = len(src_outs.intersection(tgt_ins)) == 0
            conn.set_mismatch(mismatch)

    # ------------------------------------------------------------------
    # Grouping Logic
    # ------------------------------------------------------------------
    def group_selection(self) -> None:
        """Encapsulate selected MachineNodes into a new SubFactoryNode."""
        from ui.machine_node import MachineNode
        from ui.sub_factory_node import SubFactoryNode
        from database.crud import add_group, set_node_group
        
        selected = [i for i in self.selectedItems() if isinstance(i, MachineNode)]
        if len(selected) < 2:
            return
            
        # Calculate bounding box for initial placement
        rects = [m.sceneBoundingRect() for m in selected]
        min_x = min(r.left() for r in rects)
        min_y = min(r.top() for r in rects)
        max_x = max(r.right() for r in rects)
        max_y = max(r.bottom() for r in rects)
        cx, cy = (min_x + max_x)/2, (min_y + max_y)/2
        
        group_id = add_group(self.project_id, "New Group", cx, cy)
        
        for n in selected:
            n.group_id = group_id
            set_node_group(n.db_id, group_id)
            
        group_data = {
            "id": group_id,
            "name": "New Group",
            "pos_x": cx,
            "pos_y": cy,
            "is_collapsed": 0
        }
        sub_node = SubFactoryNode(group_data, self, selected)
        self.addItem(sub_node)
        self._groups.append(sub_node)
        
        self.clearSelection()
        sub_node.setSelected(True)
        self.recalculate()

    # ------------------------------------------------------------------
    # Copy / Paste Logic
    # ------------------------------------------------------------------
    def _copy_selection(self) -> None:
        """Serialize selected nodes AND their internal connections into the clipboard."""
        from ui.machine_node import MachineNode
        from ui.connection_line import ConnectionLine
        
        self._clipboard = {"nodes": [], "connections": [], "groups": []}
        selected_nodes = []
        
        # Mapping for groups
        from ui.sub_factory_node import SubFactoryNode
        
        # 1. Collect nodes
        for item in self.selectedItems():
            if isinstance(item, MachineNode):
                selected_nodes.append(item)
                self._clipboard["nodes"].append({
                    "id": id(item),  # Internal ref for connection mapping
                    "machine_data": item.machine_data,
                    "recipe_id": item.recipe_id,
                    "clock_speed": item._clock_speed,
                    "pos": item.pos()
                })
            elif isinstance(item, SubFactoryNode):
                self._clipboard["groups"].append({
                    "name": item.name,
                    "is_collapsed": item.is_collapsed,
                    "member_ids": [id(m) for m in item.members],
                    "pos": item.pos()
                })
        
        # 2. Collect connections where BOTH ends are in the selection
        node_ids = {id(n) for n in selected_nodes}
        for item in self.selectedItems():
            if isinstance(item, ConnectionLine):
                src_node = item.src_port.parent_node
                tgt_node = item.tgt_port.parent_node
                if id(src_node) in node_ids and id(tgt_node) in node_ids:
                    self._clipboard["connections"].append({
                        "src_node_id": id(src_node),
                        "tgt_node_id": id(tgt_node),
                        "src_port_idx": item.src_port.index,
                        "tgt_port_idx": item.tgt_port.index,
                        "material_id": item.material_id
                    })
        # print(f"[CLIPBOARD] Copied {len(self._clipboard['nodes'])} nodes and {len(self._clipboard['connections'])} conns.")

    def _paste_selection(self) -> None:
        """Instantiate nodes and connections from the clipboard."""
        if not self._clipboard["nodes"]:
            return

        from ui.machine_node import MachineNode
        from ui.connection_line import ConnectionLine
        
        # Clear current selection so we select the new ones
        self.clearSelection()

        offset = QPointF(32, 32)
        old_to_new_node = {} # Mapping old internal ID -> new MachineNode instance

        # 1. Paste Nodes
        for data in self._clipboard["nodes"]:
            new_pos = data["pos"] + offset
            node = MachineNode(
                data["machine_data"], 
                new_pos, 
                self,
                recipe_id=data["recipe_id"],
                clock_speed=data["clock_speed"]
            )
            self.add_machine_node(node)
            node.setSelected(True)
            
            # Record for connection mapping
            old_to_new_node[data["id"]] = node
            # Update stored pos for consecutive pastes
            data["pos"] = new_pos

        # 2. Paste Connections between the new nodes
        for cdata in self._clipboard["connections"]:
            src_clone = old_to_new_node.get(cdata["src_node_id"])
            tgt_clone = old_to_new_node.get(cdata["tgt_node_id"])
            
            if src_clone and tgt_clone:
                s_idx = cdata["src_port_idx"]
                t_idx = cdata["tgt_port_idx"]
                
                # Bounds check
                if s_idx < len(src_clone.output_ports) and t_idx < len(tgt_clone.input_ports):
                    src_port = src_clone.output_ports[s_idx]
                    tgt_port = tgt_clone.input_ports[t_idx]
                    
                    line = ConnectionLine(
                        src_port, tgt_port,
                        material_id=cdata["material_id"]
                    )
                    self.add_connection(line)
                    src_port.connections.append(line)
                    tgt_port.connections.append(line)
                    line.setSelected(True)

        # 3. Paste/Reconstruct Groups
        from ui.sub_factory_node import SubFactoryNode
        from database.crud import add_group, set_node_group
        
        for gdata in self._clipboard.get("groups", []):
            new_pos = gdata["pos"] + offset
            
            # Find new machine instances that correspond to old member IDs
            new_members = []
            for m_id in gdata["member_ids"]:
                if m_id in old_to_new_node:
                    new_members.append(old_to_new_node[m_id])
            
            if new_members:
                # Add to DB
                gid = add_group(self.project_id, gdata["name"], new_pos.x(), new_pos.y())
                for m in new_members:
                    m.group_id = gid
                    set_node_group(m.db_id, gid)
                
                # Create visual group
                sub_node = SubFactoryNode({
                    "id": gid,
                    "name": gdata["name"],
                    "pos_x": new_pos.x(),
                    "pos_y": new_pos.y(),
                    "is_collapsed": gdata["is_collapsed"]
                }, self, new_members)
                self.addItem(sub_node)
                self._groups.append(sub_node)
                sub_node.setSelected(True)
                
                if gdata["is_collapsed"]:
                    sub_node._create_proxy_ports()
            
            gdata["pos"] = new_pos

        self.recalculate()


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
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
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
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_active = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Keyboard: Delete / Backspace removes all selected items
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        ctrl = bool(event.modifiers() & Qt.ControlModifier)

        # Ctrl+C: Copy
        if ctrl and event.key() == Qt.Key_C:
            self.scene()._copy_selection()
            event.accept()
            return

        # Ctrl+V: Paste
        if ctrl and event.key() == Qt.Key_V:
            self.scene()._paste_selection()
            event.accept()
            return

        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            scene = self.scene()
            # Collect selected items that support deletion
            from ui.machine_node import MachineNode
            from ui.sub_factory_node import SubFactoryNode
            from ui.connection_line import ConnectionLine
            
            selected_items = scene.selectedItems()
            
            # 1. Delete connections first
            for item in list(selected_items):
                if isinstance(item, ConnectionLine):
                    item._delete_self()
            
            # 2. Delete nodes (Machines and Groups)
            for item in list(selected_items):
                if isinstance(item, (MachineNode, SubFactoryNode)):
                    item._delete_self()
            
            event.accept()
        else:
            super().keyPressEvent(event)
    def contextMenuEvent(self, event) -> None:
        from ui.machine_node import MachineNode
        from ui.sub_factory_node import SubFactoryNode
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QPainterPath
        
        pos = event.pos()
        scene_pos = self.mapToScene(pos)
        item = self.itemAt(pos)
        
        menu = QMenu(self)
        
        # If right-clicking selection or nodes
        selected = [i for i in self.scene().selectedItems() if isinstance(i, MachineNode)]
        
        if len(selected) >= 2:
            act_group = QAction("📦 Group Selected Nodes", self)
            act_group.triggered.connect(self.scene().group_selection)
            menu.addAction(act_group)
            menu.addSeparator()

        if item:
            if isinstance(item, SubFactoryNode):
                # SubFactoryNode has its own context menu logic, but we can add more here
                pass
            
            # Global actions
            act_del = QAction("❌ Delete", self)
            act_del.setShortcut("Del")
            # Reuse logic from keyPressEvent — use static list to avoid mutation issues
            def _delete():
                items = list(self.scene().selectedItems())
                for i in items:
                    if i.scene() and hasattr(i, "_delete_self"): 
                        i._delete_self()
            act_del.triggered.connect(_delete)
            menu.addAction(act_del)

        if menu.actions():
            menu.exec(event.globalPos())
        else:
            super().contextMenuEvent(event)
