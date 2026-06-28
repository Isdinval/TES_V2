from PyQt6.QtWidgets import (QScrollArea, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QPushButton, QGroupBox, QLabel, QTextEdit,
                             QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt
from core.element import UIElement
from core.utils import name_to_logical_key

UI_TYPES = [
    "button", "text_input", "checkbox", "radio", "dropdown", "label",
    "icon", "tab", "menu_item", "toggle", "date_picker", "table_cell",
    "scroll_area", "drag_handle", "radio_group", "checkbox_group", "tab_bar",
    "dropdown_group",
    "other"
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
    "dropdown_group": ["select_by_label", "select_by_index"],
    "other": ["click", "hover", "none"],
}


class ChoiceListWidget(QWidget):
    choices_changed = pyqtSignal(list)

    # Maximum visible height for the scrollable area (shows ~5 rows before scrolling)
    MAX_VISIBLE_HEIGHT = 180

    def __init__(self):
        super().__init__()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(4)

        # --- Header row: count label + "Add" button always visible ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel("0 choices")
        self.count_label.setStyleSheet("color: #666; font-size: 10px;")

        self.pick_btn = QPushButton("📍 Pick")
        self.pick_btn.setFixedWidth(55)
        self.pick_btn.setCheckable(True)
        self.pick_btn.setToolTip(
            "Click this, then click on the screenshot to add a choice at that position.\n"
            "The option label will be auto-filled with the element name if one is found."
        )
        self.pick_btn.toggled.connect(self._on_pick_mode_toggled)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.setToolTip("Add a choice manually (enter label and set coordinates)")
        self.add_btn.clicked.connect(lambda: self._add_row("", 0.0, 0.0, ""))

        header_layout.addWidget(self.count_label)
        header_layout.addStretch()
        header_layout.addWidget(self.pick_btn)
        header_layout.addWidget(self.add_btn)
        outer_layout.addWidget(header)

        # --- Scrollable rows container ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setMaximumHeight(self.MAX_VISIBLE_HEIGHT)
        self.scroll_area.setMinimumHeight(60)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum
        )
        # Style the scrollbar to be visible but not intrusive
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid #ccc; border-radius: 3px; }
            QScrollBar:vertical {
                width: 8px; background: #f0f0f0; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #aaa; border-radius: 4px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #888; }
        """)

        # Inner container for the rows
        self.rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self.rows_container)
        self._rows_layout.setContentsMargins(2, 2, 2, 2)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()   # pushes rows to top

        self.scroll_area.setWidget(self.rows_container)
        outer_layout.addWidget(self.scroll_area)

        self._rows = []
        self._canvas = None
        self._pick_mode = False

    def _on_pick_mode_toggled(self, enabled: bool):
        if not hasattr(self, '_canvas') or self._canvas is None:
            self.pick_btn.setChecked(False)
            return
        self._pick_mode = enabled
        if enabled:
            self.pick_btn.setText("✕ Cancel")
            # Ensure mutual exclusion with other canvas modes
            if hasattr(self._canvas, 'parent') and hasattr(self._canvas.parent(), '_cancel_active_mode'):
                self._canvas.parent()._cancel_active_mode()
            self._canvas.set_pick_mode(True, callback=self._on_canvas_pick)
        else:
            self.pick_btn.setText("📍 Pick")
            self._canvas.set_pick_mode(False)

    def _on_canvas_pick(self, rel_x: float, rel_y: float, element=None):
        """
        Called by the canvas when user clicks in pick mode.
        rel_x, rel_y are relative coordinates (0.0–1.0).
        element is the UIElement under the cursor (or None if empty area).
        """
        label = ""
        control_type = ""
        if element:
            label = element.name or element.logical_key or ""
            control_type = element.control_type

        self._add_row(label, rel_x, rel_y, stable_id="", control_type=control_type)
        self._emit_changes()
        self.pick_btn.setChecked(False)  # exit pick mode after one pick

    def set_choices(self, choices: list):
        # Remove all existing rows
        for row_tuple in self._rows:
            row_tuple[0].setParent(None)
        self._rows.clear()
        # Add new rows
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
        self._update_count_label()
        # Scroll back to top after loading
        self.scroll_area.verticalScrollBar().setValue(0)

    def _add_row(self, label, x, y, stable_id, control_type="", class_name="",
                 automation_id="", rect=None):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 1, 0, 1)
        row_layout.setSpacing(4)

        # --- Index badge (shows position in list) ---
        idx = len(self._rows)
        index_badge = QLabel(f"{idx+1}")
        index_badge.setFixedSize(18, 18)
        index_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        index_badge.setStyleSheet(
            "background: #555; color: white; font-size: 8px; "
            "font-weight: bold; border-radius: 9px;"
        )

        # --- Type badge ---
        TYPE_COLORS = {
            "RadioButton": ("#1565C0", "#E3F2FD"),
            "CheckBox":    ("#2E7D32", "#F1F8E9"),
            "TabItem":     ("#E65100", "#FFF3E0"),
            "ListItem":    ("#7B1FA2", "#F3E5F5"),
            "MenuItem":    ("#7B1FA2", "#F3E5F5"),
            "Button":      ("#BF360C", "#FBE9E7"),
        }
        fg, bg = TYPE_COLORS.get(control_type, ("#555", "#eee"))
        short_type = control_type[:2].upper() if control_type else "??"
        type_badge = QLabel(short_type)
        type_badge.setFixedSize(22, 18)
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setStyleSheet(
            f"background: {bg}; color: {fg}; font-size: 8px; "
            f"font-weight: bold; border-radius: 3px;"
        )
        # Tooltip shows full type + metadata
        tooltip_parts = [f"Type: {control_type or 'Unknown'}"]
        if class_name:    tooltip_parts.append(f"Class: {class_name}")
        if automation_id: tooltip_parts.append(f"AutoID: {automation_id}")
        tooltip_parts.append(f"Coords: ({x:.4f}, {y:.4f})")
        if rect: tooltip_parts.append(f"Rect: {[round(v,4) for v in rect]}")
        type_badge.setToolTip("\n".join(tooltip_parts))

        # Mark interactive types with a star in tooltip
        INTERACTIVE = {"RadioButton", "CheckBox", "TabItem", "ListItem", "MenuItem"}
        if control_type in INTERACTIVE:
            type_badge.setToolTip(type_badge.toolTip() + "\n★ Interactive — keep this")
        else:
            type_badge.setToolTip(type_badge.toolTip() + "\n⚠ Non-interactive — consider removing")

        # --- Label edit ---
        label_edit = QLineEdit(label)
        label_edit.setPlaceholderText("Option label")
        label_edit.setMinimumWidth(80)

        # --- Coord display (compact) ---
        coord_label = QLabel(f"{x:.3f},{y:.3f}")
        coord_label.setFixedWidth(80)
        coord_label.setStyleSheet("color: #888; font-size: 9px; font-family: monospace;")
        coord_label.setToolTip(f"Relative center: x={x:.6f}, y={y:.6f}")

        # --- Remove button ---
        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(22)
        remove_btn.setFixedHeight(22)
        remove_btn.setStyleSheet("color: #cc0000; font-weight: bold; border: none;")
        remove_btn.setToolTip("Remove this choice")
        remove_btn.clicked.connect(lambda: self._remove_row(row))

        label_edit.textChanged.connect(self._emit_changes)

        row_layout.addWidget(index_badge)
        row_layout.addWidget(type_badge)
        row_layout.addWidget(label_edit, stretch=3)
        row_layout.addWidget(coord_label)
        row_layout.addWidget(remove_btn)

        row.setMaximumHeight(32)

        # Insert before the stretch at the end
        insert_pos = self._rows_layout.count() - 1
        self._rows_layout.insertWidget(insert_pos, row)

        self._rows.append((row, label_edit, x, y, stable_id, control_type,
                           class_name, automation_id, rect))
        self._update_count_label()

        # Scroll to the newly added row
        self.scroll_area.ensureWidgetVisible(row)

    def _remove_row(self, row_widget):
        self._rows = [r for r in self._rows if r[0] is not row_widget]
        row_widget.setParent(None)
        self._update_indices()
        self._update_count_label()
        self._emit_changes()

    def _update_indices(self):
        """Refresh the index badges after a removal."""
        for i, (row, le, *_) in enumerate(self._rows):
            # Find the index_badge (first child label)
            badge = row.layout().itemAt(0).widget()
            if badge:
                badge.setText(str(i + 1))

    def _update_count_label(self):
        n = len(self._rows)
        interactive_types = {"RadioButton", "CheckBox", "TabItem", "ListItem", "MenuItem"}
        n_interactive = sum(
            1 for r in self._rows
            if r[5] in interactive_types  # r[5] = control_type
        )
        if n_interactive < n:
            self.count_label.setText(
                f"{n} choices ({n_interactive} interactive, {n - n_interactive} other)"
            )
            self.count_label.setStyleSheet("color: #E65100; font-size: 10px;")  # orange warning
        else:
            self.count_label.setText(f"{n} choices")
            self.count_label.setStyleSheet("color: #666; font-size: 10px;")

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
        self._canvas = None

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
        self.choice_group_widget.setMaximumHeight(260)  # header + scroll area + padding
        choice_layout = QVBoxLayout(self.choice_group_widget)
        choice_layout.addWidget(self.choice_list)
        self.form_layout.addRow(self.choice_group_widget)

        # Trigger Group Widget
        self.trigger_info_label = QLabel("No trigger set. Options assumed always visible.")
        self.trigger_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.trigger_group_widget = QGroupBox("Trigger (where to click to open)")
        trigger_layout = QVBoxLayout(self.trigger_group_widget)

        trigger_instruction = QLabel(
            "Optional: define where to click to make the options visible.\n"
            "Leave empty if options are always visible (e.g. visible radio buttons).\n"
            "For dropdown/combobox: match logical_key with the 'dropdown' trigger element."
        )
        trigger_instruction.setWordWrap(True)
        trigger_instruction.setStyleSheet("color: #666; font-size: 9px;")

        self.set_trigger_btn = QPushButton("📌 Set trigger from selected element on canvas")
        self.set_trigger_btn.setToolTip(
            "First select the element to click to open this group "
            "(e.g. the ComboBox button), then click this button."
        )
        self.set_trigger_btn.clicked.connect(self._on_set_trigger_from_canvas)

        trigger_layout.addWidget(self.trigger_info_label)
        trigger_layout.addWidget(trigger_instruction)
        trigger_layout.addWidget(self.set_trigger_btn)
        self.form_layout.addRow(self.trigger_group_widget)

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

    def set_canvas(self, canvas):
        """Called from main_window.py to inject canvas reference."""
        self._canvas = canvas
        self.choice_list._canvas = canvas

    def _on_set_trigger_from_canvas(self):
        """
        Called when user clicks 'Set trigger from selected element on canvas'.
        Reads the canvas's currently selected element (not self.current_element)
        and uses its rectangle as the trigger for self.current_element.
        """
        if not hasattr(self, '_canvas') or self._canvas is None:
            return
        trigger_el = self._canvas.selected_element
        if trigger_el is None or trigger_el is self.current_element:
            return
        if not self.current_element or not self.current_element.ref_resolution:
            return
        rw, rh = self.current_element.ref_resolution
        tx, ty, tw, th = trigger_el.rectangle
        self.current_element.trigger = {
            "x": round(tx / rw, 6),
            "y": round(ty / rh, 6),
            "w": round(tw / rw, 6),
            "h": round(th / rh, 6),
        }
        self.trigger_info_label.setText(
            f"✅ Trigger set from '{trigger_el.logical_key or trigger_el.name}': "
            f"({self.current_element.trigger['x']:.3f}, {self.current_element.trigger['y']:.3f})"
        )
        self.trigger_info_label.setStyleSheet(
            "color: #008800; font-weight: bold; font-size: 10px;"
        )

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

        show_choices = ui_type in ("radio_group", "checkbox_group", "tab_bar", "dropdown_group")
        self.choice_group_widget.setVisible(show_choices)

        MULTI_CHOICE_TYPES = {"radio_group", "checkbox_group", "tab_bar", "dropdown_group"}
        show_trigger = ui_type in MULTI_CHOICE_TYPES
        self.trigger_group_widget.setVisible(show_trigger)

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

        # Set trigger info
        MULTI_CHOICE_TYPES = {"radio_group", "checkbox_group", "tab_bar", "dropdown_group"}
        if element.ui_type in MULTI_CHOICE_TYPES:
            if element.trigger:
                t = element.trigger
                self.trigger_info_label.setText(
                    f"✅ Trigger set: center=({t['x']:.3f}, {t['y']:.3f}) "
                    f"size={t['w']:.3f}×{t['h']:.3f}"
                )
                self.trigger_info_label.setStyleSheet(
                    "color: #008800; font-weight: bold; font-size: 10px;"
                )
            else:
                self.trigger_info_label.setText(
                    "No trigger set. Options assumed always visible."
                )
                self.trigger_info_label.setStyleSheet("color: #888; font-size: 10px;")

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
