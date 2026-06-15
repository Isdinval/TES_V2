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
    scroll_container_requested = pyqtSignal() # user wants to draw scroll container
    scrollbar_target_requested = pyqtSignal() # user wants to click scrollbar point

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bbox: dict | None = None
        self._source: str = "human"
        self._prior_correction: dict | None = None

        self._choices: list[dict] = [] # [{"label": str, "x": float, "y": float, "scroll_steps": int}]
        self._sampling_active = False
        self._scroll_container: dict | None = None
        self._scrollbar_target: dict | None = None
        self._current_scroll_step: int = 0

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
        self._choice_input.returnPressed.connect(self._add_choice)
        h_choices.addWidget(self._choice_input)

        self._add_choice_btn = QPushButton("➕")
        self._add_choice_btn.setFixedWidth(30)
        self._add_choice_btn.clicked.connect(self._add_choice)
        h_choices.addWidget(self._add_choice_btn)
        choices_layout.addLayout(h_choices)

        self._choices_table = QTableWidget(0, 4)
        self._choices_table.setHorizontalHeaderLabels(["Label", "Step", "Cible", "🗑"])
        self._choices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._choices_table.setColumnWidth(1, 40)
        self._choices_table.setColumnWidth(2, 40)
        self._choices_table.setColumnWidth(3, 30)
        self._choices_table.setFixedHeight(120)
        choices_layout.addWidget(self._choices_table)

        # Scroll step controls (inside choices group, visible during sampling)
        self._step_layout = QHBoxLayout()
        self._step_label = QLabel("Scroll Step: 0")
        self._step_layout.addWidget(self._step_label)

        self._step_minus_btn = QPushButton("-1")
        self._step_minus_btn.clicked.connect(lambda: self._change_step(-1))
        self._step_layout.addWidget(self._step_minus_btn)

        self._step_plus_btn = QPushButton("+1")
        self._step_plus_btn.clicked.connect(lambda: self._change_step(1))
        self._step_layout.addWidget(self._step_plus_btn)

        choices_layout.addLayout(self._step_layout)
        self._step_label.setVisible(False)
        self._step_minus_btn.setVisible(False)
        self._step_plus_btn.setVisible(False)

        self._sample_btn = QPushButton("🎯 Enregistrer les points de clic")
        self._sample_btn.setCheckable(True)
        self._sample_btn.clicked.connect(self._toggle_sampling)
        self._sample_btn.setStyleSheet(
            "QPushButton:checked { background: #7a7a20; color: white; }"
        )
        choices_layout.addWidget(self._sample_btn)

        layout.addWidget(self._choices_group)

        # --- Scroll Configuration Section ---
        self._scroll_group = QGroupBox("Configuration du Scroll")
        scroll_layout = QVBoxLayout(self._scroll_group)

        self._is_scrollable_checkbox = QCheckBox("Cet élément nécessite un scroll")
        self._is_scrollable_checkbox.toggled.connect(self._on_scrollable_toggled)
        scroll_layout.addWidget(self._is_scrollable_checkbox)

        self._scroll_buttons_layout = QHBoxLayout()
        self._set_container_btn = QPushButton("📁 Zone de scroll")
        self._set_container_btn.clicked.connect(self.scroll_container_requested.emit)
        self._scroll_buttons_layout.addWidget(self._set_container_btn)

        self._set_scrollbar_btn = QPushButton("🖱 Scrollbar")
        self._set_scrollbar_btn.clicked.connect(self.scrollbar_target_requested.emit)
        self._scroll_buttons_layout.addWidget(self._set_scrollbar_btn)
        scroll_layout.addLayout(self._scroll_buttons_layout)

        # Logical key for scroll container
        self._sc_key_label = QLabel("Clé logique conteneur:")
        self._sc_key_input = QLineEdit()
        self._sc_key_input.setPlaceholderText("Optionnel (auto si vide)")
        scroll_layout.addWidget(self._sc_key_label)
        scroll_layout.addWidget(self._sc_key_input)

        # Scroll params
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("Stratégie:"))
        self._scroll_strategy = QComboBox()
        self._scroll_strategy.addItems(["wheel", "drag_thumb", "click_arrow"])
        params_layout.addWidget(self._scroll_strategy)
        scroll_layout.addLayout(params_layout)

        params_layout2 = QHBoxLayout()
        params_layout2.addWidget(QLabel("Amount:"))
        self._scroll_amount_val = QSpinBox()
        self._scroll_amount_val.setRange(1, 1000)
        self._scroll_amount_val.setValue(120)
        params_layout2.addWidget(self._scroll_amount_val)

        params_layout2.addWidget(QLabel("Max attempts:"))
        self._scroll_max_attempts = QSpinBox()
        self._scroll_max_attempts.setRange(1, 20)
        self._scroll_max_attempts.setValue(8)
        params_layout2.addWidget(self._scroll_max_attempts)
        scroll_layout.addLayout(params_layout2)

        layout.addWidget(self._scroll_group)

        # --- Navigation Section ---
        self._nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout(self._nav_group)
        self._is_nav_checkbox = QCheckBox("Bouton de changement de fiche")
        self._is_nav_checkbox.toggled.connect(self._on_nav_toggled)
        nav_layout.addWidget(self._is_nav_checkbox)

        self._target_screen_label = QLabel("Fiche de destination")
        self._target_screen_input = QComboBox()
        self._target_screen_input.setEditable(True)
        self._target_screen_input.setPlaceholderText("ex: fiche_bilan")
        nav_layout.addWidget(self._target_screen_label)
        nav_layout.addWidget(self._target_screen_input)

        layout.addWidget(self._nav_group)

        # expected_value (fallback simple)
        self._expected_value_label = QLabel("Expected value (simple)")
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setPlaceholderText("ex: France")
        layout.addWidget(self._expected_value_label)
        layout.addWidget(self._expected_value_input)

        # scroll fields (scroll_area type)
        self._scroll_dir_label = QLabel("Scroll Direction")
        self._scroll_dir_input = QComboBox()
        self._scroll_dir_input.addItems(["up", "down", "left", "right"])
        self._scroll_amount_label = QLabel("Scroll Amount")
        self._scroll_amount_input = QSpinBox()
        self._scroll_amount_input.setRange(1, 100)
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
        self._scroll_group.setVisible(is_val_type)
        self._expected_value_label.setVisible(is_val_type)
        self._expected_value_input.setVisible(is_val_type)

        is_scroll_area = ui_type == "scroll_area"
        self._scroll_dir_label.setVisible(is_scroll_area)
        self._scroll_dir_input.setVisible(is_scroll_area)
        self._scroll_amount_label.setVisible(is_scroll_area)
        self._scroll_amount_input.setVisible(is_scroll_area)

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

    def _on_scrollable_toggled(self, checked: bool):
        self._set_container_btn.setVisible(checked)
        self._set_scrollbar_btn.setVisible(checked)
        self._sc_key_label.setVisible(checked)
        self._sc_key_input.setVisible(checked)
        self._scroll_strategy.setVisible(checked)
        self._scroll_amount_val.setVisible(checked)
        self._scroll_max_attempts.setVisible(checked)
        self._update_step_controls_visibility()

    def _change_step(self, delta: int):
        self._current_scroll_step = max(0, self._current_scroll_step + delta)
        self._step_label.setText(f"Scroll Step: {self._current_scroll_step}")

    def _update_step_controls_visibility(self):
        show = self._sampling_active and self._is_scrollable_checkbox.isChecked()
        self._step_label.setVisible(show)
        self._step_minus_btn.setVisible(show)
        self._step_plus_btn.setVisible(show)

    def _add_choice(self):
        txt = self._choice_input.text().strip()
        if not txt:
            return
        self._choices.append({"label": txt, "x": None, "y": None, "scroll_steps": 0})
        self._choice_input.clear()
        self._refresh_choices_table()

    def _refresh_choices_table(self):
        self._choices_table.setRowCount(0)
        for i, c in enumerate(self._choices):
            self._choices_table.insertRow(i)
            self._choices_table.setItem(i, 0, QTableWidgetItem(c["label"]))

            step_item = QTableWidgetItem(str(c.get("scroll_steps", 0)))
            step_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._choices_table.setItem(i, 1, step_item)

            target_status = "✅" if c["x"] is not None else "—"
            item = QTableWidgetItem(target_status)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._choices_table.setItem(i, 2, item)

            del_btn = QPushButton("✖")
            del_btn.setFixedWidth(24)
            del_btn.setStyleSheet("color: #cc4444; background: transparent; border: none;")
            del_btn.clicked.connect(self._make_delete_choice_handler(i))
            self._choices_table.setCellWidget(i, 3, del_btn)

    def _make_delete_choice_handler(self, idx: int):
        def handler():
            if 0 <= idx < len(self._choices):
                self._choices.pop(idx)
                self._refresh_choices_table()
        return handler

    def _toggle_sampling(self, checked: bool):
        self._sampling_active = checked
        self.sampling_toggled.emit(checked)
        self._update_step_controls_visibility()
        if checked:
            self._status.setText("Mode cible : clique sur le screenshot pour chaque option")
        else:
            self._status.setText(f"Source: {self._source}")

    def add_sampled_point(self, point: dict):
        """Called from outside when a point is clicked on canvas."""
        for c in self._choices:
            if c["x"] is None:
                c["x"] = point["x"]
                c["y"] = point["y"]
                if self._is_scrollable_checkbox.isChecked():
                    c["scroll_steps"] = self._current_scroll_step
                self._refresh_choices_table()
                break

        if all(c["x"] is not None for c in self._choices):
            self._sample_btn.setChecked(False)
            self._toggle_sampling(False)

    def set_scroll_container(self, bbox: dict):
        self._scroll_container = bbox
        self._status.setText("Zone de scroll définie ✅")

    def set_scrollbar_target(self, point: dict):
        self._scrollbar_target = point
        self._status.setText("Scrollbar définie ✅")

    def get_sampled_points(self) -> list[dict]:
        return [{"x": c["x"], "y": c["y"]} for c in self._choices if c["x"] is not None]

    def set_screen_suggestions(self, screens: list[str]):
        current = self._target_screen_input.currentText()
        self._target_screen_input.clear()
        self._target_screen_input.addItems(screens)
        self._target_screen_input.setEditText(current)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_bbox(self, bbox: dict, source: str = "human", correction: dict | None = None) -> None:
        """Called when user selects or draws a bbox."""
        self._bbox = bbox
        self._source = source
        self._prior_correction = correction
        self._choices = []
        self._scroll_container = None
        self._scrollbar_target = None
        self._current_scroll_step = 0
        self._step_label.setText("Scroll Step: 0")
        self._sc_key_input.clear()

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

            is_scrollable = correction.get("is_scrollable", False)
            self._is_scrollable_checkbox.setChecked(is_scrollable)
            if is_scrollable:
                self._scroll_strategy.setCurrentText(scroll_cfg.get("strategy", "wheel"))
                self._scroll_amount_val.setValue(scroll_cfg.get("amount", 120))
                self._scroll_max_attempts.setValue(scroll_cfg.get("max_attempts", 8))
                self._scroll_container = correction.get("scroll_container")
                if self._scroll_container:
                    self._sc_key_input.setText(self._scroll_container.get("logical_key", ""))
                self._scrollbar_target = correction.get("scrollbar_target")

            self._choices = list(correction.get("choices", []))
            self._refresh_choices_table()

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
            self._is_scrollable_checkbox.setChecked(False)
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

        valid_choices = [c for c in self._choices if c["label"]]
        is_scrollable = self._is_scrollable_checkbox.isChecked()
        ui_type = self._ui_type.currentText()

        sc_data = None
        if is_scrollable and self._scroll_container:
            sc_data = self._scroll_container.copy()
            custom_sc_key = self._sc_key_input.text().strip()
            sc_data["logical_key"] = custom_sc_key if custom_sc_key else f"{key}_scroll_container"

        from core.mapping_store import build_element
        element = build_element(
            bbox_relative=self._bbox,
            logical_key=key,
            ui_type=ui_type,
            action=self._action.currentText(),
            path=self._path_input.text().strip(),
            source=self._source,
            expected_value=self._expected_value_input.text().strip(),
            scroll_direction=self._scroll_dir_input.currentText(),
            scroll_amount=self._scroll_amount_val.value() if is_scrollable else self._scroll_amount_input.value(),
            drag_target=self._drag_target_input.text().strip(),
            choices=valid_choices if valid_choices else None,
            navigation_target=self._target_screen_input.currentText().strip() if self._is_nav_checkbox.isChecked() else "",
            is_scrollable=is_scrollable,
            scroll_container=sc_data,
            scroll_strategy=self._scroll_strategy.currentText(),
            scroll_max_attempts=self._scroll_max_attempts.value(),
            scrollbar_target=self._scrollbar_target,
        )
        self.element_confirmed.emit(element)
        self._clear()

    def _clear(self):
        self._bbox = None
        self._source = "human"
        self._prior_correction = None
        self._choices = []
        self._scroll_container = None
        self._scrollbar_target = None
        self._current_scroll_step = 0
        self._refresh_choices_table()
        self._bbox_label.setText("—")
        self._key_input.clear()
        self._key_input.setStyleSheet("")
        self._ui_type.setCurrentIndex(0)
        self._expected_value_input.clear()
        self._scroll_dir_input.setCurrentIndex(1) # down
        self._scroll_amount_input.setValue(1)
        self._scroll_amount_val.setValue(120)
        self._scroll_max_attempts.setValue(8)
        self._drag_target_input.clear()
        self._sc_key_input.clear()
        self._path_input.clear()
        self._is_nav_checkbox.setChecked(False)
        self._is_scrollable_checkbox.setChecked(False)
        self._target_screen_input.clearEditText()
        self._correction_label.setText("")
        self._status.setText("Dessine ou clique un élément sur le screenshot")
        self._add_btn.setEnabled(False)
        self._sample_btn.setChecked(False)
        self.sampling_toggled.emit(False)
        self._step_label.setText("Scroll Step: 0")
        self._update_step_controls_visibility()
