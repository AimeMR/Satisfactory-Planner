"""
ui/main_window.py
Phase 2 — Application shell: sidebar + canvas + status bar.
"""

from __future__ import annotations
import os
import random
import logging

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLabel, QSplitter,
    QStatusBar, QFrame, QComboBox, QPushButton, QCheckBox,
    QInputDialog, QMessageBox, QFileDialog, QMenu, QDialog,
)
from PySide6.QtCore    import Qt, QPointF
from PySide6.QtGui     import QColor, QFont, QIcon, QAction

from ui.canvas import FactoryScene, FactoryView
from ui.i18n import tr, get_language, set_language
from database.crud import (
    get_setting, set_setting,
    get_all_machines, get_all_projects, get_all_placed_nodes,
    get_all_connections, get_all_groups,
    get_machine_by_id, get_recipe_by_id, get_material_by_id,
    add_project, add_placed_node, add_connection,
    add_group, update_group_collapse,
    rename_project, delete_project, delete_placed_node, delete_group,
    set_node_group,
)

logger = logging.getLogger("satisfactory_planner")


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
        # Language Support
        from ui.i18n import set_language, tr
        from database.crud import get_setting
        lang = get_setting("language", "en")
        set_language(lang)
        
        self.setWindowTitle(tr("app_title"))
        self.resize(1400, 900)
        self._apply_global_styles()

        # Scene + view
        self.scene = FactoryScene()
        self.view  = FactoryView(self.scene)
        
        # Project State
        self.current_project_id = int(get_setting("current_project_id", "1"))
        self.scene.project_id = self.current_project_id

        # Sidebar
        self._sidebar = self._build_sidebar()

        # Splitter: sidebar | canvas
        self.layout_splitter = QSplitter(Qt.Horizontal)
        self.layout_splitter.addWidget(self._sidebar)
        self.layout_splitter.addWidget(self.view)
        self.layout_splitter.setStretchFactor(0, 0)
        self.layout_splitter.setStretchFactor(1, 1)
        self.layout_splitter.setSizes([220, 1180])
        self.layout_splitter.setHandleWidth(1)

        # Toolbar (Top)
        self._toolbar = self._build_toolbar()
        
        # Main vertical layout to hold toolbar + splitter
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._toolbar)
        main_layout.addWidget(self.layout_splitter)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Status bar
        self._status = QStatusBar()
        self._status.setStyleSheet(f"background:{_SIDEBAR_BG}; color:{_TEXT}; font-size:12px;")
        self._status.showMessage("Ready — right-drag to pan, scroll: zoom, double-click: place")

        # Load any persisted layout from DB
        self._load_layout()

        # Info Visibility Micro-Menu (Floating Bottom Left)
        self._info_menu = self._build_info_menu()
        self._info_menu.setParent(self)
        self._info_menu.show()

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
        layout.setSpacing(12)

        from ui.i18n import tr

        _combo_css = f"""
            QComboBox {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 5px 10px;
                color: white;
                font-weight: bold;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {_SIDEBAR_BG};
                selection-background-color: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                color: white;
            }}
        """
        _small_btn_css = f"""
            QPushButton {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }}
            QPushButton:hover {{ border-color: {_ACCENT}; color: {_ACCENT}; }}
        """

        # ── 1. Title (Far Left) ──
        self.toolbar_title = QLabel(tr("app_title"))
        self.toolbar_title.setStyleSheet(f"color: {_ACCENT}; font-weight: bold; font-size: 14px; letter-spacing: 1px;")
        layout.addWidget(self.toolbar_title)

        layout.addSpacing(10)

        # ── 2. Database Selector ──
        self.db_label = QLabel("DB:")
        self.db_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.db_label)

        self.db_combo = QComboBox()
        self.db_combo.setFixedWidth(150)
        self.db_combo.setStyleSheet(_combo_css)
        self.db_combo.currentIndexChanged.connect(self._on_db_changed)
        layout.addWidget(self.db_combo)

        self.new_db_btn = QPushButton("+")
        self.new_db_btn.setFixedSize(30, 30)
        self.new_db_btn.setToolTip("New Database")
        self.new_db_btn.setStyleSheet(_small_btn_css)
        self.new_db_btn.clicked.connect(self._on_new_database)
        layout.addWidget(self.new_db_btn)

        self._populate_databases()

        layout.addSpacing(8)

        # ── 3. Project Selector ──
        self.proj_label = QLabel(tr("project") + ":")
        self.proj_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.proj_label)

        self.project_combo = QComboBox()
        self.project_combo.setFixedWidth(180)
        self.project_combo.setStyleSheet(_combo_css)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        layout.addWidget(self.project_combo)

        # ── 4. Project Actions Dropdown ──
        self.proj_actions_btn = QPushButton("⚙")
        self.proj_actions_btn.setFixedSize(30, 30)
        self.proj_actions_btn.setToolTip(tr("project") + " actions")
        self.proj_actions_btn.setStyleSheet(_small_btn_css)

        proj_menu = QMenu(self)
        proj_menu.setStyleSheet(f"""
            QMenu {{
                background: {_SIDEBAR_BG};
                border: 1px solid {_BORDER};
                color: white;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {_SIDEBAR_ITEM};
                color: {_ACCENT};
            }}
        """)

        self.act_new_proj    = proj_menu.addAction("➕ " + tr("new_proj"))
        self.act_rename_proj = proj_menu.addAction("✏️ " + tr("rename_proj"))
        proj_menu.addSeparator()
        self.act_export_proj = proj_menu.addAction("📤 " + tr("export_proj"))
        self.act_import_proj = proj_menu.addAction("📥 " + tr("import_proj"))
        proj_menu.addSeparator()
        self.act_delete_proj = proj_menu.addAction("🗑️ " + tr("delete_proj_title"))

        self.act_new_proj.triggered.connect(self._on_new_project)
        self.act_rename_proj.triggered.connect(self._on_rename_project)
        self.act_export_proj.triggered.connect(self._on_export_project)
        self.act_import_proj.triggered.connect(self._on_import_project)
        self.act_delete_proj.triggered.connect(self._on_delete_project)

        self.proj_actions_btn.setMenu(proj_menu)
        layout.addWidget(self.proj_actions_btn)

        self._populate_projects()

        # ── Spacer ──
        layout.addStretch()

        # ── 5. Line Style (Right side) ──
        self.style_label = QLabel(tr("line_style") + ":")
        self.style_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.style_label)

        self.style_combo = QComboBox()
        self.style_combo.addItems([tr("style_rounded"), tr("style_straight"), tr("style_manhattan")])
        self.style_combo.setFixedWidth(150)
        self.style_combo.setStyleSheet(_combo_css)
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)

        # ── 6. Language Toggle (Far Right) ──
        self.lang_btn = QPushButton(tr("lang_toggle"))
        self.lang_btn.setFixedWidth(60)
        self.lang_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 5px;
                color: {_ACCENT};
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT};
            }}
        """)
        self.lang_btn.clicked.connect(self._on_toggle_language)
        layout.addWidget(self.lang_btn)

        return bar

    def _on_style_changed(self, index: int) -> None:
        style_map = {0: "rounded", 1: "straight", 2: "orthogonal"}
        style = style_map.get(index, "rounded")
        self.scene.set_line_style(style)
        self._update_status()
        
        # PERSIST SETTING
        from database.crud import set_setting
        set_setting("line_style", style)

    def _toggle_sidebar(self) -> None:
        is_visible = self._sidebar_content.isVisible()
        self._sidebar_content.setVisible(not is_visible)
        # Swap the arrow icon
        self.toggle_btn.setText("▶" if is_visible else "◀")
        
        # Force the wrapper to shrink in the QSplitter
        target_w = 28 if is_visible else 248
        self._sidebar.setFixedWidth(target_w)
        if hasattr(self, "layout_splitter"):
            current_sizes = self.layout_splitter.sizes()
            total = sum(current_sizes)
            self.layout_splitter.setSizes([target_w, total - target_w])
        
        self._status.showMessage(f"Sidebar {'hidden' if is_visible else 'shown'}", 2000)
        
        # PERSIST SETTING
        from database.crud import set_setting
        set_setting("sidebar_visible", "false" if is_visible else "true")

    # ------------------------------------------------------------------
    # Project Handlers
    # ------------------------------------------------------------------
    def _populate_projects(self) -> None:
        """Load project list from DB into the combo box."""
        from database.crud import get_all_projects
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        
        projects = get_all_projects()
        found = False
        for p in projects:
            self.project_combo.addItem(p["name"], p["id"])
            if p["id"] == self.current_project_id:
                self.project_combo.setCurrentIndex(self.project_combo.count() - 1)
                found = True
        
        if self.project_combo.count() == 0:
            # Should not happen due to DB migration, but safety first
            from database.crud import add_project
            pid = add_project("Default Project")
            self.project_combo.addItem("Default Project", pid)
            self.current_project_id = pid
            found = True
            
        if not found and self.project_combo.count() > 0:
            first_pid = self.project_combo.itemData(0)
            self.current_project_id = first_pid
            from database.crud import set_setting
            set_setting("current_project_id", str(first_pid))
            self.project_combo.setCurrentIndex(0)

        self.project_combo.blockSignals(False)

    def _on_project_changed(self, index: int) -> None:
        if index < 0: return
        pid = self.project_combo.currentData()
        if pid == self.current_project_id: return
        
        # 1. SAVE current project before switching
        self._save_layout()

        # 2. Switch project
        self.current_project_id = pid
        from database.crud import set_setting
        set_setting("current_project_id", str(pid))
        
        self.scene.clear()
        self._load_layout()
        self._update_status()
        from ui.i18n import tr
        self._status.showMessage(tr("project_switched", self.project_combo.currentText()), 2000)

    def _on_new_project(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from ui.i18n import tr
        name, ok = QInputDialog.getText(self, tr("new_proj"), tr("project") + " " + tr("nodes") + ":")
        if ok and name.strip():
            # Save current first
            self._save_layout()
            
            from database.crud import add_project
            pid = add_project(name.strip())
            self.current_project_id = pid
            from database.crud import set_setting
            set_setting("current_project_id", str(pid))
            
            self._populate_projects()
            self.scene.clear()
            self._load_layout()
            self._update_status()

    def _on_rename_project(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from ui.i18n import tr
        old_name = self.project_combo.currentText()
        name, ok = QInputDialog.getText(self, tr("rename_proj"), tr("new_proj") + ":", text=old_name)
        if ok and name.strip() and name.strip() != old_name:
            from database.crud import rename_project
            rename_project(self.current_project_id, name.strip())
            self._populate_projects()

    def _on_export_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from ui.i18n import tr
        path, _ = QFileDialog.getSaveFileName(self, tr("export_proj"), "", "Project Files (*.json)")
        if path:
            from database.io import export_project_to_json
            if export_project_to_json(self.current_project_id, path):
                self._status.showMessage(tr("export_success", os.path.basename(path)), 3000)
            else:
                self._status.showMessage(tr("export_failed"), 3000)

    def _on_import_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from ui.i18n import tr
        path, _ = QFileDialog.getOpenFileName(self, tr("import_proj"), "", "Project Files (*.json)")
        if path:
            # Save current first
            self._save_layout()
            
            from database.io import import_project_from_json
            new_id = import_project_from_json(path)
            if new_id:
                self.current_project_id = new_id
                from database.crud import set_setting
                set_setting("current_project_id", str(new_id))
                self._populate_projects()
                self.scene.clear()
                self._load_layout()
                self._update_status()
                self._status.showMessage(tr("import_success", os.path.basename(path)), 3000)
            else:
                self._status.showMessage(tr("import_failed"), 3000)

    def _on_delete_project(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        from ui.i18n import tr
        proj_name = self.project_combo.currentText()
        
        reply = QMessageBox.question(
            self, tr("delete_proj_title"),
            tr("delete_proj_conf", proj_name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from database.crud import delete_project
            delete_project(self.current_project_id)
            
            # Switch to another project
            from database.crud import get_all_projects
            projects = get_all_projects()
            if projects:
                self.current_project_id = projects[0]["id"]
            else:
                from database.crud import add_project
                self.current_project_id = add_project("Default Project")
                
            from database.crud import set_setting
            set_setting("current_project_id", str(self.current_project_id))
            
            self._populate_projects()
            self.scene.clear()
            self._load_layout()
            self._update_status()
            self._status.showMessage(tr("project_deleted", proj_name), 3000)

    def _on_toggle_language(self) -> None:
        from ui.i18n import get_language, set_language, tr
        new_lang = "es" if get_language() == "en" else "en"
        set_language(new_lang)
        
        # Save to DB
        from database.crud import set_setting
        set_setting("language", new_lang)
        
        # REFRESH UI
        self.setWindowTitle(tr("app_title"))
        self.lang_btn.setText(tr("lang_toggle"))
        
        # New static labels
        self.toolbar_title.setText(tr("app_title"))
        self.proj_label.setText(tr("project") + ":")
        self.style_label.setText(tr("line_style") + ":")
        self.sidebar_header_label.setText("  " + tr("machine_library"))
        self.sidebar_hint.setText(tr("double_click_place"))
        
        # Re-populate language-sensitive areas
        self._populate_machine_list()
        self._populate_projects()

        # Update style combo
        self.style_combo.blockSignals(True)
        old_style = self.style_combo.currentIndex()
        self.style_combo.clear()
        self.style_combo.addItems([tr("style_rounded"), tr("style_straight"), tr("style_manhattan")])
        self.style_combo.setCurrentIndex(old_style)
        self.style_combo.blockSignals(False)
        
        # Update project actions menu text
        self.act_new_proj.setText("➕ " + tr("new_proj"))
        self.act_rename_proj.setText("✏️ " + tr("rename_proj"))
        self.act_export_proj.setText("📤 " + tr("export_proj"))
        self.act_import_proj.setText("📥 " + tr("import_proj"))
        self.act_delete_proj.setText("🗑️ " + tr("delete_proj_title"))
        
        # Refresh info menu strings
        self.info_header.setText(tr("show_info"))
        self.check_power.setText(tr("info_power"))
        self.check_inputs.setText(tr("info_inputs"))
        self.check_output.setText(tr("info_output"))
        self.check_belts.setText(tr("info_belts"))
        
        self._update_status()
        self._status.showMessage(f"Language switched to {new_lang.upper()}", 3000)

    # ------------------------------------------------------------------
    # Database Management
    # ------------------------------------------------------------------
    def _populate_databases(self) -> None:
        """Load .db filenames from databases/ folder into the combo."""
        from database.db import list_databases, get_active_db_name

        self.db_combo.blockSignals(True)
        self.db_combo.clear()

        dbs = list_databases()
        active = get_active_db_name()

        for db_name in dbs:
            display = db_name.replace(".db", "")
            self.db_combo.addItem(display, db_name)
            if db_name == active:
                self.db_combo.setCurrentIndex(self.db_combo.count() - 1)

        self.db_combo.blockSignals(False)

    def _on_db_changed(self, index: int) -> None:
        if index < 0:
            return
        db_name = self.db_combo.currentData()
        from database.db import get_active_db_name
        if db_name == get_active_db_name():
            return

        # 1. Save current layout before switching
        self._save_layout()

        # 2. Close old connection, switch, initialise new DB
        from database.db import close_connection, set_db_path, initialize_db
        close_connection()
        set_db_path(db_name)
        initialize_db()
        # NOTE: seed_db() not called — other databases may be for different games

        # 3. Reload everything
        self.current_project_id = 1
        from database.crud import get_setting, set_setting
        self.current_project_id = int(get_setting("current_project_id", "1"))
        self.scene.project_id = self.current_project_id

        self._populate_machine_list()
        self._populate_projects()
        self.scene.clear()
        self.scene._machines.clear()
        self.scene._connections.clear()
        self.scene._groups.clear()
        self._load_layout()
        self._update_status()
        self._status.showMessage(f"Switched to database: {db_name}", 3000)

    def _on_new_database(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "New Database",
            "Enter a name for the new database:\n"
            "(Example: 'factorio' will create 'factorio.db')"
        )
        if ok and name.strip():
            db_name = name.strip()
            if not db_name.endswith(".db"):
                db_name += ".db"

            # Check if already exists
            from database.db import list_databases
            if db_name in list_databases():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Database '{db_name}' already exists.")
                return

            # Save current project first
            self._save_layout()

            # Switch to new DB (initialize_db creates the schema)
            from database.db import close_connection, set_db_path, initialize_db
            close_connection()
            set_db_path(db_name)
            initialize_db()

            # Reset state for blank DB
            self.current_project_id = 1
            from database.crud import set_setting
            set_setting("current_project_id", "1")
            self.scene.project_id = 1

            self._populate_databases()
            self._populate_machine_list()
            self._populate_projects()
            self.scene.clear()
            self.scene._machines.clear()
            self.scene._connections.clear()
            self.scene._groups.clear()
            self._load_layout()
            self._update_status()
            self._status.showMessage(f"Created new database: {db_name}", 3000)

    # ------------------------------------------------------------------
    # Add Element (Material / Machine / Recipe)
    # ------------------------------------------------------------------
    def _on_add_element(self) -> None:
        from ui.add_element_dialog import (
            AddElementTypeDialog, AddMaterialDialog,
            AddMachineDialog, AddRecipeDialog,
        )

        # Step 1: Ask what type
        type_dlg = AddElementTypeDialog(self)
        if type_dlg.exec() != QDialog.Accepted:
            return

        chosen = type_dlg.chosen_type

        # Step 2: Show the correct form
        if chosen == "material":
            dlg = AddMaterialDialog(self)
            if dlg.exec() == QDialog.Accepted:
                from database.crud import add_material
                add_material(dlg.result_data["name"], dlg.result_data["type"])
                self._status.showMessage(f"Material '{dlg.result_data['name']}' added.", 3000)

        elif chosen == "machine":
            dlg = AddMachineDialog(self)
            if dlg.exec() == QDialog.Accepted:
                from database.crud import add_machine
                d = dlg.result_data
                add_machine(d["name"], d["category"], d["base_power"],
                            d["inputs_allowed"], d["outputs_allowed"])
                self._populate_machine_list()
                self._status.showMessage(f"Machine '{d['name']}' added.", 3000)

        elif chosen == "recipe":
            dlg = AddRecipeDialog(self)
            if dlg.exec() == QDialog.Accepted:
                from database.crud import add_recipe
                d = dlg.result_data
                add_recipe(d["name"], d["machine_id"], d["ingredients"], d["craft_time"])
                self._status.showMessage(f"Recipe '{d['name']}' added.", 3000)

    def _build_info_menu(self) -> QFrame:
        from ui.i18n import tr
        from database.crud import get_setting
        
        frame = QFrame()
        frame.setObjectName("InfoMenu")
        frame.setFixedWidth(180)
        # Style: Glassmorphism / Dark Translucent
        frame.setStyleSheet(f"""
            QFrame#InfoMenu {{
                background: rgba(15, 52, 96, 220);
                border: 1px solid {_BORDER};
                border-top-left-radius: 12px;
            }}
            QLabel {{ 
                color: {_ACCENT}; 
                font-weight: bold; 
                font-size: 10px; 
                letter-spacing: 0.5px;
                padding-bottom: 2px;
                border-bottom: 1px solid rgba(233, 69, 96, 50);
            }}
            QCheckBox {{ color: white; font-size: 11px; padding: 2px; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px; border: 1px solid {_BORDER}; background: #16213e; }}
            QCheckBox::indicator:checked {{ background: {_ACCENT}; border-color: {_ACCENT}; }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        
        self.info_header = QLabel(tr("show_info"))
        layout.addWidget(self.info_header)
        
        # Checkboxes
        self.check_power  = QCheckBox(tr("info_power"))
        self.check_inputs = QCheckBox(tr("info_inputs"))
        self.check_output = QCheckBox(tr("info_output"))
        self.check_belts  = QCheckBox(tr("info_belts"))
        
        # Load states
        from database.crud import get_setting
        self.check_power.setChecked(get_setting("show_power", "true") == "true")
        self.check_inputs.setChecked(get_setting("show_inputs", "true") == "true")
        self.check_output.setChecked(get_setting("show_output", "true") == "true")
        self.check_belts.setChecked(get_setting("show_belts", "true") == "true")
        
        # Connect signals (Use clicked to ensure it only reacts to user)
        self.check_power.clicked.connect(lambda: self._on_info_toggle("show_power", self.check_power.isChecked()))
        self.check_inputs.clicked.connect(lambda: self._on_info_toggle("show_inputs", self.check_inputs.isChecked()))
        self.check_output.clicked.connect(lambda: self._on_info_toggle("show_output", self.check_output.isChecked()))
        self.check_belts.clicked.connect(lambda: self._on_info_toggle("show_belts", self.check_belts.isChecked()))
        
        layout.addWidget(self.check_power)
        layout.addWidget(self.check_inputs)
        layout.addWidget(self.check_output)
        layout.addWidget(self.check_belts)
        
        return frame

    def _on_info_toggle(self, key: str, val: bool) -> None:
        from ui.settings_cache import set_cached_setting
        set_cached_setting(key, "true" if val else "false")
        # Force redraw of machine nodes and connections
        self.scene.update()
        for conn in self.scene.all_connections():
             conn._update_label() # Explicitly update connection labels

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Reposition floating menu to bottom right
        if hasattr(self, "_info_menu"):
            # Put it above status bar
            sb_h = self.statusBar().height() if self.statusBar() else 30
            self._info_menu.move(
                self.width() - self._info_menu.width(), 
                self.height() - self._info_menu.height() - sb_h
            )

    def _build_sidebar(self) -> QWidget:
        wrapper = QWidget()
        wrap_layout = QHBoxLayout(wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)

        self._sidebar_content = QWidget()
        self._sidebar_content.setFixedWidth(220)
        self._sidebar_content.setStyleSheet(f"""
            QWidget {{ background: {_SIDEBAR_BG}; }}
        """)

        layout = QVBoxLayout(self._sidebar_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header without toggle button
        from ui.i18n import tr
        header_widget = QWidget()
        header_widget.setFixedHeight(36)
        header_widget.setStyleSheet(f"background: {_ACCENT};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 0, 4, 0)
        header_layout.setSpacing(0)

        self.sidebar_header_label = QLabel("  " + tr("machine_library"))
        self.sidebar_header_label.setStyleSheet("""
            color: white;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
        """)
        header_layout.addWidget(self.sidebar_header_label)
        header_layout.addStretch()

        layout.addWidget(header_widget)

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

        # Add Element button
        self.add_element_btn = QPushButton("➕ Add Element")
        self.add_element_btn.setFixedHeight(34)
        self.add_element_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SIDEBAR_ITEM};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                color: #00d2ff;
                font-weight: bold;
                font-size: 12px;
                margin: 6px;
            }}
            QPushButton:hover {{ border-color: {_ACCENT}; color: {_ACCENT}; background: #1a2a5e; }}
        """)
        self.add_element_btn.clicked.connect(self._on_add_element)
        layout.addWidget(self.add_element_btn)

        # Footer hint
        self.sidebar_hint = QLabel(tr("double_click_place"))
        self.sidebar_hint.setAlignment(Qt.AlignCenter)
        self.sidebar_hint.setStyleSheet(f"color: #888; font-size: 11px; padding: 8px;")
        layout.addWidget(self.sidebar_hint)

        wrap_layout.addWidget(self._sidebar_content)
        
        # Toggle strip
        self._toggle_strip = QWidget()
        self._toggle_strip.setFixedWidth(28)
        self._toggle_strip.setStyleSheet(f"background: {_SIDEBAR_BG}; border-left: 1px solid {_BORDER}; border-right: 1px solid {_BORDER};")
        strip_layout = QVBoxLayout(self._toggle_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)

        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setFixedSize(28, 36)
        self.toggle_btn.setToolTip("Toggle sidebar")
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                border: none;
                border-radius: 0px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #ff6b81; }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        
        strip_layout.addWidget(self.toggle_btn)
        strip_layout.addStretch()

        wrap_layout.addWidget(self._toggle_strip)

        return wrapper

    def _populate_machine_list(self) -> None:
        """Load machine types from DB and group them by category in the Tree."""
        self._machine_tree.clear()
        from database.crud import get_all_machines
        from ui.i18n import tr
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
            cat_item.setText(0, tr(cat_name.lower()))
            cat_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable) 
            # Note: We need some flags to allow expansion but we handle non-selection in dblclick
            cat_item.setForeground(0, QColor(_ACCENT))
            font = QFont("Segoe UI", 9)
            font.setPixelSize(12)
            font.setBold(True)
            cat_item.setFont(0, font)
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

        # Add to DB first to get an ID
        from database.crud import add_placed_node
        db_id = add_placed_node(self.current_project_id, machine_data["id"], pos_x=view_centre.x()+offset.x(), pos_y=view_centre.y()+offset.y())

        node = MachineNode(machine_data, view_centre + offset, self.scene, db_id=db_id)
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
        from ui.i18n import tr
        n = len(self.scene.all_nodes())
        c = len(self.scene.all_connections())
        self._status.showMessage(tr("status_bar", n, c))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_layout(self) -> None:
        """Reload placed nodes and connections saved in the DB."""
        from database.crud import (
            get_all_placed_nodes, get_all_connections,
            get_machine_by_id, get_recipe_by_id, get_material_by_id,
            get_setting, get_all_projects,
        )
        from ui.machine_node import MachineNode
        from ui.connection_line import ConnectionLine
        
        self.scene.project_id = self.current_project_id

        # 0. Load Configuration
        saved_style = get_setting("line_style", "rounded")
        style_to_idx = {"rounded": 0, "straight": 1, "orthogonal": 2}
        self.style_combo.setCurrentIndex(style_to_idx.get(saved_style, 0))
        # (The currentIndexChanged signal will trigger _on_style_changed and scene.set_line_style)
        
        is_visible = get_setting("sidebar_visible", "true") == "true"
        self._sidebar_content.setVisible(is_visible)
        self.toggle_btn.setText("◀" if is_visible else "▶")
        
        target_w = 248 if is_visible else 28
        self._sidebar.setFixedWidth(target_w)
        if hasattr(self, "layout_splitter"):
            current_sizes = self.layout_splitter.sizes()
            total = sum(current_sizes) if sum(current_sizes) > 0 else 1400
            self.layout_splitter.setSizes([target_w, total - target_w])

        node_map: dict[int, MachineNode] = {}  # db_id → MachineNode
        group_map: dict[int, SubFactoryNode] = {}

        # 1. Load Nodes FIRST (so we know which are in which group)
        for row in get_all_placed_nodes(self.current_project_id):
            machine = get_machine_by_id(row["machine_id"])
            if not machine:
                continue
            pos = QPointF(row["pos_x"], row["pos_y"])
            node = MachineNode(machine, pos, self.scene,
                               db_id=row["id"],
                               recipe_id=row.get("recipe_id"),
                               clock_speed=row.get("clock_speed", 1.0),
                               group_id=row.get("group_id"))
            self.scene.add_machine_node(node)
            node_map[row["id"]] = node

        # 2. Load Groups (skip orphan groups that have no members)
        from database.crud import get_all_groups
        from ui.sub_factory_node import SubFactoryNode
        for gdata in get_all_groups(self.current_project_id):
            gid = gdata["id"]
            # Find nodes that belong to this group
            members = [n for n in node_map.values() if n.group_id == gid]
            if not members:
                # Orphan group — delete from DB and skip
                from database.crud import delete_group
                delete_group(gid)
                continue
            sub_node = SubFactoryNode(gdata, self.scene, members)
            self.scene.addItem(sub_node)
            self.scene._groups.append(sub_node)
            group_map[gid] = sub_node
            if sub_node.is_collapsed:
                for m in members:
                    m.setVisible(False)

        # 2. Load Connections for this project
        for row in get_all_connections(self.current_project_id):
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
            add_placed_node, add_connection, get_all_groups, delete_group, add_group,
            update_group_collapse,
        )
        
        # 1. Clear everything for this project
        for row in get_all_placed_nodes(self.current_project_id):
            delete_placed_node(row["id"])
        for row in get_all_groups(self.current_project_id):
            delete_group(row["id"])

        # 2. Map Groups
        group_id_map: dict[int, int] = {} # old_obj_id -> new_db_id
        for group in list(self.scene._groups):
            try:
                if not group.members:
                    continue  # Don't save empty groups
                new_gid = add_group(
                    project_id=self.current_project_id,
                    name=group.name,
                    x=group.pos().x(),
                    y=group.pos().y()
                )
                update_group_collapse(new_gid, group.is_collapsed)
                group_id_map[id(group)] = new_gid
                group.group_id = new_gid
            except RuntimeError:
                continue  # C++ object already deleted

        # 3. Map Nodes
        id_map: dict[int, int] = {}  # old_obj_id → new_db_id
        for node in self.scene.all_nodes():
            try:
                # Find group_id if node belongs to a group
                parent_group = next((g for g in self.scene._groups if node in g.members), None)
                new_gid = group_id_map.get(id(parent_group)) if parent_group else None
                
                new_id = add_placed_node(
                    project_id=self.current_project_id,
                    machine_id=node._m_id,
                    recipe_id=node.recipe_id,
                    pos_x=node.pos().x(),
                    pos_y=node.pos().y(),
                    clock_speed=node._clock_speed,
                    group_id=new_gid
                )
                id_map[id(node)] = new_id
                node.db_id = new_id
            except RuntimeError:
                continue  # C++ object already deleted

        # 4. Map Connections
        for conn in self.scene.all_connections():
            try:
                # Use original node refs (survives proxy rerouting)
                src_node = conn._original_src_node
                tgt_node = conn._original_tgt_node
                src_id = id_map.get(id(src_node))
                tgt_id = id_map.get(id(tgt_node))
                if src_id and tgt_id:
                    new_id = add_connection(
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        source_port_idx=getattr(conn.src_port, 'index', 0),
                        target_port_idx=getattr(conn.tgt_port, 'index', 0),
                        material_id=conn.material_id,
                    )
                    conn.conn_db_id = new_id
            except RuntimeError:
                continue  # C++ object already deleted

