from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QPushButton, QLabel, QGroupBox, QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt
from core.element import UIElement

UI_TYPES = [
    "button", "text_input", "checkbox", "radio", "dropdown", "label",
    "icon", "tab", "menu_item", "toggle", "date_picker", "table_cell",
    "scroll_area", "drag_handle", "hyperlink", "slider", "spinner", "tree_item", "other"
]

UI_TYPE_ACTIONS = {
    "button": ["click", "double_click", "right_click", "hover"],
    "text_input": ["click_then_type", "click", "triple_click_then_type"],
    "checkbox": ["check", "uncheck", "click"],
    "radio": ["select", "click"],
    "dropdown": ["select", "click"],
    "label": ["hover", "none"],
    "icon": ["click", "double_click", "right_click", "hover"],
    "tab": ["click", "hover"],
    "menu_item": ["click", "hover"],
    "toggle": ["click"],
    "date_picker": ["click", "click_then_type", "select"],
    "table_cell": ["click", "double_click", "click_then_type", "none"],
    "scroll_area": ["scroll"],
    "drag_handle": ["drag"],
    "hyperlink": ["click", "hover"],
    "slider": ["set_value", "click"],
    "spinner": ["triple_click_then_type", "click_then_type"],
    "tree_item": ["click", "double_click", "expand", "select"],
    "other": ["click", "hover", "none"],
}

class ElementForm(QWidget):
    element_updated = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.current_element = None

        self.group = QGroupBox("Mapping Configuration")
        self.form_layout = QFormLayout(self.group)

        self.logical_key_edit = QLineEdit()
        self.logical_key_edit.setPlaceholderText("e.g. login_button")
        self.logical_key_edit.textChanged.connect(self._validate_form)

        self.ui_type_combo = QComboBox()
        self.ui_type_combo.addItems(UI_TYPES)
        self.ui_type_combo.currentTextChanged.connect(self._on_ui_type_changed)

        self.action_combo = QComboBox()
        # Actions will be populated dynamically

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("UIA Path / XPath (optional)")

        self.expected_value_edit = QLineEdit()
        self.expected_value_edit.setPlaceholderText("Value to select or check")

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Internal notes...")
        self.notes_edit.setMaximumHeight(80)

        self.value_pattern_cb = QCheckBox("Supports Value Pattern")

        self.form_layout.addRow("Logical Key*:", self.logical_key_edit)
        self.form_layout.addRow("UI Type:", self.ui_type_combo)
        self.form_layout.addRow("Action:", self.action_combo)
        self.form_layout.addRow("Path:", self.path_edit)
        self.form_layout.addRow("Expected Value:", self.expected_value_edit)
        self.form_layout.addRow("Value Pattern:", self.value_pattern_cb)
        self.form_layout.addRow("Notes:", self.notes_edit)

        self.layout.addWidget(self.group)

        self.save_btn = QPushButton("Update Element")
        self.save_btn.clicked.connect(self._on_save)
        self.layout.addWidget(self.save_btn)

        self.status_msg = QLabel("")
        self.status_msg.setStyleSheet("color: red;")
        self.layout.addWidget(self.status_msg)

        self.layout.addStretch()

        # Initial state
        self._on_ui_type_changed(self.ui_type_combo.currentText())
        self._validate_form()

    def _on_ui_type_changed(self, ui_type):
        self.action_combo.clear()
        actions = UI_TYPE_ACTIONS.get(ui_type, ["click"])
        self.action_combo.addItems(actions)

        # Dynamic visibility
        show_expected = ui_type in ["dropdown", "radio", "checkbox", "table_cell", "date_picker", "slider"]
        self.expected_value_edit.setVisible(show_expected)
        label = self.form_layout.labelForField(self.expected_value_edit)
        if label:
            label.setVisible(show_expected)

    def _validate_form(self):
        key = self.logical_key_edit.text().strip()
        is_valid = len(key) > 0

        if not is_valid:
            self.logical_key_edit.setStyleSheet("border: 1px solid red;")
            self.save_btn.setEnabled(False)
            self.status_msg.setText("Logical Key is mandatory")
        else:
            self.logical_key_edit.setStyleSheet("")
            self.save_btn.setEnabled(True)
            self.status_msg.setText("")

    def set_element(self, element: UIElement):
        self.current_element = element
        if not element:
            self.clear_form()
            return

        # Automatic Logical Key suggestion
        if not element.logical_key and element.automation_id:
            element.logical_key = element.automation_id

        self.logical_key_edit.setText(element.logical_key)

        # Try to match UI Type
        idx = self.ui_type_combo.findText(element.ui_type)
        if idx >= 0:
            self.ui_type_combo.setCurrentIndex(idx)
        else:
            self._suggest_ui_type(element)

        # Action (depends on UI Type)
        idx = self.action_combo.findText(element.action)
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)

        self.path_edit.setText(getattr(element, "path", ""))
        self.expected_value_edit.setText(getattr(element, "expected_value", ""))
        self.value_pattern_cb.setChecked(getattr(element, "value_pattern", False))
        self.notes_edit.setText(getattr(element, "notes", ""))

        self._validate_form()

    def _suggest_ui_type(self, element: UIElement):
        ctype = element.control_type.lower()
        mapping = {
            "button": "button",
            "edit": "text_input",
            "checkbox": "checkbox",
            "radiobutton": "radio",
            "combobox": "dropdown",
            "list": "dropdown",
            "listitem": "dropdown",
            "text": "label",
            "image": "icon",
            "tabitem": "tab",
            "menuitem": "menu_item",
            "datagrid": "table_cell",
            "dataitem": "table_cell",
            "hyperlink": "hyperlink",
            "slider": "slider",
            "spinner": "spinner",
            "treeitem": "tree_item",
            "scrollbar": "scroll_area",
            "pane": "other",
            "window": "other",
            "group": "other",
            "custom": "other",
        }
        suggested = mapping.get(ctype, "other")

        # Some special cases
        if ctype == "edit" and "password" in element.name.lower():
            suggested = "text_input"

        idx = self.ui_type_combo.findText(suggested)
        if idx >= 0:
            self.ui_type_combo.setCurrentIndex(idx)

    def _on_save(self):
        if not self.current_element:
            return

        key = self.logical_key_edit.text().strip()
        if not key:
            self._validate_form()
            return

        self.current_element.logical_key = key
        self.current_element.ui_type = self.ui_type_combo.currentText()
        self.current_element.action = self.action_combo.currentText()
        self.current_element.path = self.path_edit.text().strip()
        self.current_element.expected_value = self.expected_value_edit.text().strip()
        self.current_element.value_pattern = self.value_pattern_cb.isChecked()
        self.current_element.notes = self.notes_edit.toPlainText().strip()

        self.element_updated.emit(self.current_element)

    def clear_form(self):
        self.logical_key_edit.clear()
        self.ui_type_combo.setCurrentIndex(0)
        self.path_edit.clear()
        self.expected_value_edit.clear()
        self.value_pattern_cb.setChecked(False)
        self.notes_edit.clear()
        self._validate_form()
