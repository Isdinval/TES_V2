"""
MappingList: bottom panel showing the current list of mapped elements.
Supports delete and triggers export.
App/screen context fields have been moved to the main window toolbar.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QFileDialog, QLineEdit, QMessageBox, QDialog, QComboBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor


class ScrollInstructionDialog(QDialog):
    def __init__(self, scroll_areas: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter une instruction de Scroll")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Zone à scroller :"))
        self.target_combo = QComboBox()
        self.target_combo.addItems(scroll_areas)
        layout.addWidget(self.target_combo)

        layout.addWidget(QLabel("Direction :"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["down", "up", "left", "right"])
        layout.addWidget(self.direction_combo)

        layout.addWidget(QLabel("Quantité (px ou pages) :"))
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(1, 5000)
        self.amount_spin.setValue(1)
        layout.addWidget(self.amount_spin)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Ajouter")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def get_values(self):
        return {
            "target": self.target_combo.currentText(),
            "direction": self.direction_combo.currentText(),
            "amount": self.amount_spin.value()
        }


class MappingList(QWidget):
    element_deleted = pyqtSignal(int)
    export_requested = pyqtSignal(str, str, str)  # output_path, app_name, screen_name
    scroll_instruction_added = pyqtSignal(dict)

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

        self._scroll_instr_btn = QPushButton("📜 Action Scroll")
        self._scroll_instr_btn.clicked.connect(self._add_scroll_instruction)
        self._scroll_instr_btn.setStyleSheet(
            "QPushButton { background: #7a5a1a; color: white; padding: 5px 10px; border-radius: 4px; }"
            "QPushButton:hover { background: #9a7a2a; }"
        )
        header.addWidget(self._scroll_instr_btn)

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
        # Enable editing
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self._table.setAlternatingRowColors(True)
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_element(self, element: dict) -> None:
        """Add a single element, refusing duplicates on logical_key (unless instruction)."""
        if element.get("ui_type") != "instruction":
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
        return [el.get("bbox_relative") for el in self._elements if el.get("bbox_relative")]

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
        """Rebuild the table from scratch."""
        self._table.blockSignals(True)
        self._table.setRowCount(0)

        for i, el in enumerate(self._elements):
            self._table.insertRow(i)

            ui_type = el.get("ui_type", "")
            is_instr = ui_type == "instruction"

            key = el.get("logical_key", "")
            if is_instr:
                key = f"SCROLL: {el.get('parent_scroll_area', '')}"

            key_item = QTableWidgetItem(key)
            if is_instr:
                key_item.setBackground(QColor("#3a3a2a"))
            self._table.setItem(i, 0, key_item)

            type_item = QTableWidgetItem(ui_type)
            if is_instr:
                type_item.setBackground(QColor("#3a3a2a"))
            self._table.setItem(i, 1, type_item)

            action_item = QTableWidgetItem(el.get("action", ""))
            if is_instr:
                action_item.setBackground(QColor("#3a3a2a"))
            self._table.setItem(i, 2, action_item)

            path_item = QTableWidgetItem(el.get("path", ""))
            if is_instr:
                path_item.setBackground(QColor("#3a3a2a"))
            self._table.setItem(i, 3, path_item)

            source = el.get("source", "human")
            src_item = QTableWidgetItem(source)
            src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            src_item.setForeground(
                QColor("#7ec8e3") if source == "yolo_accepted" else QColor("#a0d4a0")
            )
            if is_instr:
                src_item.setBackground(QColor("#3a3a2a"))
            self._table.setItem(i, 4, src_item)

            del_btn = QPushButton("✖")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet("color: #cc4444; background: transparent; border: none;")
            del_btn.clicked.connect(self._make_delete_handler(i))
            self._table.setCellWidget(i, 5, del_btn)

        self._count_label.setText(f"{len(self._elements)} élément(s)")
        self._export_btn.setEnabled(len(self._elements) > 0)
        self._table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()
        if 0 <= row < len(self._elements):
            field_map = {0: "logical_key", 1: "ui_type", 2: "action", 3: "path"}
            field = field_map.get(col)
            if field:
                self._elements[row][field] = item.text().strip()

    def _make_delete_handler(self, idx: int):
        def handler():
            self._delete(idx)
        return handler

    def _delete(self, idx: int) -> None:
        if 0 <= idx < len(self._elements):
            self._elements.pop(idx)
            self._refresh_table()
            self.element_deleted.emit(idx)

    def _add_scroll_instruction(self):
        # Get list of existing scroll areas
        scroll_areas = [el["logical_key"] for el in self._elements if el.get("ui_type") == "scroll_area"]
        if not scroll_areas:
            QMessageBox.warning(self, "Action impossible", "Aucune zone scrollable n'a été mappée.")
            return

        dlg = ScrollInstructionDialog(scroll_areas, self)
        if dlg.exec():
            vals = dlg.get_values()
            from core.mapping_store import build_scroll_instruction
            instr = build_scroll_instruction(
                target_scroll_area=vals["target"],
                direction=vals["direction"],
                amount=vals["amount"]
            )
            self.add_element(instr)
            self.scroll_instruction_added.emit(instr)

    def _export(self) -> None:
        self.export_requested.emit("", "", "")
