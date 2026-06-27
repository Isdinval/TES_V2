from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLabel,
                             QLineEdit, QTextEdit, QPushButton, QGroupBox)
from PyQt6.QtCore import pyqtSignal
from core.element import UIElement
import json

class ElementInfoPanel(QWidget):
    export_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Info Group
        self.group = QGroupBox("Element Info")
        self.form_layout = QFormLayout(self.group)

        self.name_edit = QLineEdit()
        self.auto_id_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.class_edit = QLineEdit()
        self.rect_edit = QLineEdit()
        self.value_edit = QLineEdit()

        for edit in [self.name_edit, self.auto_id_edit, self.type_edit,
                     self.class_edit, self.rect_edit, self.value_edit]:
            edit.setReadOnly(True)

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("AutomationId:", self.auto_id_edit)
        self.form_layout.addRow("ControlType:", self.type_edit)
        self.form_layout.addRow("ClassName:", self.class_edit)
        self.form_layout.addRow("Rectangle:", self.rect_edit)
        self.form_layout.addRow("Value:", self.value_edit)

        self.layout.addWidget(self.group)

        # Export Button
        self.export_btn = QPushButton("Export to JSON")
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.layout.addWidget(self.export_btn)

        self.layout.addStretch()

    def update_info(self, element: UIElement):
        if not element:
            self.clear_info()
            return

        self.name_edit.setText(element.name)
        self.auto_id_edit.setText(element.automation_id)
        self.type_edit.setText(element.control_type)
        self.class_edit.setText(element.class_name)
        self.rect_edit.setText(str(element.rectangle))
        self.value_edit.setText(element.value if element.value else "")

    def clear_info(self):
        self.name_edit.clear()
        self.auto_id_edit.clear()
        self.type_edit.clear()
        self.class_edit.clear()
        self.rect_edit.clear()
        self.value_edit.clear()
