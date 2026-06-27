import os
import json
import time
import win32gui
import win32api
import win32con
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QLabel, QProgressBar, QFileDialog,
                             QMessageBox, QApplication, QLineEdit, QFormLayout)
from PyQt6.QtGui import QPixmap, QImage, QCursor
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PIL import Image

from ui.canvas_view import CanvasView
from ui.element_info_panel import ElementInfoPanel
from ui.element_form import ElementForm
from core.window_selector import WindowSelector
from core.uia_scanner import UIAScanner
from core.mapping_store import MappingStore

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TES V2 - UIA Mapper")
        self.resize(1400, 900)

        self.scanner = UIAScanner()
        self.mapping_store = MappingStore()
        self.selected_handle = None
        self.is_selecting_window = False
        self.last_lbutton_state = False
        self.window_title = ""

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: Toolbar + Canvas
        left_layout = QVBoxLayout()

        # Context bar
        context_layout = QHBoxLayout()
        self.app_name_edit = QLineEdit("MyApp")
        self.screen_name_edit = QLineEdit("MainScreen")
        context_layout.addWidget(QLabel("App:"))
        context_layout.addWidget(self.app_name_edit)
        context_layout.addWidget(QLabel("Screen:"))
        context_layout.addWidget(self.screen_name_edit)

        self.load_btn = QPushButton("Load Existing")
        self.load_btn.clicked.connect(self._on_load_mapping)
        context_layout.addWidget(self.load_btn)

        left_layout.addLayout(context_layout)

        toolbar = QHBoxLayout()
        self.select_btn = QPushButton("Select Window")
        self.select_btn.clicked.connect(self._start_window_selection)
        toolbar.addWidget(self.select_btn)

        self.show_all_cb = QCheckBox("Show All")
        toolbar.addWidget(self.show_all_cb)

        self.status_label = QLabel("Ready")
        toolbar.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        toolbar.addWidget(self.progress)

        left_layout.addLayout(toolbar)

        self.canvas = CanvasView()
        self.canvas.element_selected.connect(self._on_element_selected)
        left_layout.addWidget(self.canvas)

        main_layout.addLayout(left_layout, stretch=4)

        # Right side: Form + Info
        right_layout = QVBoxLayout()

        self.element_form = ElementForm()
        self.element_form.element_updated.connect(self._on_element_updated)
        right_layout.addWidget(self.element_form)

        self.info_panel = ElementInfoPanel()
        self.info_panel.export_requested.connect(self._on_export_requested)
        right_layout.addWidget(self.info_panel)

        main_layout.addLayout(right_layout, stretch=1)

        self.selection_timer = QTimer()
        self.selection_timer.timeout.connect(self._poll_mouse_for_window)

    def _start_window_selection(self):
        self.is_selecting_window = True
        self.select_btn.setEnabled(False)
        self.select_btn.setText("Click target...")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.last_lbutton_state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
        self.selection_timer.start(50)

    def _poll_mouse_for_window(self):
        current_lbutton_state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
        if current_lbutton_state and not self.last_lbutton_state:
            self.selection_timer.stop()
            self.selected_handle = WindowSelector.get_window_at_mouse()
            self._finish_selection()
        self.last_lbutton_state = current_lbutton_state

    def _finish_selection(self):
        self.is_selecting_window = False
        self.select_btn.setEnabled(True)
        self.select_btn.setText("Select Window")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.selected_handle:
            time.sleep(0.2)
            info = WindowSelector.get_window_info(self.selected_handle)
            self.window_title = info.get('title', 'Unknown')
            self.status_label.setText(f"Window: {self.window_title}")
            self._run_scan()

    def _run_scan(self):
        if not self.selected_handle: return
        self.progress.setVisible(True)
        self.status_label.setText("Scanning...")
        QApplication.processEvents()

        screenshot, rect = self.scanner.capture_window(self.selected_handle)
        if screenshot:
            qimage = self._pil_to_qimage(screenshot)
            self.canvas.set_screenshot(QPixmap.fromImage(qimage), rect)

        elements = self.scanner.scan(self.selected_handle, self.show_all_cb.isChecked())

        # Merge with existing mapping if any
        mapping = self.mapping_store.load_mapping(self.app_name_edit.text(), self.screen_name_edit.text())
        if mapping:
            elements = self.mapping_store.merge_with_scanned_elements(elements, mapping)

        self.canvas.set_elements(elements)
        self.status_label.setText(f"Done: {len(elements)} elements ({self.scanner.backend})")
        self.progress.setVisible(False)

    def _pil_to_qimage(self, pil_img):
        if pil_img.mode != "RGB": pil_img = pil_img.convert("RGB")
        data = pil_img.tobytes("raw", "RGB")
        return QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGB888)

    def _on_element_selected(self, element):
        self.element_form.set_element(element)
        self.info_panel.update_info(element)

    def _on_element_updated(self, element):
        # Auto save to store when an element is updated? Or wait for export?
        # Let's auto-save to the screen file to be robust.
        self._on_export_requested(silent=True)
        self.canvas.update()

    def _on_load_mapping(self):
        if self.selected_handle:
            self._run_scan()
        else:
            QMessageBox.warning(self, "Load", "Select a window first to apply mapping.")

    def _on_export_requested(self, silent=False):
        if not self.canvas.elements: return

        app_name = self.app_name_edit.text().strip()
        screen_name = self.screen_name_edit.text().strip()

        if not app_name or not screen_name:
            if not silent: QMessageBox.warning(self, "Export", "App Name and Screen Name are required.")
            return

        resolution = (win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN))

        file_path = self.mapping_store.save_mapping(
            app_name, screen_name, self.scanner.backend, self.window_title, self.canvas.elements, resolution
        )

        if not silent:
            QMessageBox.information(self, "Export", f"Mapping saved to {file_path}")
