"""
ElementForm: right-side panel where the human fills in metadata
for the selected/drawn bbox.
Emits element_confirmed with a complete element dict.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QGroupBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


UI_TYPES = [
    "text_input",
    "button",
    "checkbox",
    "radio",
    "dropdown",
    "label",
    "icon",
    "tab",
    "menu_item",
    "toggle",
    "date_picker",
    "table_cell",
    "other",
]

ACTIONS = [
    "click",
    "click_then_type",
    "double_click",
    "right_click",
    "check",
    "uncheck",
    "select",
    "hover",
    "scroll",
    "drag",
    "none",
]


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
        layout.addWidget(self._ui_type)

        # action
        layout.addWidget(QLabel("Action *"))
        self._action = QComboBox()
        self._action.addItems(ACTIONS)
        layout.addWidget(self._action)

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
            idx = self._ui_type.findText(correction.get("ui_type", ""))
            if idx >= 0:
                self._ui_type.setCurrentIndex(idx)
            idx = self._action.findText(correction.get("action", ""))
            if idx >= 0:
                self._action.setCurrentIndex(idx)
            self._path_input.setText(correction.get("path", ""))
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
        self._action.setCurrentIndex(0)
        self._path_input.clear()
        self._correction_label.setText("")
        self._status.setText("Dessine ou clique un élément sur le screenshot")
        self._add_btn.setEnabled(False)
