"""
MappingList: bottom panel showing the current list of mapped elements.
Supports delete and triggers export.
App/screen context fields have been moved to the main window toolbar.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QFileDialog, QLineEdit, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor


class MappingList(QWidget):
    element_deleted = pyqtSignal(int)
    export_requested = pyqtSignal(str, str, str)  # output_path, app_name, screen_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._elements: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.addWidget(QLabel("🗂 Mapping en cours"))

        self._count_label = QLabel("0 éléments")
        self._count_label.setStyleSheet("color: #aaa;")
        header.addWidget(self._count_label)
        header.addStretch()

        self._export_btn = QPushButton("💾 Exporter JSON")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        self._export_btn.setStyleSheet(
            "QPushButton { background: #1a4f7a; color: white; padding: 5px 10px; border-radius: 4px; }"
            "QPushButton:hover { background: #2a6fa0; }"
            "QPushButton:disabled { background: #333; color: #666; }"
        )
        header.addWidget(self._export_btn)
        layout.addLayout(header)

        # Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["logical_key", "ui_type", "action", "path", "source", "🗑"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(4, 90)
        self._table.setColumnWidth(5, 30)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_element(self, element: dict) -> None:
        """Add a single element, refusing duplicates on logical_key."""
        for existing in self._elements:
            if existing["logical_key"] == element["logical_key"]:
                QMessageBox.warning(
                    self,
                    "Doublon",
                    f"Un élément avec la clé '{element['logical_key']}' existe déjà.\n"
                    "Supprime-le d'abord si tu veux le remplacer.",
                )
                return
        self._elements.append(element)
        self._refresh_table()

    def load_from_elements(self, elements: list[dict]) -> None:
        """
        Restore a full session — replaces the current list entirely.
        No duplicate check: the source (corrections_store) is trusted.
        """
        self._elements = list(elements)
        self._refresh_table()

    def clear_elements(self) -> None:
        """Clear all elements (called when context changes)."""
        self._elements = []
        self._refresh_table()

    def get_elements(self) -> list[dict]:
        return list(self._elements)

    def get_bboxes(self) -> list[dict]:
        return [el["bbox_relative"] for el in self._elements]

    # ------------------------------------------------------------------
    # Export — app/screen names injected from main_window
    # ------------------------------------------------------------------

    def trigger_export(self, app_name: str, screen_name: str) -> None:
        """Called by main_window with the current context."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le mapping", f"{app_name}_{screen_name}.json", "JSON (*.json)"
        )
        if path:
            self.export_requested.emit(path, app_name, screen_name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh_table(self):
        """Rebuild the table from scratch. All delete buttons are recreated
        with correct indices via _make_delete_handler to avoid lambda closure bugs."""
        self._table.setRowCount(0)

        for i, el in enumerate(self._elements):
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(el.get("logical_key", "")))
            self._table.setItem(i, 1, QTableWidgetItem(el.get("ui_type", "")))
            self._table.setItem(i, 2, QTableWidgetItem(el.get("action", "")))
            self._table.setItem(i, 3, QTableWidgetItem(el.get("path", "")))

            source = el.get("source", "human")
            src_item = QTableWidgetItem(source)
            src_item.setForeground(
                QColor("#7ec8e3") if source == "yolo_accepted" else QColor("#a0d4a0")
            )
            self._table.setItem(i, 4, src_item)

            del_btn = QPushButton("✖")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet("color: #cc4444; background: transparent; border: none;")
            del_btn.clicked.connect(self._make_delete_handler(i))
            self._table.setCellWidget(i, 5, del_btn)

        self._count_label.setText(f"{len(self._elements)} élément(s)")
        self._export_btn.setEnabled(len(self._elements) > 0)

    def _make_delete_handler(self, idx: int):
        """Returns a stable closure capturing idx by value."""
        def handler():
            self._delete(idx)
        return handler

    def _delete(self, idx: int) -> None:
        if 0 <= idx < len(self._elements):
            self._elements.pop(idx)
            self._refresh_table()
            self.element_deleted.emit(idx)

    def _export(self) -> None:
        # Delegate to main_window which owns app/screen context
        # This button is kept for direct access; main_window connects it
        self.export_requested.emit("", "", "")