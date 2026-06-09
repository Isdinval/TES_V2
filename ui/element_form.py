"""
ElementForm: right-side panel where the human fills in metadata
for the selected/drawn bbox.
Emits element_confirmed with a complete element dict.
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
    element_confirmed = pyqtSignal(dict)   # full element dict ready to add
    sampling_toggled = pyqtSignal(bool)    # emitted when user starts/stops sampling click targets

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bbox: dict | None = None
        self._source: str = "human"
        self._prior_correction: dict | None = None

        self._choices: list[dict] = [] # [{"label": str, "x": float, "y": float}]
        self._sampling_active = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Status label
        self._status = QLabel("Dessine ou clique un élément sur le screenshot")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(self._status)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        # BBox info (read-only)
        bbox_group = QGroupBox("Bbox (relative)")
        bbox_layout = QHBoxLayout(bbox_group)
        self._bbox_label = QLabel("—")
        self._bbox_label.setFont(QFont("monospace", 9))
        self._bbox_label.setStyleSheet("color: #ccc;")
        bbox_layout.addWidget(self._bbox_label)
        layout.addWidget(bbox_group)

        # logical_key
        layout.addWidget(QLabel("Logical key *"))
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("ex: diagnostic_squelettique")
        layout.addWidget(self._key_input)

        # ui_type
        layout.addWidget(QLabel("UI Type *"))
        self._ui_type = QComboBox()
        self._ui_type.addItems(UI_TYPES)
        self._ui_type.currentTextChanged.connect(self._on_ui_type_changed)
        layout.addWidget(self._ui_type)

        # action
        layout.addWidget(QLabel("Action *"))
        self._action = QComboBox()
        layout.addWidget(self._action)

        # --- Multi-Choice / Targets Section ---
        self._choices_group = QGroupBox("Options / Cibles")
        choices_layout = QVBoxLayout(self._choices_group)

        h_choices = QHBoxLayout()
        self._choice_input = QLineEdit()
        self._choice_input.setPlaceholderText("Label de l'option")
        h_choices.addWidget(self._choice_input)
        add_choice_btn = QPushButton("+")
        add_choice_btn.setFixedWidth(30)
        add_choice_btn.clicked.connect(self._add_choice)
        h_choices.addWidget(add_choice_btn)
        choices_layout.addLayout(h_choices)

        self._choices_table = QTableWidget(0, 3)
        self._choices_table.setHorizontalHeaderLabels(["Label", "Cible", ""])
        self._choices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._choices_table.setColumnWidth(1, 40)
        self._choices_table.setColumnWidth(2, 24)
        self._choices_table.setFixedHeight(100)
        choices_layout.addWidget(self._choices_table)

        self._sample_btn = QPushButton("🎯 Capturer les points de clic")
        self._sample_btn.setCheckable(True)
        self._sample_btn.toggled.connect(self._toggle_sampling)
        choices_layout.addWidget(self._sample_btn)

        layout.addWidget(self._choices_group)

        # expected_value (for validations or radio select)
        self._expected_value_label = QLabel("Valeur attendue")
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setPlaceholderText("ex: True ou label exact")
        layout.addWidget(self._expected_value_label)
        layout.addWidget(self._expected_value_input)

        # Navigation section
        self._nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout(self._nav_group)
        self._is_nav_checkbox = QCheckBox("Bouton de navigation ?")
        self._is_nav_checkbox.toggled.connect(self._on_nav_toggled)
        nav_layout.addWidget(self._is_nav_checkbox)

        self._target_screen_label = QLabel("Écran de destination")
        self._target_screen_input = QComboBox()
        self._target_screen_input.setEditable(True)
        nav_layout.addWidget(self._target_screen_label)
        nav_layout.addWidget(self._target_screen_input)
        layout.addWidget(self._nav_group)

        # parent_scroll_area
        parent_scroll_box = QGroupBox("Zone Scrollable")
        parent_scroll_layout = QVBoxLayout(parent_scroll_box)

        self._parent_scroll_label = QLabel("Conteneur parent")
        self._parent_scroll_input = QComboBox()
        self._parent_scroll_input.setPlaceholderText("Aucune zone scrollable")
        self._parent_scroll_input.currentTextChanged.connect(self._on_parent_scroll_changed)

        self._requires_scroll_checkbox = QCheckBox("Nécessite un scroll préalable ?")
        self._requires_scroll_checkbox.setToolTip("Cocher si cet élément n'est visible qu'après avoir fait défiler le parent")

        parent_scroll_layout.addWidget(self._parent_scroll_label)
        parent_scroll_layout.addWidget(self._parent_scroll_input)
        parent_scroll_layout.addWidget(self._requires_scroll_checkbox)

        self._parent_scroll_group = parent_scroll_box
        layout.addWidget(self._parent_scroll_group)

        # scroll fields (only for scroll_area type)
        self._scroll_dir_label = QLabel("Direction du scroll")
        self._scroll_dir_input = QComboBox()
        self._scroll_dir_input.addItems(["up", "down", "left", "right"])
        self._scroll_dir_input.setCurrentText("down")
        self._scroll_amount_label = QLabel("Quantité (px ou pages)")
        self._scroll_amount_input = QSpinBox()
        self._scroll_amount_input.setRange(1, 5000)
        self._scroll_amount_input.setValue(1)
        layout.addWidget(self._scroll_dir_label)
        layout.addWidget(self._scroll_dir_input)
        layout.addWidget(self._scroll_amount_label)
        layout.addWidget(self._scroll_amount_input)

        # drag fields (drag_handle)
        self._drag_target_label = QLabel("Drag Target (Logical Key)")
        self._drag_target_input = QLineEdit()
        self._drag_target_input.setPlaceholderText("ex: target_zone")
        layout.addWidget(self._drag_target_label)
        layout.addWidget(self._drag_target_input)

        # path
        layout.addWidget(QLabel("Path fonctionnel"))
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("ex: Fiche Patient > Diagnostic")
        layout.addWidget(self._path_input)

        # Prior correction notice
        self._correction_label = QLabel("")
        self._correction_label.setWordWrap(True)
        self._correction_label.setStyleSheet("color: #7ec8e3; font-style: italic; font-size: 11px;")
        layout.addWidget(self._correction_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("✅ Ajouter au mapping")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._confirm)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #2d6a2d; color: white; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #3a8a3a; }"
            "QPushButton:disabled { background: #333; color: #666; }"
        )
        btn_layout.addWidget(self._add_btn)

        self._clear_btn = QPushButton("✖ Effacer")
        self._clear_btn.clicked.connect(self._clear)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: #5a2020; color: white; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #7a2020; }"
        )
        btn_layout.addWidget(self._clear_btn)
        layout.addLayout(btn_layout)

        # Initial refresh
        self._on_ui_type_changed(self._ui_type.currentText())

    def _on_ui_type_changed(self, ui_type: str):
        # Update actions
        self._action.clear()
        actions = UI_TYPE_ACTIONS.get(ui_type, ["none"])
        self._action.addItems(actions)
        self._action.setCurrentIndex(0)

        # Conditional visibility
        is_val_type = ui_type in ("dropdown", "radio", "checkbox")
        self._choices_group.setVisible(is_val_type)
        self._expected_value_label.setVisible(is_val_type)
        self._expected_value_input.setVisible(is_val_type)

        is_scroll = ui_type == "scroll_area"
        self._scroll_dir_label.setVisible(is_scroll)
        self._scroll_dir_input.setVisible(is_scroll)
        self._scroll_amount_label.setVisible(is_scroll)
        self._scroll_amount_input.setVisible(is_scroll)

        # parent_scroll_area visibility: show for everything EXCEPT scroll_area itself
        self._parent_scroll_group.setVisible(not is_scroll)

        is_drag = ui_type == "drag_handle"
        self._drag_target_label.setVisible(is_drag)
        self._drag_target_input.setVisible(is_drag)

        is_button = ui_type == "button"
        self._nav_group.setVisible(is_button)
        if not is_button:
            self._is_nav_checkbox.setChecked(False)

    def _on_nav_toggled(self, checked: bool):
        self._target_screen_label.setVisible(checked)
        self._target_screen_input.setVisible(checked)

    def _on_parent_scroll_changed(self, text: str):
        # Only enable requires_scroll if a parent is selected
        self._requires_scroll_checkbox.setEnabled(bool(text.strip()))
        if not text.strip():
            self._requires_scroll_checkbox.setChecked(False)

    def _add_choice(self):
        txt = self._choice_input.text().strip()
        if not txt:
            return
        self._choices.append({"label": txt, "x": None, "y": None})
        self._choice_input.clear()
        self._refresh_choices_table()

    def _refresh_choices_table(self):
        self._choices_table.setRowCount(0)
        for i, c in enumerate(self._choices):
            self._choices_table.insertRow(i)
            self._choices_table.setItem(i, 0, QTableWidgetItem(c["label"]))

            target_status = "✅" if c["x"] is not None else "—"
            item = QTableWidgetItem(target_status)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._choices_table.setItem(i, 1, item)

            del_btn = QPushButton("✖")
            del_btn.setFixedWidth(24)
            del_btn.setStyleSheet("color: #cc4444; background: transparent; border: none;")
            del_btn.clicked.connect(self._make_delete_choice_handler(i))
            self._choices_table.setCellWidget(i, 2, del_btn)

    def _make_delete_choice_handler(self, idx: int):
        def handler():
            if 0 <= idx < len(self._choices):
                self._choices.pop(idx)
                self._refresh_choices_table()
        return handler

    def _toggle_sampling(self, checked: bool):
        self._sampling_active = checked
        self.sampling_toggled.emit(checked)
        if checked:
            self._status.setText("Mode cible : clique sur le screenshot pour chaque option")
        else:
            self._status.setText(f"Source: {self._source}")

    def add_sampled_point(self, point: dict):
        """Called from outside when a point is clicked on canvas."""
        # Assign to the first choice that doesn't have a target
        for c in self._choices:
            if c["x"] is None:
                c["x"] = point["x"]
                c["y"] = point["y"]
                self._refresh_choices_table()
                break

        # If all choices have targets, stop sampling automatically
        if all(c["x"] is not None for c in self._choices):
            self._sample_btn.setChecked(False)
            self._toggle_sampling(False)

    def get_sampled_points(self) -> list[dict]:
        return [{"x": c["x"], "y": c["y"]} for c in self._choices if c["x"] is not None]

    def set_screen_suggestions(self, screens: list[str]):
        current = self._target_screen_input.currentText()
        self._target_screen_input.clear()
        self._target_screen_input.addItems(screens)
        self._target_screen_input.setEditText(current)

    def set_scroll_area_suggestions(self, names: list[str]):
        """Update the parent_scroll_area dropdown with existing scroll areas."""
        current = self._parent_scroll_input.currentText()
        self._parent_scroll_input.blockSignals(True)
        self._parent_scroll_input.clear()
        self._parent_scroll_input.addItem("") # Empty option
        if names:
            self._parent_scroll_input.addItems(names)
            self._parent_scroll_input.setEnabled(True)
            self._parent_scroll_input.setPlaceholderText("Choisir un parent...")
        else:
            self._parent_scroll_input.setEnabled(False)
            self._parent_scroll_input.setPlaceholderText("Aucune zone scrollable")

        idx = self._parent_scroll_input.findText(current)
        if idx >= 0:
            self._parent_scroll_input.setCurrentIndex(idx)
        self._parent_scroll_input.blockSignals(False)
        self._on_parent_scroll_changed(self._parent_scroll_input.currentText())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_bbox(self, bbox: dict, source: str = "human", correction: dict | None = None) -> None:
        """Called when user selects or draws a bbox."""
        self._bbox = bbox
        self._source = source
        self._prior_correction = correction
        self._choices = []

        b = bbox
        self._bbox_label.setText(
            f"x={b['x']:.3f}  y={b['y']:.3f}  w={b['w']:.3f}  h={b['h']:.3f}"
        )

        if correction:
            self._key_input.setText(correction.get("logical_key", ""))

            ui_type = correction.get("ui_type", "")
            idx = self._ui_type.findText(ui_type)
            if idx >= 0:
                self._ui_type.setCurrentIndex(idx)

            action = correction.get("action", "")
            idx = self._action.findText(action)
            if idx >= 0:
                self._action.setCurrentIndex(idx)

            self._path_input.setText(correction.get("path", ""))
            self._expected_value_input.setText(correction.get("expected_value", ""))

            scroll_cfg = correction.get("scroll_config", {})
            self._scroll_dir_input.setCurrentText(scroll_cfg.get("direction", "down"))
            self._scroll_amount_input.setValue(scroll_cfg.get("amount", 1))

            self._drag_target_input.setText(correction.get("drag_target", ""))

            parent_scroll = correction.get("parent_scroll_area", "")
            idx = self._parent_scroll_input.findText(parent_scroll)
            if idx >= 0:
                self._parent_scroll_input.setCurrentIndex(idx)

            self._requires_scroll_checkbox.setChecked(correction.get("requires_scroll", False))

            # Load choices
            self._choices = list(correction.get("choices", []))
            self._refresh_choices_table()

            # Load navigation
            nav_cfg = correction.get("navigation_config", {})
            if nav_cfg:
                self._is_nav_checkbox.setChecked(True)
                self._target_screen_input.setEditText(nav_cfg.get("target_screen", ""))
            else:
                self._is_nav_checkbox.setChecked(False)

            self._correction_label.setText("⚡ Pré-rempli depuis une correction précédente")
            self._status.setText(f"Source: {source} — corrigé préc.")
        else:
            self._refresh_choices_table()
            self._is_nav_checkbox.setChecked(False)
            self._parent_scroll_input.setCurrentIndex(0) # None
            self._requires_scroll_checkbox.setChecked(False)
            self._correction_label.setText("")
            self._status.setText(f"Source: {source}")

        self._add_btn.setEnabled(True)

    def _confirm(self):
        if self._bbox is None:
            return
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet("border: 1px solid red;")
            return
        self._key_input.setStyleSheet("")

        # Filter choices to those with labels
        valid_choices = [c for c in self._choices if c["label"]]

        from core.mapping_store import build_element
        element = build_element(
            bbox_relative=self._bbox,
            logical_key=key,
            ui_type=self._ui_type.currentText(),
            action=self._action.currentText(),
            path=self._path_input.text().strip(),
            source=self._source,
            expected_value=self._expected_value_input.text().strip(),
            scroll_direction=self._scroll_dir_input.currentText(),
            scroll_amount=self._scroll_amount_input.value(),
            drag_target=self._drag_target_input.text().strip(),
            choices=valid_choices if valid_choices else None,
            navigation_target=self._target_screen_input.currentText().strip() if self._is_nav_checkbox.isChecked() else "",
            parent_scroll_area=self._parent_scroll_input.currentText().strip(),
            requires_scroll=self._requires_scroll_checkbox.isChecked(),
        )
        self.element_confirmed.emit(element)
        self._clear()

    def _clear(self):
        self._bbox = None
        self._source = "human"
        self._prior_correction = None
        self._choices = []
        self._refresh_choices_table()
        self._bbox_label.setText("—")
        self._key_input.clear()
        self._key_input.setStyleSheet("")
        self._ui_type.setCurrentIndex(0)
        self._expected_value_input.clear()
        self._scroll_dir_input.setCurrentIndex(1) # down
        self._scroll_amount_input.setValue(1)
        self._drag_target_input.clear()
        self._path_input.clear()
        self._parent_scroll_input.setCurrentIndex(0)
        self._requires_scroll_checkbox.setChecked(False)
        self._is_nav_checkbox.setChecked(False)
        self._target_screen_input.clearEditText()
        self._correction_label.setText("")
        self._status.setText("Dessine ou clique un élément sur le screenshot")
        self._add_btn.setEnabled(False)
        self._sample_btn.setChecked(False)
        self.sampling_toggled.emit(False)
