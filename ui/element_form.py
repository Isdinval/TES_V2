"""
ElementForm: right-side panel where the human fills in metadata
for the selected/drawn bbox.
Emits element_confirmed with a complete element dict.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QGroupBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bbox: dict | None = None
        self._source: str = "human"
        self._prior_correction: dict | None = None
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

        # expected_value (dropdown / radio / checkbox)
        self._expected_value_label = QLabel("Expected value")
        self._expected_value_input = QLineEdit()
        self._expected_value_input.setPlaceholderText("ex: France ou true")
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_bbox(self, bbox: dict, source: str = "human", correction: dict | None = None) -> None:
        """Called when user selects or draws a bbox."""
        self._bbox = bbox
        self._source = source
        self._prior_correction = correction

        b = bbox
        self._bbox_label.setText(
            f"x={b['x']:.3f}  y={b['y']:.3f}  w={b['w']:.3f}  h={b['h']:.3f}"
        )

        if correction:
            # Pre-fill from corrections_store
            self._key_input.setText(correction.get("logical_key", ""))

            ui_type = correction.get("ui_type", "")
            idx = self._ui_type.findText(ui_type)
            if idx >= 0:
                self._ui_type.setCurrentIndex(idx)

            # Action list is already updated by _on_ui_type_changed via setCurrentIndex above
            action = correction.get("action", "")
            idx = self._action.findText(action)
            if idx >= 0:
                self._action.setCurrentIndex(idx)

            self._path_input.setText(correction.get("path", ""))

            # Additional fields
            self._expected_value_input.setText(correction.get("expected_value", ""))

            scroll_cfg = correction.get("scroll_config", {})
            self._scroll_dir_input.setCurrentText(scroll_cfg.get("direction", "down"))
            self._scroll_amount_input.setValue(scroll_cfg.get("amount", 1))

            self._drag_target_input.setText(correction.get("drag_target", ""))

            self._correction_label.setText("⚡ Pré-rempli depuis une correction précédente")
            self._status.setText(f"Source: {source} — corrigé préc.")
        else:
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
        )
        self.element_confirmed.emit(element)
        self._clear()

    def _clear(self):
        self._bbox = None
        self._source = "human"
        self._prior_correction = None
        self._bbox_label.setText("—")
        self._key_input.clear()
        self._key_input.setStyleSheet("")
        self._ui_type.setCurrentIndex(0)
        # _on_ui_type_changed will reset action and other fields visibility
        self._expected_value_input.clear()
        self._scroll_dir_input.setCurrentIndex(1) # down
        self._scroll_amount_input.setValue(1)
        self._drag_target_input.clear()
        self._path_input.clear()
        self._correction_label.setText("")
        self._status.setText("Dessine ou clique un élément sur le screenshot")
        self._add_btn.setEnabled(False)
