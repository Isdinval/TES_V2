from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QPushButton, QLabel, QGroupBox, QCheckBox)
from PyQt6.QtCore import pyqtSignal
from core.element import UIElement

class ElementForm(QWidget):
    element_updated = pyqtSignal(object)

    ACTIONS = [
        "Click", "SetText", "SelectItem", "Toggle",
        "GetValue", "Exists", "Invoke", "ExpandCollapse"
    ]

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.current_element = None

        self.group = QGroupBox("Mapping Configuration")
        self.form_layout = QFormLayout(self.group)

        self.logical_key_edit = QLineEdit()
        self.logical_key_edit.setPlaceholderText("e.g. login_button")

        self.ui_type_edit = QLineEdit() # Could be a combo but start with edit

        self.action_combo = QComboBox()
        self.action_combo.addItems(self.ACTIONS)
        self.action_combo.setEditable(True)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)

        self.value_pattern_cb = QCheckBox("Supports Value Pattern")

        self.form_layout.addRow("Logical Key*:", self.logical_key_edit)
        self.form_layout.addRow("UI Type:", self.ui_type_edit)
        self.form_layout.addRow("Action:", self.action_combo)
        self.form_layout.addRow("Value Pattern:", self.value_pattern_cb)
        self.form_layout.addRow("Notes:", self.notes_edit)

        self.layout.addWidget(self.group)

        self.save_btn = QPushButton("Update Element")
        self.save_btn.clicked.connect(self._on_save)
        self.layout.addWidget(self.save_btn)

        self.layout.addStretch()

    def set_element(self, element: UIElement):
        self.current_element = element
        if not element:
            self.clear_form()
            return

        self.logical_key_edit.setText(element.logical_key)
        self.ui_type_edit.setText(element.ui_type)
        idx = self.action_combo.findText(element.action)
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)
        else:
            self.action_combo.setEditText(element.action)

        self.value_pattern_cb.setChecked(element.value_pattern)
        self.notes_edit.setText(element.notes)

    def _on_save(self):
        if not self.current_element:
            return

        self.current_element.logical_key = self.logical_key_edit.text().strip()
        self.current_element.ui_type = self.ui_type_edit.text().strip()
        self.current_element.action = self.action_combo.currentText().strip()
        self.current_element.value_pattern = self.value_pattern_cb.isChecked()
        self.current_element.notes = self.notes_edit.toPlainText().strip()

        self.element_updated.emit(self.current_element)

    def clear_form(self):
        self.logical_key_edit.clear()
        self.ui_type_edit.clear()
        self.action_combo.setCurrentIndex(0)
        self.value_pattern_cb.setChecked(False)
        self.notes_edit.clear()
