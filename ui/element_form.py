"""
ElementForm: simplified right-side panel with auto-parenting support.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QGroupBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor


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
    "other": ["click", "hover", "none"],
}

UI_TYPES = list(UI_TYPE_ACTIONS.keys())


class ElementForm(QWidget):
    element_confirmed = pyqtSignal(dict)
    sampling_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bbox: dict | None = None
        self._source: str = "human"
        self._prior_correction: dict | None = None
        self._choices: list[dict] = []
        self._sampling_active = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # logical_key
        layout.addWidget(QLabel("<b>Logical key *</b>"))
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("ex: checkbox_diag_1")
        layout.addWidget(self._key_input)

        # ui_type & action
        row1 = QHBoxLayout()
        v1 = QVBoxLayout()
        v1.addWidget(QLabel("Type"))
        self._ui_type = QComboBox()
        self._ui_type.addItems(UI_TYPES)
        self._ui_type.currentTextChanged.connect(self._on_ui_type_changed)
        v1.addWidget(self._ui_type)
        row1.addLayout(v1)

        v2 = QVBoxLayout()
        v2.addWidget(QLabel("Action"))
        self._action = QComboBox()
        v2.addWidget(self._action)
        row1.addLayout(v2)
        layout.addLayout(row1)

        # Parent Scroll (Simplified)
        self._scroll_group = QGroupBox("Scroll Context")
        scroll_layout = QVBoxLayout(self._scroll_group)
        self._parent_scroll_input = QComboBox()
        scroll_layout.addWidget(self._parent_scroll_input)
        self._requires_scroll_checkbox = QCheckBox("Visible uniquement après scroll")
        scroll_layout.addWidget(self._requires_scroll_checkbox)
        layout.addWidget(self._scroll_group)

        # --- Options Section (Collapsible in spirit, here just a group) ---
        self._choices_group = QGroupBox("Options / Cibles")
        choices_layout = QVBoxLayout(self._choices_group)
        h_choices = QHBoxLayout()
        self._choice_input = QLineEdit()
        self._choice_input.setPlaceholderText("Label de l'option")
        h_choices.addWidget(self._choice_input)
        add_choice_btn = QPushButton("+")
        add_choice_btn.clicked.connect(self._add_choice)
        h_choices.addWidget(add_choice_btn)
        choices_layout.addLayout(h_choices)

        self._choices_table = QTableWidget(0, 3)
        self._choices_table.setHorizontalHeaderLabels(["Label", "🎯", ""])
        self._choices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._choices_table.setColumnWidth(1, 30)
        self._choices_table.setColumnWidth(2, 24)
        self._choices_table.setFixedHeight(80)
        choices_layout.addWidget(self._choices_table)

        self._sample_btn = QPushButton("🎯 Capturer les points")
        self._sample_btn.setCheckable(True)
        self._sample_btn.toggled.connect(self._toggle_sampling)
        choices_layout.addWidget(self._sample_btn)
        layout.addWidget(self._choices_group)

        # Scroll Area specific config (hidden by default)
        self._scroll_config_group = QGroupBox("Config Scroll")
        sc_layout = QHBoxLayout(self._scroll_config_group)
        self._scroll_dir_input = QComboBox()
        self._scroll_dir_input.addItems(["down", "up", "left", "right"])
        self._scroll_amount_input = QSpinBox()
        self._scroll_amount_input.setRange(1, 1000)
        sc_layout.addWidget(self._scroll_dir_input)
        sc_layout.addWidget(self._scroll_amount_input)
        layout.addWidget(self._scroll_config_group)

        # Hidden fields but kept for data model
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setVisible(False)
        self._drag_target_input = QLineEdit()
        self._drag_target_input.setVisible(False)
        self._path_input = QLineEdit()
        self._path_input.setVisible(False)
        self._is_nav_checkbox = QCheckBox()
        self._is_nav_checkbox.setVisible(False)
        self._target_screen_input = QComboBox()
        self._target_screen_input.setVisible(False)

        # Info & Buttons
        self._bbox_label = QLabel("—")
        self._bbox_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self._bbox_label)

        self._add_btn = QPushButton("✅ AJOUTER AU MAPPING")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._confirm)
        self._add_btn.setMinimumHeight(40)
        self._add_btn.setStyleSheet("background: #2d6a2d; color: white; font-weight: bold; border-radius: 4px;")
        layout.addWidget(self._add_btn)

        self._clear_btn = QPushButton("✖ Effacer")
        self._clear_btn.clicked.connect(self._clear)
        layout.addWidget(self._clear_btn)

        layout.addStretch()
        self._on_ui_type_changed(self._ui_type.currentText())

    def _on_ui_type_changed(self, ui_type: str):
        actions = UI_TYPE_ACTIONS.get(ui_type, ["none"])
        self._action.clear()
        self._action.addItems(actions)

        is_val_type = ui_type in ("dropdown", "radio", "checkbox")
        self._choices_group.setVisible(is_val_type)

        is_scroll = ui_type == "scroll_area"
        self._scroll_config_group.setVisible(is_scroll)
        self._scroll_group.setVisible(not is_scroll)

    def set_parent_scroll_area(self, logical_key: str, requires_scroll: bool = False):
        """Called by MainWindow to auto-select the parent."""
        idx = self._parent_scroll_input.findText(logical_key)
        if idx >= 0:
            self._parent_scroll_input.setCurrentIndex(idx)
            self._requires_scroll_checkbox.setChecked(requires_scroll)

    def set_scroll_area_suggestions(self, names: list[str]):
        current = self._parent_scroll_input.currentText()
        self._parent_scroll_input.clear()
        self._parent_scroll_input.addItem("")
        self._parent_scroll_input.addItems(names)
        idx = self._parent_scroll_input.findText(current)
        if idx >= 0: self._parent_scroll_input.setCurrentIndex(idx)

    def set_screen_suggestions(self, screens: list[str]):
        self._target_screen_input.clear()
        self._target_screen_input.addItems(screens)

    def _add_choice(self):
        txt = self._choice_input.text().strip()
        if txt:
            self._choices.append({"label": txt, "x": None, "y": None})
            self._choice_input.clear()
            self._refresh_choices_table()

    def _refresh_choices_table(self):
        self._choices_table.setRowCount(0)
        for i, c in enumerate(self._choices):
            self._choices_table.insertRow(i)
            self._choices_table.setItem(i, 0, QTableWidgetItem(c["label"]))
            self._choices_table.setItem(i, 1, QTableWidgetItem("✅" if c["x"] is not None else "—"))
            del_btn = QPushButton("✖")
            del_btn.clicked.connect(lambda _, idx=i: [self._choices.pop(idx), self._refresh_choices_table()])
            self._choices_table.setCellWidget(i, 2, del_btn)

    def _toggle_sampling(self, checked: bool):
        self._sampling_active = checked
        self.sampling_toggled.emit(checked)

    def add_sampled_point(self, point: dict):
        for c in self._choices:
            if c["x"] is None:
                c["x"], c["y"] = point["x"], point["y"]
                self._refresh_choices_table()
                break
        if all(c["x"] is not None for c in self._choices):
            self._sample_btn.setChecked(False)

    def get_sampled_points(self) -> list[dict]:
        return [{"x": c["x"], "y": c["y"]} for c in self._choices if c["x"] is not None]

    def set_bbox(self, bbox: dict, source: str = "human", correction: dict | None = None) -> None:
        self._bbox, self._source = bbox, source
        self._bbox_label.setText(f"x={bbox['x']:.3f} y={bbox['y']:.3f} w={bbox['w']:.3f} h={bbox['h']:.3f}")

        if correction:
            self._key_input.setText(correction.get("logical_key", ""))
            self._ui_type.setCurrentText(correction.get("ui_type", "button"))
            self._action.setCurrentText(correction.get("action", "click"))
            self._parent_scroll_input.setCurrentText(correction.get("parent_scroll_area", ""))
            self._requires_scroll_checkbox.setChecked(correction.get("requires_scroll", False))
            self._choices = list(correction.get("choices", []))
            self._refresh_choices_table()
        else:
            self._key_input.clear()
            self._choices = []
            self._refresh_choices_table()

        self._add_btn.setEnabled(True)

    def _confirm(self):
        if not self._bbox: return
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet("border: 1px solid red;")
            return

        from core.mapping_store import build_element
        element = build_element(
            bbox_relative=self._bbox,
            logical_key=key,
            ui_type=self._ui_type.currentText(),
            action=self._action.currentText(),
            path=self._path_input.text(),
            source=self._source,
            expected_value=self._expected_value_input.text(),
            scroll_direction=self._scroll_dir_input.currentText(),
            scroll_amount=self._scroll_amount_input.value(),
            drag_target=self._drag_target_input.text(),
            choices=[c for c in self._choices if c["label"]],
            navigation_target=self._target_screen_input.currentText() if self._is_nav_checkbox.isChecked() else "",
            parent_scroll_area=self._parent_scroll_input.currentText(),
            requires_scroll=self._requires_scroll_checkbox.isChecked(),
        )
        self.element_confirmed.emit(element)
        self._clear()

    def _clear(self):
        self._bbox = None
        self._key_input.clear()
        self._key_input.setStyleSheet("")
        self._add_btn.setEnabled(False)
        self._bbox_label.setText("—")
