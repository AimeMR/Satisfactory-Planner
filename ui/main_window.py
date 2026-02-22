"""
ui/main_window.py
Phase 2 — Application shell: sidebar + canvas + status bar.
"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QSplitter,
    QStatusBar, QFrame,
)
from PySide6.QtCore    import Qt, QPointF
from PySide6.QtGui     import QColor, QFont, QIcon

from ui.canvas import FactoryScene, FactoryView


# Satisfactory-style palette
_SIDEBAR_BG   = "#16213e"
_SIDEBAR_ITEM = "#0f3460"
_ACCENT       = "#e94560"
_TEXT         = "#eaeaea"
_BORDER       = "#2a2a4a"


class MainWindow(QMainWindow):
    """
    Root application window.

    Layout:
        ┌──────────┬────────────────────────────────┐
        │ Sidebar  │        FactoryView (canvas)     │
        │ (machine │                                  │
        │  palette)│                                  │
        └──────────┴────────────────────────────────┘
        │              Status Bar                    │
        └────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Satisfactory Planner")
        self.resize(1400, 900)
        self._apply_global_styles()

        # Scene + view
        self.scene = FactoryScene()
        self.view  = FactoryView(self.scene)

        # Sidebar
        self._sidebar = self._build_sidebar()

        # Splitter: sidebar | canvas
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 1180])
        splitter.setHandleWidth(1)

        self.setCentralWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self._status.setStyleSheet(f"background:{_SIDEBAR_BG}; color:{_TEXT}; font-size:12px;")
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — middle-drag to pan, scroll to zoom, double-click a machine to place")

        # Load any persisted layout from DB
        self._load_layout()

    # ------------------------------------------------------------------
    # Sidebar builder
    # ------------------------------------------------------------------
    def _apply_global_styles(self) -> None:
        """Apply a dark QSS theme to the entire application."""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {_SIDEBAR_BG};
                color: {_TEXT};
                font-family: "Segoe UI";
            }}
            QSplitter::handle {{
                background: {_BORDER};
            }}
            QScrollBar {{ background: {_SIDEBAR_BG}; width: 8px; }}
            QScrollBar::handle {{ background: {_BORDER}; border-radius: 4px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """)

    def _build_sidebar(self) -> QWidget:
        container = QWidget()
        container.setFixedWidth(220)
        container.setStyleSheet(f"""
            QWidget {{ background: {_SIDEBAR_BG}; }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("  MACHINES")
        header.setStyleSheet(f"""
            background: {_ACCENT};
            color: white;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 2px;
            padding: 10px 0;
        """)
        layout.addWidget(header)

        # Machine list
        self._machine_list = QListWidget()
        self._machine_list.setStyleSheet(f"""
            QListWidget {{
                background: {_SIDEBAR_BG};
                border: none;
                outline: none;
                color: {_TEXT};
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 14px;
                border-bottom: 1px solid {_BORDER};
            }}
            QListWidget::item:selected {{
                background: {_SIDEBAR_ITEM};
                color: white;
            }}
            QListWidget::item:hover {{
                background: #1a2a5e;
            }}
        """)
        self._machine_list.itemDoubleClicked.connect(self._on_machine_dblclick)
        layout.addWidget(self._machine_list)

        # Populate
        self._populate_machine_list()

        # Footer hint
        hint = QLabel("Double-click to place")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: #888; font-size: 11px; padding: 8px;")
        layout.addWidget(hint)

        return container

    def _populate_machine_list(self) -> None:
        """Load machine types from DB and add to the sidebar list."""
        from database.crud import get_all_machines
        self._machines_data: dict[str, dict] = {}
        for m in get_all_machines():
            item = QListWidgetItem(f"  {m['name']}")
            item.setData(Qt.UserRole, m)
            self._machine_list.addItem(item)
            self._machines_data[m["name"]] = m

    # ------------------------------------------------------------------
    # Double-click: place a new node at canvas centre
    # ------------------------------------------------------------------
    def _on_machine_dblclick(self, item: QListWidgetItem) -> None:
        from ui.machine_node import MachineNode
        machine_data = item.data(Qt.UserRole)

        # Place node at the centre of the current view
        view_centre = self.view.mapToScene(
            self.view.viewport().rect().center()
        )
        # Small random offset so multiple placements don't exactly overlap
        import random
        offset = QPointF(random.randint(-40, 40), random.randint(-40, 40))

        node = MachineNode(machine_data, view_centre + offset, self.scene)
        self.scene.add_machine_node(node)
        self.scene.recalculate()
        self._update_status()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _update_status(self) -> None:
        n = len(self.scene.all_nodes())
        c = len(self.scene.all_connections())
        self._status.showMessage(
            f"Nodes: {n}   Connections: {c}   "
            "| middle-drag: pan   scroll: zoom   "
            "drag port→port: connect   right-click: delete"
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_layout(self) -> None:
        """Reload placed nodes and connections saved in the DB."""
        from database.crud import (
            get_all_placed_nodes, get_all_connections,
            get_machine_by_id, get_recipe_by_id, get_material_by_id,
        )
        from ui.machine_node import MachineNode
        from ui.connection_line import ConnectionLine

        node_map: dict[int, object] = {}  # db_id → MachineNode

        for row in get_all_placed_nodes():
            machine = get_machine_by_id(row["machine_id"])
            if not machine:
                continue
            pos = QPointF(row["pos_x"], row["pos_y"])
            node = MachineNode(machine, pos, self.scene,
                               db_id=row["id"],
                               recipe_id=row.get("recipe_id"),
                               clock_speed=row.get("clock_speed", 1.0))
            self.scene.add_machine_node(node)
            node_map[row["id"]] = node

        for row in get_all_connections():
            src_node = node_map.get(row["source_node_id"])
            tgt_node = node_map.get(row["target_node_id"])
            if src_node and tgt_node:
                # Find the matching ports
                src_port = src_node.output_ports[0] if src_node.output_ports else None
                tgt_port = tgt_node.input_ports[0]  if tgt_node.input_ports  else None
                if src_port and tgt_port:
                    line = ConnectionLine(src_port, tgt_port,
                                         db_id=row["id"],
                                         material_id=row.get("material_id"))
                    self.scene.add_connection(line)
                    src_port.connections.append(line)
                    tgt_port.connections.append(line)

        if node_map:
            self.scene.recalculate()
        self._update_status()

    def closeEvent(self, event) -> None:
        """Persist the current layout to DB on close."""
        self._save_layout()
        event.accept()

    def _save_layout(self) -> None:
        """Write all placed node positions and connections back to DB."""
        from database.crud import (
            get_all_placed_nodes, delete_placed_node, delete_connection,
            add_placed_node, add_connection, update_placed_node,
        )
        # Simple strategy: clear and re-insert
        for row in get_all_placed_nodes():
            delete_placed_node(row["id"])

        id_map: dict[int, int] = {}  # old_obj_id → new_db_id
        for node in self.scene.all_nodes():
            new_id = add_placed_node(
                machine_id=node.machine_data["id"],
                recipe_id=node.current_recipe_id,
                pos_x=node.pos().x(),
                pos_y=node.pos().y(),
                clock_speed=node.clock_speed,
            )
            id_map[id(node)] = new_id
            node.node_db_id = new_id

        for conn in self.scene.all_connections():
            src_node = conn.src_port.parent_node
            tgt_node = conn.tgt_port.parent_node
            src_id = id_map.get(id(src_node))
            tgt_id = id_map.get(id(tgt_node))
            if src_id and tgt_id:
                new_id = add_connection(
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    material_id=conn.material_id,
                )
                conn.conn_db_id = new_id
