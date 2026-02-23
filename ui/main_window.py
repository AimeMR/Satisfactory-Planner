"""
ui/main_window.py
Phase 2 — Application shell: sidebar + canvas + status bar.
"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLabel, QSplitter,
    QStatusBar, QFrame, QComboBox, QPushButton,
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
        layout_splitter = QSplitter(Qt.Horizontal)
        layout_splitter.addWidget(self._sidebar)
        layout_splitter.addWidget(self.view)
        layout_splitter.setStretchFactor(0, 0)
        layout_splitter.setStretchFactor(1, 1)
        layout_splitter.setSizes([220, 1180])
        layout_splitter.setHandleWidth(1)

        # Toolbar (Top)
        self._toolbar = self._build_toolbar()
        
        # Main vertical layout to hold toolbar + splitter
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._toolbar)
        main_layout.addWidget(layout_splitter)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Status bar
        self._status = QStatusBar()
        self._status.setStyleSheet(f"background:{_SIDEBAR_BG}; color:{_TEXT}; font-size:12px;")
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — right-drag to pan, scroll to zoom, double-click a machine to place")

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

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet(f"""
            QWidget {{ 
                background: {_SIDEBAR_BG}; 
                border-bottom: 1px solid {_BORDER};
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 20, 0)
        layout.setSpacing(15)

        # Sidebar Toggle Button
        self.toggle_btn = QPushButton("☰ SIDEBAR")
        self.toggle_btn.setFixedWidth(100)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 5px;
                color: {_ACCENT};
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:checked {{
                background: {_ACCENT};
                color: {_SIDEBAR_BG};
            }}
            QPushButton:hover {{
                border-color: {_ACCENT};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.toggle_btn)
        
        # Title area
        title = QLabel("SATISFACTORY PLANNER")
        title.setStyleSheet(f"color: {_ACCENT}; font-weight: bold; font-size: 14px; letter-spacing: 1px;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Line Style Dropdown
        style_label = QLabel("LINE STYLE:")
        style_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(style_label)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Rounded (Bezier)", "Straight", "Orthogonal (Manhattan)"])
        self.style_combo.setFixedWidth(180)
        self.style_combo.setStyleSheet(f"""
            QComboBox {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 5px 10px;
                color: white;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {_SIDEBAR_BG};
                selection-background-color: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
            }}
        """)
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)
        
        return bar

    def _on_style_changed(self, index: int) -> None:
        style_map = {0: "rounded", 1: "straight", 2: "orthogonal"}
        style = style_map.get(index, "rounded")
        self.scene.set_line_style(style)
        self._update_status()
        
        # PERSIST SETTING
        from database.crud import set_setting
        set_setting("line_style", style)

    def _toggle_sidebar(self, checked: bool) -> None:
        self._sidebar.setVisible(checked)
        self._status.showMessage(f"Sidebar {'shown' if checked else 'hidden'}", 2000)
        
        # PERSIST SETTING
        from database.crud import set_setting
        set_setting("sidebar_visible", "true" if checked else "false")

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

        # Machine list (Tree)
        self._machine_tree = QTreeWidget()
        self._machine_tree.setHeaderHidden(True)
        self._machine_tree.setIndentation(20)
        self._machine_tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {_SIDEBAR_BG};
                border: none;
                outline: none;
                color: {_TEXT};
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid #222;
            }}
            QTreeWidget::item:selected {{
                background: {_SIDEBAR_ITEM};
                color: white;
            }}
            QTreeWidget::item:hover {{
                background: #1a2a5e;
            }}
        """)
        self._machine_tree.itemDoubleClicked.connect(self._on_machine_dblclick)
        self._machine_tree.itemExpanded.connect(self._on_tree_item_toggle)
        self._machine_tree.itemCollapsed.connect(self._on_tree_item_toggle)
        layout.addWidget(self._machine_tree)

        # Populate
        self._populate_machine_list()

        # Footer hint
        hint = QLabel("Double-click to place")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: #888; font-size: 11px; padding: 8px;")
        layout.addWidget(hint)

        return container

    def _populate_machine_list(self) -> None:
        """Load machine types from DB and group them by category in the Tree."""
        from database.crud import get_all_machines
        self._machines_data: dict[str, dict] = {}
        machines = get_all_machines()

        # Group machines by category
        categories: dict[str, list] = {}
        for m in machines:
            cat = m.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)

        # Create Tree items
        for cat_name in sorted(categories.keys()):
            # Category Header
            cat_item = QTreeWidgetItem(self._machine_tree)
            cat_item.setText(0, cat_name.upper())
            cat_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable) 
            # Note: We need some flags to allow expansion but we handle non-selection in dblclick
            cat_item.setForeground(0, QColor(_ACCENT))
            cat_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            cat_item.setData(0, Qt.UserRole + 1, cat_name) # Identifier for state lookup
            
            # Machine Items
            for m in sorted(categories[cat_name], key=lambda x: x["name"]):
                item = QTreeWidgetItem(cat_item)
                item.setText(0, f"  {m['name']}")
                item.setData(0, Qt.UserRole, m)
                self._machines_data[m["name"]] = m
            
            # RESTORE EXPANSION STATE
            from database.crud import get_setting
            is_expanded = get_setting(f"cat_expanded_{cat_name}", "true") == "true"
            cat_item.setExpanded(is_expanded)

    # ------------------------------------------------------------------
    # Double-click: place a new node at canvas centre
    # ------------------------------------------------------------------
    def _on_machine_dblclick(self, item: QTreeWidgetItem, column: int) -> None:
        from ui.machine_node import MachineNode
        machine_data = item.data(0, Qt.UserRole)
        if not machine_data:
            return  # This was a category header or empty

        # Place node at the centre of the current view
        view_centre = self.view.mapToScene(
            self.view.viewport().rect().center()
        )
        # Small random offset so multiple placements don't exactly overlap
        import random
        from PySide6.QtCore import QPointF
        offset = QPointF(random.randint(-40, 40), random.randint(-40, 40))

        node = MachineNode(machine_data, view_centre + offset, self.scene)
        self.scene.add_machine_node(node)
        self.scene.recalculate()
        self._update_status()

    def _on_tree_item_toggle(self, item: QTreeWidgetItem) -> None:
        """Save the expansion state of a category to DB."""
        cat_name = item.data(0, Qt.UserRole + 1)
        if cat_name:
            from database.crud import set_setting
            set_setting(f"cat_expanded_{cat_name}", "true" if item.isExpanded() else "false")

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
            get_setting,
        )
        from ui.machine_node import MachineNode
        from ui.connection_line import ConnectionLine

        # 0. Load Configuration
        saved_style = get_setting("line_style", "rounded")
        style_to_idx = {"rounded": 0, "straight": 1, "orthogonal": 2}
        self.style_combo.setCurrentIndex(style_to_idx.get(saved_style, 0))
        # (The currentIndexChanged signal will trigger _on_style_changed and scene.set_line_style)
        
        is_visible = get_setting("sidebar_visible", "true") == "true"
        self.toggle_btn.setChecked(is_visible)
        self._sidebar.setVisible(is_visible)

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
                # Find the matching ports by index
                s_idx = row.get("source_port_idx", 0)
                t_idx = row.get("target_port_idx", 0)
                
                src_port = src_node.output_ports[s_idx] if s_idx < len(src_node.output_ports) else None
                tgt_port = tgt_node.input_ports[t_idx]  if t_idx < len(tgt_node.input_ports)  else None
                
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
                    source_port_idx=conn.src_port.index,
                    target_port_idx=conn.tgt_port.index,
                    material_id=conn.material_id,
                )
                conn.conn_db_id = new_id
