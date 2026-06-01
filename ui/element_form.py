"""
ElementForm: right-side panel where the human fills in metadata
for the selected/drawn bbox.
Emits element_confirmed with a complete element dict.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
    QComboBox, QPushButton, QFrame, QGroupBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor
=======
    QComboBox, QPushButton, QFrame, QGroupBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
>>>>>>> main


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

<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
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

        self._choices_table = QTableWidget(0, 3)
        self._choices_table.setHorizontalHeaderLabels(["Label", "Cible", "🗑"])
        self._choices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._choices_table.setColumnWidth(1, 40)
        self._choices_table.setColumnWidth(2, 30)
        self._choices_table.setFixedHeight(120)
        choices_layout.addWidget(self._choices_table)

        self._sample_btn = QPushButton("🎯 Enregistrer les points de clic")
        self._sample_btn.setCheckable(True)
        self._sample_btn.clicked.connect(self._toggle_sampling)
        self._sample_btn.setStyleSheet(
            "QPushButton:checked { background: #7a7a20; color: white; }"
        )
        choices_layout.addWidget(self._sample_btn)

        layout.addWidget(self._choices_group)

        # expected_value (fallback simple)
        self._expected_value_label = QLabel("Expected value (simple)")
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setPlaceholderText("ex: France")
=======
        # expected_value (dropdown / radio / checkbox)
        self._expected_value_label = QLabel("Expected value")
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setPlaceholderText("ex: France ou true")
>>>>>>> main
        layout.addWidget(self._expected_value_label)
        layout.addWidget(self._expected_value_input)

        # scroll fields (scroll_area)
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
<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
        self._choices_group.setVisible(is_val_type)
=======
>>>>>>> main
        self._expected_value_label.setVisible(is_val_type)
        self._expected_value_input.setVisible(is_val_type)

        is_scroll = ui_type == "scroll_area"
        self._scroll_dir_label.setVisible(is_scroll)
        self._scroll_dir_input.setVisible(is_scroll)
        self._scroll_amount_label.setVisible(is_scroll)
        self._scroll_amount_input.setVisible(is_scroll)

        is_drag = ui_type == "drag_handle"
        self._drag_target_label.setVisible(is_drag)
        self._drag_target_input.setVisible(is_drag)

<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
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

=======
>>>>>>> main
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

<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
=======
            # Action list is already updated by _on_ui_type_changed via setCurrentIndex above
>>>>>>> main
            action = correction.get("action", "")
            idx = self._action.findText(action)
            if idx >= 0:
                self._action.setCurrentIndex(idx)

            self._path_input.setText(correction.get("path", ""))
<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
=======

            # Additional fields
>>>>>>> main
            self._expected_value_input.setText(correction.get("expected_value", ""))

            scroll_cfg = correction.get("scroll_config", {})
            self._scroll_dir_input.setCurrentText(scroll_cfg.get("direction", "down"))
            self._scroll_amount_input.setValue(scroll_cfg.get("amount", 1))

            self._drag_target_input.setText(correction.get("drag_target", ""))

<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
            # Load choices
            self._choices = list(correction.get("choices", []))
            self._refresh_choices_table()

=======
>>>>>>> main
            self._correction_label.setText("⚡ Pré-rempli depuis une correction précédente")
            self._status.setText(f"Source: {source} — corrigé préc.")
        else:
            self._refresh_choices_table()
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
<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
            choices=valid_choices if valid_choices else None,
=======
>>>>>>> main
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
<<<<<<< feature/ui-mapping-enhancements-10846057040124289619
=======
        # _on_ui_type_changed will reset action and other fields visibility
>>>>>>> main
        self._expected_value_input.clear()
        self._scroll_dir_input.setCurrentIndex(1) # down
        self._scroll_amount_input.setValue(1)
        self._drag_target_input.clear()
        self._path_input.clear()
        self._correction_label.setText("")
        self._status.setText("Dessine ou clique un élément sur le screenshot")
        self._add_btn.setEnabled(False)
        self._sample_btn.setChecked(False)
        self.sampling_toggled.emit(False)
