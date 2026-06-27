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
        self.toggle_state_edit = QLineEdit()
        self.choices_edit = QLineEdit()

        for edit in [self.auto_id_edit, self.name_edit, self.type_edit,
                     self.class_edit, self.framework_edit, self.rect_edit,
                     self.toggle_state_edit, self.choices_edit]:
            edit.setReadOnly(True)
        self.patterns_edit.setReadOnly(True)

        self.form_layout.addRow("AutomationId:", self.auto_id_edit)
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("ControlType:", self.type_edit)
        self.form_layout.addRow("ClassName:", self.class_edit)
        self.form_layout.addRow("FrameworkId:", self.framework_edit)
        self.form_layout.addRow("Rectangle:", self.rect_edit)
        self.form_layout.addRow("Patterns:", self.patterns_edit)
        self.form_layout.addRow("Toggle State:", self.toggle_state_edit)
        self.form_layout.addRow("Choices:", self.choices_edit)

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

        # P1-C: Display toggle_state and choices count
        if element.toggle_state:
            self.toggle_state_edit.setText(element.toggle_state)
            self.toggle_state_edit.setVisible(True)
            self.form_layout.labelForField(self.toggle_state_edit).setVisible(True)
        else:
            self.toggle_state_edit.setVisible(False)
            self.form_layout.labelForField(self.toggle_state_edit).setVisible(False)

        if element.choices:
            self.choices_edit.setText(f"{len(element.choices)} items detected")
            self.choices_edit.setVisible(True)
            self.form_layout.labelForField(self.choices_edit).setVisible(True)
        else:
            self.choices_edit.setVisible(False)
            self.form_layout.labelForField(self.choices_edit).setVisible(False)

    def clear_info(self):
        self.auto_id_edit.clear()
        self.name_edit.clear()
        self.type_edit.clear()
        self.class_edit.clear()
        self.framework_edit.clear()
        self.rect_edit.clear()
        self.patterns_edit.clear()
        self.toggle_state_edit.clear()
        self.choices_edit.clear()
