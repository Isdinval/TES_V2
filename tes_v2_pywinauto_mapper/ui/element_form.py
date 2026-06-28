from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QPushButton, QLabel, QGroupBox, QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt
from core.element import UIElement
from core.utils import name_to_logical_key

UI_TYPES = [
    "button", "text_input", "checkbox", "radio", "dropdown", "label",
    "icon", "tab", "menu_item", "toggle", "date_picker", "table_cell",
    "scroll_area", "drag_handle", "radio_group", "checkbox_group", "tab_bar", "other"
]

UI_TYPE_ACTIONS = {
    "button": ["click", "double_click", "right_click", "hover"],
    "text_input": ["click_then_type", "click", "triple_click_then_type"],
    "checkbox": ["check", "uncheck", "click"],
    "radio": ["click", "select"],
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
    "radio_group": ["select_by_label", "select_by_index"],
    "checkbox_group": ["check_by_label", "uncheck_by_label", "check_by_index"],
    "tab_bar": ["click_by_label", "click_by_index"],
    "other": ["click", "hover", "none"],
}

class ChoiceListWidget(QWidget):
    """
    Editable list of {label, x, y} choices for radio_group / checkbox_group / tab_bar.
    Emits choices_changed(list[dict]) when the user edits.
    """
    choices_changed = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._rows = []   # list of (QWidget row, QLineEdit label_edit, float x, float y, str stable_id)

        self.add_btn = QPushButton("+ Add choice manually")
        self.add_btn.clicked.connect(lambda: self._add_row("", 0.0, 0.0, ""))
        self._layout.addWidget(self.add_btn)

    def set_choices(self, choices: list):
        for row_tuple in self._rows:
            row_tuple[0].setParent(None)
        self._rows.clear()
        for c in choices:
            self._add_row(
                c.get("label", ""),
                c.get("x", 0.0),
                c.get("y", 0.0),
                c.get("stable_id", ""),
                c.get("control_type", ""),
                c.get("class_name", ""),
                c.get("automation_id", ""),
                c.get("rect", None),
            )

    def _add_row(self, label, x, y, stable_id, control_type="", class_name="",
                 automation_id="", rect=None):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)

        # Type badge: colored label showing control_type
        TYPE_COLORS = {
            "RadioButton": ("#2196F3", "white"),   # blue
            "CheckBox":    ("#4CAF50", "white"),   # green
            "TabItem":     ("#9C27B0", "white"),   # purple
            "Static":      ("#9E9E9E", "white"),   # grey
            "Text":        ("#9E9E9E", "white"),
            "Button":      ("#FF9800", "white"),   # orange
        }
        bg, fg = TYPE_COLORS.get(control_type, ("#607D8B", "white"))
        type_badge = QLabel(control_type or "?")
        type_badge.setFixedWidth(90)
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setStyleSheet(
            f"background: {bg}; color: {fg}; font-size: 9px; "
            f"border-radius: 3px; padding: 1px 3px;"
        )

        INTERACTIVE_TYPES = {"RadioButton", "CheckBox", "TabItem", "Button"}
        interactive = control_type in INTERACTIVE_TYPES
        badge_tooltip = (f"{control_type} — interactive (keep this)"
                         if interactive
                         else f"{control_type} — likely a label, consider removing")
        type_badge.setToolTip(badge_tooltip)

        label_edit = QLineEdit(label)
        label_edit.setPlaceholderText("Option label")

        # Metadata line: show automation_id if present, then coords
        meta_parts = []
        if automation_id:
            meta_parts.append(f"id:{automation_id}")
        meta_parts.append(f"({x:.3f},{y:.3f})")
        meta_label = QLabel(" | ".join(meta_parts))
        meta_label.setStyleSheet("color: #888; font-size: 9px; font-family: monospace;")
        meta_label.setMinimumWidth(120)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(24)
        remove_btn.clicked.connect(lambda: self._remove_row(row))

        label_edit.textChanged.connect(self._emit_changes)

        row_layout.addWidget(type_badge)
        row_layout.addWidget(label_edit, stretch=2)
        row_layout.addWidget(meta_label, stretch=1)
        row_layout.addWidget(remove_btn)

        self._rows.append((row, label_edit, x, y, stable_id, control_type, class_name,
                           automation_id, rect))
        self._layout.insertWidget(self._layout.count() - 1, row)

    def _remove_row(self, row_widget):
        self._rows = [r for r in self._rows if r[0] is not row_widget]
        row_widget.setParent(None)
        self._emit_changes()

    def _emit_changes(self):
        self.choices_changed.emit(self.get_choices())

    def get_choices(self) -> list:
        result = []
        for r in self._rows:
            row, le, x, y, stable_id, ct, cn, aid, rect = r
            entry = {"label": le.text().strip(), "x": x, "y": y, "stable_id": stable_id}
            if ct:    entry["control_type"] = ct
            if cn:    entry["class_name"] = cn
            if aid:   entry["automation_id"] = aid
            if rect:  entry["rect"] = rect
            result.append(entry)
        return result

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

        self.patterns_label = QLabel("")
        self.patterns_label.setStyleSheet("color: #888; font-size: 10px;")

        self.form_layout.addRow("Logical Key*:", self.logical_key_edit)
        self.form_layout.addRow("UI Type:", self.ui_type_combo)
        self.form_layout.addRow("Action:", self.action_combo)
        self.form_layout.addRow("Path:", self.path_edit)
        self.form_layout.addRow("Expected Value:", self.expected_value_edit)
        self.form_layout.addRow("Value Pattern:", self.value_pattern_cb)
        self.form_layout.addRow("Notes:", self.notes_edit)
        self.form_layout.addRow("UIA Patterns:", self.patterns_label)

        # Choice Group Widget
        self.choice_list = ChoiceListWidget()
        self.choice_group_widget = QGroupBox("Choices")
        choice_layout = QVBoxLayout(self.choice_group_widget)
        choice_layout.addWidget(self.choice_list)
        self.form_layout.addRow(self.choice_group_widget)

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
        show_expected = ui_type in ["dropdown", "radio", "checkbox", "table_cell", "date_picker"]
        self.expected_value_edit.setVisible(show_expected)
        label = self.form_layout.labelForField(self.expected_value_edit)
        if label:
            label.setVisible(show_expected)

        show_choices = ui_type in ("radio_group", "checkbox_group", "tab_bar")
        self.choice_group_widget.setVisible(show_choices)

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

        # Automatic Logical Key suggestion (3-priority cascade)
        if not element.logical_key:
            if element.automation_id and not element.automation_id.isdigit():
                element.logical_key = element.automation_id
            elif element.name.strip():
                element.logical_key = name_to_logical_key(element.name)
            else:
                rect_hash = abs(hash(str(element.rectangle))) % 10000
                element.logical_key = f"{element.control_type.lower()}_{rect_hash}"

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

        # Set choices
        self.choice_list.set_choices(element.choices or [])

        patterns = getattr(element, 'supported_patterns', [])
        hint = getattr(element, 'execution_hint', 'pyautogui_fallback')
        if patterns:
            self.patterns_label.setText(f"{', '.join(patterns)} [{hint}]")
        else:
            self.patterns_label.setText("none detected (pyautogui fallback)")

        self._validate_form()

    def _suggest_ui_type(self, element: UIElement):
        # If scanner already inferred a ui_type from patterns, use it directly
        if element.ui_type and element.ui_type not in ("", "Unknown", element.control_type):
            idx = self.ui_type_combo.findText(element.ui_type)
            if idx >= 0:
                self.ui_type_combo.setCurrentIndex(idx)
                return  # Pattern-based inference is more reliable than our heuristic

        ctype = element.control_type.lower()
        mapping = {
            "button": "button",
            "edit": "text_input",
            "checkbox": "checkbox",
            "radiobutton": "radio",
            "combobox": "dropdown",
            "list": "dropdown",
            "text": "label",
            "image": "icon",
            "tabitem": "tab",
            "menuitem": "menu_item",
            "datagrid": "table_cell",
            "pane": "other",
            "window": "other",
            "group": "other",
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
        self.current_element.choices = self.choice_list.get_choices()

        self.element_updated.emit(self.current_element)

    def clear_form(self):
        self.logical_key_edit.clear()
        self.ui_type_combo.setCurrentIndex(0)
        self.path_edit.clear()
        self.expected_value_edit.clear()
        self.value_pattern_cb.setChecked(False)
        self.notes_edit.clear()
        self.patterns_label.clear()
        self.choice_list.set_choices([])
        self._validate_form()
