import os
import json
import time
import win32gui
import win32api
import win32con
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QLabel, QProgressBar, QFileDialog,
                             QMessageBox, QApplication, QLineEdit, QFormLayout, QSplitter)
from PyQt6.QtGui import QPixmap, QImage, QCursor
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QRect, QSettings
from PIL import Image

from ui.canvas_view import CanvasView
from ui.element_info_panel import ElementInfoPanel
from ui.element_form import ElementForm
from core.window_selector import WindowSelector
from core.uia_scanner import UIAScanner
from core.mapping_store import MappingStore
from core.element import UIElement

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
        self.ref_resolution = [1920, 1080] # Default

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Main horizontal splitter: [left area | right panels]
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Toolbar + Canvas
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

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

        self.group_mode_btn = QPushButton("Map as Group")
        self.group_mode_btn.setCheckable(True)
        self.group_mode_btn.toggled.connect(self._on_group_mode_toggled)
        toolbar.addWidget(self.group_mode_btn)

        self.status_label = QLabel("Ready")
        toolbar.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        toolbar.addWidget(self.progress)

        left_layout.addLayout(toolbar)

        self.canvas = CanvasView()
        self.canvas.element_selected.connect(self._on_element_selected)
        self.canvas.group_zone_selected.connect(self._on_group_zone_selected)
        left_layout.addWidget(self.canvas)

        self.h_splitter.addWidget(left_widget)

        # Right: vertical splitter with form on top, info panel below
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)

        self.element_form = ElementForm()
        self.element_form.element_updated.connect(self._on_element_updated)
        self.element_form.setMinimumHeight(200)
        self.v_splitter.addWidget(self.element_form)

        self.info_panel = ElementInfoPanel()
        self.info_panel.export_requested.connect(self._on_export_requested)
        self.info_panel.setMinimumHeight(80)
        self.v_splitter.addWidget(self.info_panel)

        self.v_splitter.setSizes([400, 300])
        self.v_splitter.setCollapsible(0, False)
        self.v_splitter.setCollapsible(1, True)

        self.h_splitter.addWidget(self.v_splitter)

        # Initial proportions: canvas gets 75%, right panels get 25%
        self.h_splitter.setSizes([1050, 350])
        self.h_splitter.setCollapsible(0, False)
        self.h_splitter.setCollapsible(1, False)

        outer_layout.addWidget(self.h_splitter)
        settings = QSettings("TES_V2", "UIA_Mapper")
        if settings.value("h_splitter"):
            self.h_splitter.restoreState(settings.value("h_splitter"))
        if settings.value("v_splitter"):
            self.v_splitter.restoreState(settings.value("v_splitter"))

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

            # Update ref_resolution from current screen
            self.ref_resolution = [
                win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            ]

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

        for el in elements:
            el.ref_resolution = self.ref_resolution

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
        self._on_export_requested(silent=True)
        self.canvas.update()

    def _on_load_mapping(self):
        if self.selected_handle:
            self._run_scan()
        else:
            QMessageBox.warning(self, "Load", "Select a window first to apply mapping.")

    def _on_group_mode_toggled(self, enabled):
        self.canvas.enable_drag_mode(enabled)

    def _on_group_zone_selected(self, zone_rect: QRect):
        # zone_rect is in canvas local coordinates (relative to window_rect[0,1])
        if not self.canvas.window_rect: return

        # Convert zone_rect to global coordinates
        wx, wy, ww, wh = self.canvas.window_rect
        global_zone_x1 = zone_rect.left() + wx
        global_zone_y1 = zone_rect.top() + wy
        global_zone_x2 = zone_rect.right() + wx
        global_zone_y2 = zone_rect.bottom() + wy

        members = []
        for el in self.canvas.elements:
            el_x1 = el.rectangle[0]
            el_y1 = el.rectangle[1]
            el_x2 = el.rectangle[0] + el.rectangle[2]
            el_y2 = el.rectangle[1] + el.rectangle[3]

            # Overlap check
            if el_x1 < global_zone_x2 and el_x2 > global_zone_x1 and                el_y1 < global_zone_y2 and el_y2 > global_zone_y1:
                members.append(el)

        if len(members) < 2:
            QMessageBox.information(self, "Group Selection", "Select a zone containing at least 2 elements.")
            self.group_mode_btn.setChecked(False)
            return

        # Detect predominant type
        types_in_zone = [m.control_type for m in members]
        if all(t == "RadioButton" for t in types_in_zone):
            proposed_ui_type = "radio_group"
            proposed_action = "select_by_label"
        elif all(t == "CheckBox" for t in types_in_zone):
            proposed_ui_type = "checkbox_group"
            proposed_action = "check_by_label"
        elif all(t == "TabItem" for t in types_in_zone):
            proposed_ui_type = "tab_bar"
            proposed_action = "click_by_label"
        else:
            proposed_ui_type = "radio_group"
            proposed_action = "select_by_label"

        # Build group bounding box (union of members)
        left   = min(m.rectangle[0] for m in members)
        top    = min(m.rectangle[1] for m in members)
        right  = max(m.rectangle[0] + m.rectangle[2] for m in members)
        bottom = max(m.rectangle[1] + m.rectangle[3] for m in members)

        rw, rh = self.ref_resolution
        choices = []
        for m in members:
            cx = m.rectangle[0] + m.rectangle[2] / 2
            cy = m.rectangle[1] + m.rectangle[3] / 2
            choices.append({
                "label": m.name or m.logical_key or f"option_{len(choices)}",
                "x": round(cx / rw, 6),
                "y": round(cy / rh, 6),
                "stable_id": m.automation_id or f"{m.name}_{m.control_type}"
            })

        group_el = UIElement(
            name="",
            automation_id="",
            control_type=proposed_ui_type,
            class_name="",
            framework_id="",
            rectangle=[left, top, right - left, bottom - top],
            is_enabled=True,
            is_visible=True,
            ui_type=proposed_ui_type,
            action=proposed_action,
            logical_key="",
            choices=choices,
            supported_patterns=[],
            execution_hint="pyautogui_fallback",
        )
        group_el.ref_resolution = self.ref_resolution

        self.canvas.elements.append(group_el)
        self.canvas.add_group_overlay(group_el)
        self.element_form.set_element(group_el)
        self.group_mode_btn.setChecked(False)

    def _on_export_requested(self, silent=False):
        if not self.canvas.elements: return

        app_name = self.app_name_edit.text().strip()
        screen_name = self.screen_name_edit.text().strip()

        if not app_name or not screen_name:
            if not silent: QMessageBox.warning(self, "Export", "App Name and Screen Name are required.")
            return

        file_path = self.mapping_store.save_mapping(
            app_name, screen_name, self.scanner.backend, self.window_title, self.canvas.elements, self.ref_resolution
        )

        if not silent:
            QMessageBox.information(self, "Export", f"Mapping saved to {file_path}")

    def closeEvent(self, event):
        settings = QSettings("TES_V2", "UIA_Mapper")
        settings.setValue("h_splitter", self.h_splitter.saveState())
        settings.setValue("v_splitter", self.v_splitter.saveState())
        super().closeEvent(event)
