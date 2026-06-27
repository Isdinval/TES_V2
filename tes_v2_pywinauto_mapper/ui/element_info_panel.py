from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QPushButton, QGroupBox, QTextEdit)
from PyQt6.QtCore import pyqtSignal
from core.element import UIElement

class ElementInfoPanel(QWidget):
    export_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.group = QGroupBox("Technical Details")
        self.form_layout = QFormLayout(self.group)

        self.auto_id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.class_edit = QLineEdit()
        self.framework_edit = QLineEdit()
        self.rect_edit = QLineEdit()
        self.patterns_edit = QTextEdit()
        self.patterns_edit.setMaximumHeight(60)

        for edit in [self.auto_id_edit, self.name_edit, self.type_edit,
                     self.class_edit, self.framework_edit, self.rect_edit]:
            edit.setReadOnly(True)
        self.patterns_edit.setReadOnly(True)

        self.form_layout.addRow("AutomationId:", self.auto_id_edit)
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("ControlType:", self.type_edit)
        self.form_layout.addRow("ClassName:", self.class_edit)
        self.form_layout.addRow("FrameworkId:", self.framework_edit)
        self.form_layout.addRow("Rectangle:", self.rect_edit)
        self.form_layout.addRow("Patterns:", self.patterns_edit)

        self.layout.addWidget(self.group)

        self.export_btn = QPushButton("Save All Mappings")
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.layout.addWidget(self.export_btn)

        self.layout.addStretch()

    def update_info(self, element: UIElement):
        if not element:
            self.clear_info()
            return

        self.auto_id_edit.setText(element.automation_id)
        self.name_edit.setText(element.name)
        self.type_edit.setText(element.control_type)
        self.class_edit.setText(element.class_name)
        self.framework_edit.setText(element.framework_id)
        self.rect_edit.setText(str(element.rectangle))
        self.patterns_edit.setText(", ".join(element.patterns))

    def clear_info(self):
        self.auto_id_edit.clear()
        self.name_edit.clear()
        self.type_edit.clear()
        self.class_edit.clear()
        self.framework_edit.clear()
        self.rect_edit.clear()
        self.patterns_edit.clear()
