import os
import json
import time
import win32gui
import win32api
import win32con
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QLabel, QProgressBar, QFileDialog,
                            QMessageBox, QApplication, QLineEdit, QFormLayout, QSplitter)

from PyQt6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QCursor
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

        self.draw_mode_btn = QPushButton("✏ Draw Element")
        self.draw_mode_btn.setCheckable(True)
        self.draw_mode_btn.setToolTip(
            "Draw a rectangle on the screenshot to manually create an element\n"
            "that pywinauto did not detect automatically."
        )
        self.draw_mode_btn.toggled.connect(self._on_draw_mode_toggled)
        toolbar.addWidget(self.draw_mode_btn)

        self.status_label = QLabel("Ready")
        toolbar.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        toolbar.addWidget(self.progress)
        self.coord_label = QLabel("x:0 y:0 | rel:(0.000, 0.000)")
        self.coord_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; "
            "background: #1e1e1e; color: #00ff88; padding: 2px 6px; border-radius: 3px;"
        )
        self.coord_label.setMinimumWidth(220)
        toolbar.addWidget(self.coord_label)

        left_layout.addLayout(toolbar)

        self.group_mode_banner = QLabel("🔲 GROUP MODE ACTIVE — Drag to select members | ESC to cancel")
        self.group_mode_banner.setStyleSheet("background: #FF9800; color: white; font-weight: bold; padding: 4px 8px; border-radius: 3px;")
        self.group_mode_banner.setVisible(False)
        left_layout.addWidget(self.group_mode_banner)

        self.draw_mode_banner = QLabel("✏ DRAW MODE ACTIVE — Drag to define element rectangle | ESC to cancel")
        self.draw_mode_banner.setStyleSheet("background: #00BCD4; color: white; font-weight: bold; padding: 4px 8px;")
        self.draw_mode_banner.setVisible(False)
        left_layout.addWidget(self.draw_mode_banner)

        self.canvas = CanvasView()
        self.canvas.element_selected.connect(self._on_element_selected)
        self.canvas.group_zone_selected.connect(self._on_group_zone_selected)
        self.canvas.element_drawn.connect(self._on_element_drawn)
        self.canvas.delete_preview_count.connect(
            lambda n: self.status_label.setText(
                f"Release to delete {n} element(s)" if n > 0 else "No elements in zone"
            )
        )
        self.canvas.elements_deleted.connect(self._on_elements_deleted)
        self.canvas.mouse_position_changed.connect(self._on_mouse_position_changed)
        left_layout.addWidget(self.canvas)

        self.h_splitter.addWidget(left_widget)

        # Right: vertical splitter with form on top, info panel below
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)

        self.element_form = ElementForm()
        self.element_form.set_canvas(self.canvas)
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
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self._cancel_active_mode)
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

        # Preserve manually-created elements from previous session
        manual_elements = [el for el in self.canvas.elements if el.control_type == "Manual"]
        elements.extend(manual_elements)

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

    def _cancel_active_mode(self):
        if self.group_mode_btn.isChecked():
            self.group_mode_btn.setChecked(False)
            self.status_label.setText("Group mode cancelled.")
        elif self.draw_mode_btn.isChecked():
            self.draw_mode_btn.setChecked(False)
            self.status_label.setText("Draw mode cancelled.")

    def _on_draw_mode_toggled(self, enabled: bool):
        if enabled:
            self.group_mode_btn.setChecked(False)
        self.canvas.enable_draw_mode(enabled)
        self.draw_mode_banner.setVisible(enabled)
        if not enabled:
            self.canvas._draw_start = None
            self.canvas._draw_rect = None
            self.canvas.label.update()
        self.draw_mode_btn.setText("✕ Cancel Draw" if enabled else "✏ Draw Element")

    def _on_element_drawn(self, pix_rect: QRect):
        if not self.canvas.window_rect:
            return

        wx, wy, ww, wh = self.canvas.window_rect
        abs_x = pix_rect.x() + wx
        abs_y = pix_rect.y() + wy
        abs_w = pix_rect.width()
        abs_h = pix_rect.height()

        new_el = UIElement(
            name="",
            automation_id="",
            control_type="Manual",
            class_name="",
            framework_id="",
            rectangle=[abs_x, abs_y, abs_w, abs_h],
            is_enabled=True,
            is_visible=True,
            ui_type="button",
            action="click",
            logical_key="",
            supported_patterns=[],
            execution_hint="pyautogui_fallback",
        )
        new_el.ref_resolution = self.ref_resolution

        self.draw_mode_btn.setChecked(False)
        self.canvas.elements.append(new_el)
        self.canvas.selected_element = new_el
        self.canvas.label.update()
        self.element_form.set_element(new_el)
        self.info_panel.update_info(new_el)
        self.status_label.setText(
            "Manual element created. Set logical_key, ui_type and click 'Update Element'."
        )

    def _on_group_mode_toggled(self, enabled):
        if enabled:
            self.draw_mode_btn.setChecked(False)
        self.canvas.enable_drag_mode(enabled)
        self.group_mode_banner.setVisible(enabled)
        if not enabled:
            # Explicitly clear any in-progress drag
            self.canvas._drag_start = None
            self.canvas._drag_rect = None
            self.canvas.label.update()
        self.group_mode_btn.setText("✕ Cancel Group" if enabled else "Map as Group")

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

        # Sort members: interactive first, then top-to-bottom
        INTERACTIVE_TYPES = {"RadioButton", "CheckBox", "TabItem", "Button"}
        members.sort(key=lambda m: (0 if m.control_type in INTERACTIVE_TYPES else 1, m.rectangle[1]))

        # Detect predominant type with majority-vote + override
        from collections import Counter
        types_in_zone = [m.control_type for m in members]
        type_counts = Counter(types_in_zone)

        TYPE_TO_UI = {
            "RadioButton":  "radio_group",
            "CheckBox":     "checkbox_group",
            "TabItem":      "tab_bar",
            "ListItem":     "dropdown_group",
            "MenuItem":     "dropdown_group",
        }

        dominant_type, dominant_count = type_counts.most_common(1)[0]
        proposed_ui_type = TYPE_TO_UI.get(dominant_type, "radio_group")
        proposed_action_map = {
            "radio_group":    "select_by_label",
            "checkbox_group": "check_by_label",
            "tab_bar":        "click_by_label",
            "dropdown_group": "select_by_label",
        }
        proposed_action = proposed_action_map.get(proposed_ui_type, "select_by_label")

        # Special case: RadioButton items that are actually dropdown options
        auto_reclassified = False
        if proposed_ui_type == "radio_group" and len(members) >= 2:
            heights = [m.rectangle[3] for m in members]
            avg_height = sum(heights) / len(heights)
            gaps = []
            sorted_members = sorted(members, key=lambda m: m.rectangle[1])
            for i in range(1, len(sorted_members)):
                gap = sorted_members[i].rectangle[1] - (
                    sorted_members[i-1].rectangle[1] + sorted_members[i-1].rectangle[3]
                )
                gaps.append(gap)
            if gaps and all(abs(g) < avg_height * 0.3 for g in gaps):
                proposed_ui_type = "dropdown_group"
                proposed_action = "select_by_label"
                auto_reclassified = True

        unknown_type = dominant_type not in TYPE_TO_UI
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
                "label":        m.name or m.logical_key or f"option_{len(choices)}",
                "x":            round(cx / rw, 6),
                "y":            round(cy / rh, 6),
                "stable_id":    m.automation_id or f"{m.name}_{m.control_type}",
                "control_type": m.control_type,
                "class_name":   getattr(m, "class_name", ""),
                "automation_id": getattr(m, "automation_id", ""),
                "rect":         [
                    round(m.rectangle[0] / rw, 6),
                    round(m.rectangle[1] / rh, 6),
                    round(m.rectangle[2] / rw, 6),
                    round(m.rectangle[3] / rh, 6),
                ]
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
            member_rects=[m.rectangle for m in members],
            supported_patterns=[],
            execution_hint="pyautogui_fallback",
        )
        group_el.ref_resolution = self.ref_resolution

        # 1. Exit group mode FIRST
        self.group_mode_btn.setChecked(False)
        self.canvas.enable_drag_mode(False)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

        # 2. Reset any in-progress drag state
        self.canvas._drag_start = None
        self.canvas._drag_rect = None

        # 3. Add the group element and update UI
        self.canvas.elements.append(group_el)
        self.canvas.add_group_overlay(group_el)
        self.element_form.set_element(group_el)

        # 4. Visual feedback
        if auto_reclassified:
            self.status_label.setText(
                f"⚠ Elements were classified as '{dominant_type}' but look like a list. "
                f"Proposed: dropdown_group. Change ui_type in the form if incorrect."
            )
        elif unknown_type:
            self.status_label.setText(
                f"⚠ Could not auto-classify elements (type: '{dominant_type}'). "
                f"Defaulted to 'radio_group'. Please change ui_type and verify choices in the form."
            )
        elif proposed_ui_type == "dropdown_group":
            self.status_label.setText(
                "Dropdown options captured. Now set logical_key to match the trigger "
                "dropdown element and click 'Update Element'."
            )
        else:
            self.status_label.setText(
                f"Group '{proposed_ui_type}' created with {len(members)} members. "
                f"Set logical_key and click 'Update Element'."
            )

    def _on_export_requested(self, silent=False):
        if not self.canvas.elements: return

        # Resolve triggers for ALL multi-choice types with no trigger already set
        MULTI_CHOICE_TYPES = {"radio_group", "checkbox_group", "tab_bar", "dropdown_group"}
        dropdowns = {el.logical_key: el for el in self.canvas.elements
                     if el.ui_type == "dropdown" and el.logical_key}

        for el in self.canvas.elements:
            if el.ui_type in MULTI_CHOICE_TYPES and el.logical_key in dropdowns and not el.trigger:
                trigger_el = dropdowns[el.logical_key]
                rw, rh = self.ref_resolution
                tx, ty, tw, th = trigger_el.rectangle
                el.trigger = {
                    "x": round(tx / rw, 6),
                    "y": round(ty / rh, 6),
                    "w": round(tw / rw, 6),
                    "h": round(th / rh, 6),
                }

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

    def _on_mouse_position_changed(self, cx: int, cy: int, rx: float, ry: float):
        self.coord_label.setText(f"x:{cx} y:{cy} | rel:({rx:.3f}, {ry:.3f})")

    def _on_elements_deleted(self, deleted: list):
        """Auto-save after deletion so the mapping file stays in sync."""
        self._on_export_requested(silent=True)
        count = len(deleted)
        self.status_label.setText(f"Deleted {count} element(s). Total: {len(self.canvas.elements)}")


    def closeEvent(self, event):
        settings = QSettings("TES_V2", "UIA_Mapper")
        settings.setValue("h_splitter", self.h_splitter.saveState())
        settings.setValue("v_splitter", self.v_splitter.saveState())
        super().closeEvent(event)
