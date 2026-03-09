"""
ui/add_element_dialog.py
Dialogs for adding Materials, Machines, and Recipes to the active database.
"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QDoubleSpinBox, QSpinBox, QDialogButtonBox,
    QGroupBox, QScrollArea, QWidget, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Palette (reused from main_window)
_BG        = "#16213e"
_ITEM_BG   = "#0f3460"
_ACCENT    = "#e94560"
_TEXT       = "#eaeaea"
_BORDER    = "#2a2a4a"

_DIALOG_CSS = f"""
    QDialog {{
        background: {_BG};
        color: {_TEXT};
    }}
    QLabel {{
        color: {_TEXT};
        font-size: 12px;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {_ITEM_BG};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        padding: 5px 8px;
        color: white;
        font-size: 12px;
        min-width: 180px;
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background: {_BG};
        selection-background-color: {_ITEM_BG};
        border: 1px solid {_BORDER};
        color: white;
    }}
    QPushButton {{
        background: {_ITEM_BG};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        padding: 6px 16px;
        color: white;
        font-weight: bold;
        font-size: 12px;
    }}
    QPushButton:hover {{
        border-color: {_ACCENT};
        color: {_ACCENT};
    }}
    QGroupBox {{
        color: {_ACCENT};
        font-weight: bold;
        border: 1px solid {_BORDER};
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}
"""


# ---------------------------------------------------------------------------
# Type Chooser — first step
# ---------------------------------------------------------------------------

class AddElementTypeDialog(QDialog):
    """Ask the user what kind of element they want to add."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Element")
        self.setFixedSize(340, 220)
        self.setStyleSheet(_DIALOG_CSS)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("What do you want to add?")
        header.setStyleSheet(f"color: {_ACCENT}; font-size: 14px; font-weight: bold;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        for emoji, label, value in [
            ("🧱", "Material", "material"),
            ("⚙️", "Machine", "machine"),
            ("📋", "Recipe", "recipe"),
        ]:
            btn = QPushButton(f"{emoji}  {label}")
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_ITEM_BG};
                    border: 1px solid {_BORDER};
                    border-radius: 6px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {_ACCENT};
                    color: {_ACCENT};
                    background: #1a2a5e;
                }}
            """)
            btn.clicked.connect(lambda _, v=value: self._choose(v))
            layout.addWidget(btn)

        self.chosen_type = None

    def _choose(self, value: str):
        self.chosen_type = value
        self.accept()


# ---------------------------------------------------------------------------
# Add Material
# ---------------------------------------------------------------------------

class AddMaterialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Material")
        self.setFixedWidth(400)
        self.setStyleSheet(_DIALOG_CSS)

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Iron Ore")
        layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["solid", "liquid", "gas"])
        layout.addRow("Type:", self.type_combo)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name cannot be empty.")
            return
        self.result_data = {
            "name": name,
            "type": self.type_combo.currentText(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Add Machine
# ---------------------------------------------------------------------------

class AddMachineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Machine")
        self.setFixedWidth(420)
        self.setStyleSheet(_DIALOG_CSS)

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Constructor")
        layout.addRow("Name:", self.name_edit)

        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("e.g. Production, Extraction, Power…")
        layout.addRow("Category:", self.category_edit)

        self.power_spin = QDoubleSpinBox()
        self.power_spin.setRange(0, 99999)
        self.power_spin.setSuffix(" MW")
        self.power_spin.setDecimals(1)
        layout.addRow("Base Power:", self.power_spin)

        self.inputs_spin = QSpinBox()
        self.inputs_spin.setRange(0, 10)
        self.inputs_spin.setValue(1)
        layout.addRow("Inputs Allowed:", self.inputs_spin)

        self.outputs_spin = QSpinBox()
        self.outputs_spin.setRange(0, 10)
        self.outputs_spin.setValue(1)
        layout.addRow("Outputs Allowed:", self.outputs_spin)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        name = self.name_edit.text().strip()
        category = self.category_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name cannot be empty.")
            return
        if not category:
            QMessageBox.warning(self, "Error", "Category cannot be empty.")
            return
        self.result_data = {
            "name": name,
            "category": category,
            "base_power": self.power_spin.value(),
            "inputs_allowed": self.inputs_spin.value(),
            "outputs_allowed": self.outputs_spin.value(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Add Recipe (dynamic ingredient rows)
# ---------------------------------------------------------------------------

class _IngredientRow(QWidget):
    """A single input/output ingredient row."""

    def __init__(self, materials: list[dict], is_input: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.material_combo = QComboBox()
        self.material_combo.setMinimumWidth(160)
        for m in materials:
            self.material_combo.addItem(m["name"], m["id"])
        layout.addWidget(self.material_combo)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setFixedWidth(90)
        layout.addWidget(self.amount_spin)

        self.remove_btn = QPushButton("−")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {_BORDER};
                border-radius: 4px;
                color: #ff5555;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ border-color: #ff5555; background: #330000; }}
        """)
        layout.addWidget(self.remove_btn)

    def get_data(self) -> dict:
        return {
            "material_id": self.material_combo.currentData(),
            "amount": self.amount_spin.value(),
        }


class AddRecipeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Recipe")
        self.setMinimumWidth(500)
        self.setStyleSheet(_DIALOG_CSS)

        from database.crud import get_all_machines, get_all_materials
        self._machines = get_all_machines()
        self._materials = get_all_materials()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header fields
        form = QFormLayout()
        form.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Iron Plate")
        form.addRow("Recipe Name:", self.name_edit)

        self.machine_combo = QComboBox()
        for m in self._machines:
            self.machine_combo.addItem(f"{m['name']} ({m['category']})", m["id"])
        form.addRow("Machine:", self.machine_combo)

        self.craft_time_spin = QDoubleSpinBox()
        self.craft_time_spin.setRange(0.1, 9999)
        self.craft_time_spin.setValue(2.0)
        self.craft_time_spin.setSuffix(" s")
        self.craft_time_spin.setDecimals(1)
        form.addRow("Craft Time:", self.craft_time_spin)

        main_layout.addLayout(form)

        # Inputs group
        self._inputs_group = QGroupBox("Inputs")
        self._inputs_layout = QVBoxLayout(self._inputs_group)
        self._inputs_layout.setSpacing(4)
        self._input_rows: list[_IngredientRow] = []

        add_input_btn = QPushButton("+ Add Input")
        add_input_btn.clicked.connect(lambda: self._add_row(is_input=True))
        self._inputs_layout.addWidget(add_input_btn)
        main_layout.addWidget(self._inputs_group)

        # Outputs group
        self._outputs_group = QGroupBox("Outputs")
        self._outputs_layout = QVBoxLayout(self._outputs_group)
        self._outputs_layout.setSpacing(4)
        self._output_rows: list[_IngredientRow] = []

        add_output_btn = QPushButton("+ Add Output")
        add_output_btn.clicked.connect(lambda: self._add_row(is_input=False))
        self._outputs_layout.addWidget(add_output_btn)
        main_layout.addWidget(self._outputs_group)

        # Start with one input and one output row
        self._add_row(is_input=True)
        self._add_row(is_input=False)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def _add_row(self, is_input: bool):
        row = _IngredientRow(self._materials, is_input)
        if is_input:
            self._input_rows.append(row)
            # Insert before the "+ Add" button
            self._inputs_layout.insertWidget(self._inputs_layout.count() - 1, row)
        else:
            self._output_rows.append(row)
            self._outputs_layout.insertWidget(self._outputs_layout.count() - 1, row)

        row.remove_btn.clicked.connect(lambda: self._remove_row(row, is_input))

    def _remove_row(self, row: _IngredientRow, is_input: bool):
        if is_input:
            if row in self._input_rows:
                self._input_rows.remove(row)
        else:
            if row in self._output_rows:
                self._output_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Recipe name cannot be empty.")
            return
        if not self._input_rows and not self._output_rows:
            QMessageBox.warning(self, "Error", "Add at least one input or output.")
            return

        ingredients = []
        for row in self._input_rows:
            d = row.get_data()
            d["is_input"] = True
            ingredients.append(d)
        for row in self._output_rows:
            d = row.get_data()
            d["is_input"] = False
            ingredients.append(d)

        self.result_data = {
            "name": name,
            "machine_id": self.machine_combo.currentData(),
            "craft_time": self.craft_time_spin.value(),
            "ingredients": ingredients,
        }
        self.accept()
