"""
ui/production_line_dialog.py
Dialog to configure parameters for the Automated Factory Generator.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QDoubleSpinBox, QRadioButton, QLineEdit, QPushButton, QButtonGroup
)
from PySide6.QtCore import Qt

from database.crud import get_all_materials
from ui.i18n import tr

class ProductionLineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪄 " + tr("auto_gen_factory", "Auto-Generate Factory"))
        self.setFixedWidth(400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a2e; color: #eaeaea; font-family: "Segoe UI"; }}
            QLabel {{ color: #eaeaea; font-weight: bold; font-size: 12px; }}
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
                background: #0f3460; border: 1px solid #2a2a4a;
                border-radius: 4px; padding: 4px 8px; color: white;
            }}
            QPushButton {{
                background: #0f3460; border: 1px solid #2a2a4a;
                border-radius: 4px; padding: 6px; color: white; font-weight: bold;
            }}
            QPushButton:hover {{ border-color: #e94560; color: #e94560; }}
            QRadioButton {{ color: #eaeaea; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Target Material
        layout.addWidget(QLabel("Target Material:"))
        self.material_combo = QComboBox()
        self.materials = sorted(get_all_materials(), key=lambda m: m["name"])
        for mat in self.materials:
            self.material_combo.addItem(mat["name"], mat["id"])
        layout.addWidget(self.material_combo)

        # 2. Target Rate (items/min)
        layout.addWidget(QLabel("Target Rate (items/min):"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.1, 100000.0)
        self.rate_spin.setValue(60.0)
        self.rate_spin.setDecimals(1)
        self.rate_spin.setSuffix(" items/min")
        layout.addWidget(self.rate_spin)

        # 3. Destination
        layout.addWidget(QLabel("Destination:"))
        self.dest_group = QButtonGroup(self)
        
        self.radio_current = QRadioButton("Current Project")
        self.radio_current.setChecked(True)
        self.dest_group.addButton(self.radio_current)
        layout.addWidget(self.radio_current)
        
        self.radio_new = QRadioButton("New Project")
        self.dest_group.addButton(self.radio_new)
        layout.addWidget(self.radio_new)

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Enter new project name...")
        self.project_name_edit.setEnabled(False)
        layout.addWidget(self.project_name_edit)

        self.radio_new.toggled.connect(self.project_name_edit.setEnabled)

        layout.addStretch()

        # 4. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_generate = QPushButton("🪄 Generate")
        self.btn_generate.setStyleSheet(self.btn_generate.styleSheet() + " color: #e94560;")
        self.btn_generate.clicked.connect(self._on_generate)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_generate)
        layout.addLayout(btn_layout)

        self.result_data = {}

    def _on_generate(self) -> None:
        if self.radio_new.isChecked() and not self.project_name_edit.text().strip():
            self.project_name_edit.setFocus()
            return
            
        self.result_data = {
            "material_id": self.material_combo.currentData(),
            "material_name": self.material_combo.currentText(),
            "target_rate": self.rate_spin.value(),
            "new_project": self.radio_new.isChecked(),
            "project_name": self.project_name_edit.text().strip() if self.radio_new.isChecked() else None
        }
        self.accept()
