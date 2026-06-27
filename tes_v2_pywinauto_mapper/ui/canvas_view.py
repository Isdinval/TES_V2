from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QLabel, QToolTip
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QMouseEvent
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from typing import List, Optional
from core.element import UIElement

class CanvasView(QScrollArea):
    element_hovered = pyqtSignal(object)
    element_selected = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.label = QLabel(self.container)
        self.setWidget(self.container)

        self.screenshot_pixmap: Optional[QPixmap] = None
        self.elements: List[UIElement] = []
        self.window_rect: Optional[tuple] = None
        self.hovered_element: Optional[UIElement] = None
        self.selected_element: Optional[UIElement] = None

        self.label.setMouseTracking(True)
        self.label.paintEvent = self._label_paint_event
        self.label.mouseMoveEvent = self._label_mouse_move_event
        self.label.mousePressEvent = self._label_mouse_press_event

    def set_screenshot(self, pixmap: QPixmap, window_rect: tuple):
        self.screenshot_pixmap = pixmap
        self.window_rect = window_rect
        self.label.setPixmap(pixmap)
        self.label.setFixedSize(pixmap.size())
        self.update()

    def set_elements(self, elements: List[UIElement]):
        self.elements = elements
        self.hovered_element = None
        self.selected_element = None
        self.update()

    def _label_paint_event(self, event):
        painter = QPainter(self.label)
        if self.screenshot_pixmap:
            painter.drawPixmap(0, 0, self.screenshot_pixmap)

        for el in self.elements:
            rect = self._get_local_rect(el.rectangle)

            if el == self.selected_element:
                pen = QPen(QColor(255, 0, 0), 2) # Red for selected
            elif el.logical_key:
                pen = QPen(QColor(0, 0, 255), 2) # Blue for mapped
            elif el == self.hovered_element:
                pen = QPen(QColor(255, 255, 0), 2) # Yellow for hover
            else:
                pen = QPen(QColor(0, 255, 0), 1) # Green for discovered

            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw logical key if present
            if el.logical_key and not (el == self.hovered_element):
                painter.setPen(QColor(0, 0, 255))
                painter.drawText(rect.topLeft() + QPoint(2, -2), el.logical_key)

    def _get_local_rect(self, global_rect: List[int]) -> QRect:
        if not self.window_rect:
            return QRect(global_rect[0], global_rect[1], global_rect[2], global_rect[3])
        lx = global_rect[0] - self.window_rect[0]
        ly = global_rect[1] - self.window_rect[1]
        return QRect(lx, ly, global_rect[2], global_rect[3])

    def _label_mouse_move_event(self, event: QMouseEvent):
        pos = event.pos()
        found = None
        for el in reversed(self.elements):
            if self._get_local_rect(el.rectangle).contains(pos):
                found = el
                break

        if found != self.hovered_element:
            self.hovered_element = found
            if found:
                tooltip = f"<b>{found.control_type}</b>: {found.name}<br>"
                if found.automation_id: tooltip += f"ID: {found.automation_id}<br>"
                if found.logical_key: tooltip += f"Key: <b>{found.logical_key}</b>"
                QToolTip.showText(event.globalPosition().toPoint(), tooltip, self.label)
            else:
                QToolTip.hideText()
            self.element_hovered.emit(found)
            self.label.update()

    def _label_mouse_press_event(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected_element = self.hovered_element
            self.element_selected.emit(self.selected_element)
            self.label.update()
