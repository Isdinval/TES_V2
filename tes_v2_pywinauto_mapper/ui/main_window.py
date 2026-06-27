import os
import json
import time
import win32gui
import win32api
import win32con
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QLabel, QProgressBar, QFileDialog, QMessageBox, QApplication)
from PyQt6.QtGui import QPixmap, QImage, QCursor
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PIL import Image

from .canvas_view import CanvasView
from .element_info_panel import ElementInfoPanel
from core.window_selector import WindowSelector
from core.uia_scanner import UIAScanner

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UIA Mapper Prototype")
        self.resize(1200, 800)

        self.scanner = UIAScanner()
        self.selected_handle = None
        self.is_selecting_window = False
        self.last_lbutton_state = False

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: Toolbar + Canvas
        left_layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        self.select_btn = QPushButton("Select Window (Target)")
        self.select_btn.clicked.connect(self._start_window_selection)
        toolbar.addWidget(self.select_btn)

        self.show_all_cb = QCheckBox("Show All Elements")
        toolbar.addWidget(self.show_all_cb)

        self.status_label = QLabel("Ready")
        toolbar.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        toolbar.addWidget(self.progress)

        left_layout.addLayout(toolbar)

        self.canvas = CanvasView()
        self.canvas.element_hovered.connect(self._on_element_hovered)
        self.canvas.element_selected.connect(self._on_element_selected)
        left_layout.addWidget(self.canvas)

        main_layout.addLayout(left_layout, stretch=3)

        # Right side: Info Panel
        self.info_panel = ElementInfoPanel()
        self.info_panel.export_requested.connect(self._on_export_requested)
        main_layout.addWidget(self.info_panel, stretch=1)

        # Selection Timer
        self.selection_timer = QTimer()
        self.selection_timer.timeout.connect(self._poll_mouse_for_window)

    def _start_window_selection(self):
        self.is_selecting_window = True
        self.select_btn.setEnabled(False)
        self.select_btn.setText("Click on target window...")
        self.setCursor(Qt.CursorShape.CrossCursor)
        # Wait a bit so the click on this button is ignored
        self.last_lbutton_state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
        self.selection_timer.start(50)

    def _poll_mouse_for_window(self):
        current_lbutton_state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000

        # We look for a transition from UP to DOWN
        if current_lbutton_state and not self.last_lbutton_state:
            # Check if we clicked on our own window?
            # Actually, the user wants to click the target window.
            # If they click our window, it will select it, which is fine for testing.
            self.selection_timer.stop()
            self.selected_handle = WindowSelector.get_window_at_mouse()
            self._finish_selection()

        self.last_lbutton_state = current_lbutton_state

    def _finish_selection(self):
        self.is_selecting_window = False
        self.select_btn.setEnabled(True)
        self.select_btn.setText("Select Window (Target)")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.selected_handle:
            # Small delay to let the click finish so it doesn't interact with the app immediately
            time.sleep(0.2)
            info = WindowSelector.get_window_info(self.selected_handle)
            self.status_label.setText(f"Selected: {info.get('title', 'Unknown')}")
            self._run_scan()

    def _run_scan(self):
        if not self.selected_handle:
            return

        self.progress.setVisible(True)
        self.status_label.setText("Scanning...")
        # Force UI update
        QApplication.processEvents()

        # Capture
        screenshot, rect = self.scanner.capture_window(self.selected_handle)
        if screenshot:
            qimage = self._pil_to_qimage(screenshot)
            pixmap = QPixmap.fromImage(qimage)
            self.canvas.set_screenshot(pixmap, rect)

        # Scan
        elements = self.scanner.scan(self.selected_handle, self.show_all_cb.isChecked())
        self.canvas.set_elements(elements)

        self.status_label.setText(f"Done ({len(elements)} elements found via {self.scanner.backend})")
        self.progress.setVisible(False)

    def _pil_to_qimage(self, pil_img):
        if pil_img.mode == "RGB":
            data = pil_img.tobytes("raw", "RGB")
            format = QImage.Format.Format_RGB888
        elif pil_img.mode == "RGBA":
            data = pil_img.tobytes("raw", "RGBA")
            format = QImage.Format.Format_RGBA8888
        else:
            pil_img = pil_img.convert("RGB")
            data = pil_img.tobytes("raw", "RGB")
            format = QImage.Format.Format_RGB888

        return QImage(data, pil_img.size[0], pil_img.size[1], format)

    def _on_element_hovered(self, element):
        if element:
            self.status_label.setText(f"Hover: {element.control_type} - {element.name}")

    def _on_element_selected(self, element):
        self.info_panel.update_info(element)

    def _on_export_requested(self):
        if not self.canvas.elements:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if path:
            data = {
                "window_title": self.status_label.text(),
                "backend_used": self.scanner.backend,
                "elements": [el.to_dict() for el in self.canvas.elements]
            }
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Export", f"Exported {len(self.canvas.elements)} elements to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
