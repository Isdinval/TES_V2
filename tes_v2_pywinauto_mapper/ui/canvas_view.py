from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QLabel, QToolTip
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QMouseEvent
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from typing import List, Optional
from core.element import UIElement

class CanvasView(QScrollArea):
    element_hovered = pyqtSignal(object)
    elements_deleted = pyqtSignal(list)
    mouse_position_changed = pyqtSignal(int, int, float, float)
    element_selected = pyqtSignal(object)
    group_zone_selected = pyqtSignal(QRect)
    element_drawn = pyqtSignal(QRect)
    delete_preview_count = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.label = QLabel()
        self.setWidget(self.label)

        self.screenshot_pixmap: Optional[QPixmap] = None
        self.elements: List[UIElement] = []
        self.window_rect: Optional[tuple] = None
        self.hovered_element: Optional[UIElement] = None
        # Right-click drag for deletion
        self._rdrag_start: Optional[QPoint] = None
        self._rdrag_rect: Optional[QRect] = None
        self.selected_element: Optional[UIElement] = None

        self.scale = 1.0
        self.offset = QPoint(0, 0)

        # Drag mode for group mapping
        self._drag_mode = False
        self._drag_start = None
        self._drag_rect = None

        # Draw mode for manual element creation
        self._draw_mode = False
        self._draw_start = None
        self._draw_rect = None

        # Pick mode for choosing coordinates
        self._pick_mode = False
        self._pick_callback = None

        self.label.setMouseTracking(True)
        self.label.paintEvent = self._label_paint_event
        self.label.mouseMoveEvent = self._label_mouse_move_event
        self.label.mousePressEvent = self._label_mouse_press_event
        self.label.mouseReleaseEvent = self._label_mouse_release_event

    def set_screenshot(self, pixmap: QPixmap, window_rect: tuple):
        self.screenshot_pixmap = pixmap
        self.window_rect = window_rect
        self.label.update()

    def set_elements(self, elements: List[UIElement]):
        self.elements = elements
        self.hovered_element = None
        self.selected_element = None
        self.label.update()

    def enable_drag_mode(self, enabled: bool):
        self._drag_mode = enabled
        self.label.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def enable_draw_mode(self, enabled: bool):
        self._draw_mode = enabled
        if enabled:
            self.label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.label.setCursor(Qt.CursorShape.ArrowCursor)
            self._draw_start = None
            self._draw_rect = None
            self.label.update()

    def set_pick_mode(self, enabled: bool, callback=None):
        """
        In pick mode, the next left-click emits a relative coordinate + element.
        Disables normal element selection while active.
        Cursor changes to crosshair + target.
        """
        self._pick_mode = enabled
        self._pick_callback = callback if enabled else None
        if enabled:
            self.label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.label.setCursor(Qt.CursorShape.ArrowCursor)

    def _update_scaling(self):
        if not self.screenshot_pixmap:
            self.scale = 1.0
            self.offset = QPoint(0, 0)
            return

        target_w = self.label.width()
        target_h = self.label.height()
        pix_w = self.screenshot_pixmap.width()
        pix_h = self.screenshot_pixmap.height()

        if pix_w > 0 and pix_h > 0:
            self.scale = min(target_w / pix_w, target_h / pix_h)
        else:
            self.scale = 1.0

        scaled_w = int(pix_w * self.scale)
        scaled_h = int(pix_h * self.scale)
        self.offset = QPoint((target_w - scaled_w) // 2, (target_h - scaled_h) // 2)

    def _label_paint_event(self, event):
        self._update_scaling()
        painter = QPainter(self.label)

        if self.screenshot_pixmap:
            painter.drawPixmap(self.offset, self.screenshot_pixmap.scaled(
                self.label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        for el in self.elements:
            rect = self._get_widget_rect(el.rectangle)

            if el == self.selected_element:
                pen = QPen(QColor(255, 0, 0), 3) # Red for selected
            elif el.control_type == "Manual" and not el.logical_key:
                pen = QPen(QColor(0, 200, 200), 2, Qt.PenStyle.DashDotLine)  # teal dashed
            elif el.control_type == "Manual" and el.logical_key:
                pen = QPen(QColor(0, 150, 150), 2)   # dark teal when mapped
            elif el.logical_key:
                pen = QPen(QColor(0, 0, 255), 2) # Blue for mapped
            elif el == self.hovered_element:
                pen = QPen(QColor(255, 255, 0), 2) # Yellow for hover
            elif el.ui_type in ("radio_group", "checkbox_group", "tab_bar", "dropdown_group"):
                pen = QPen(QColor(255, 165, 0), 2) # Orange for groups
            else:
                pen = QPen(QColor(0, 255, 0), 1) # Green for discovered

            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw member rects for groups
            if el.ui_type in ("radio_group", "checkbox_group", "tab_bar", "dropdown_group"):
                member_pen = QPen(QColor(255, 165, 0), 1, Qt.PenStyle.DotLine)  # dotted orange
                painter.setPen(member_pen)
                for mrect in getattr(el, "member_rects", []):
                    local_mrect = self._get_local_rect(mrect)
                    painter.drawRect(local_mrect)
                # Reset pen for text drawing below
                painter.setPen(pen)

            # Draw logical key if present
            if el.logical_key and not (el == self.hovered_element):
                painter.setPen(QColor(0, 0, 255))
                painter.drawText(rect.topLeft() + QPoint(2, -2), el.logical_key)


        # Draw mode rectangle (teal, solid)
        if self._draw_rect:
            draw_pen = QPen(QColor(0, 200, 200), 2, Qt.PenStyle.SolidLine)
            painter.setPen(draw_pen)
            painter.setBrush(QColor(0, 200, 200, 40))
            painter.drawRect(self._draw_rect)
            painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._drag_rect:
            painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._drag_rect)

        if self._rdrag_rect:
            # Highlight elements that will be deleted
            delete_highlight_pen = QPen(QColor(220, 0, 0), 2)
            delete_highlight_brush = QColor(220, 0, 0, 60)
            for el in self.elements:
                el_rect = self._get_widget_rect(el.rectangle)
                if el_rect.intersects(self._rdrag_rect):
                    painter.setPen(delete_highlight_pen)
                    painter.setBrush(delete_highlight_brush)
                    painter.drawRect(el_rect)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Red dashed border
            painter.setPen(QPen(QColor(220, 0, 0), 2, Qt.PenStyle.DashLine))
            # Semi-transparent red fill (alpha=50)
            painter.setBrush(QColor(220, 0, 0, 50))
            painter.drawRect(self._rdrag_rect)
            # Reset brush
            painter.setBrush(Qt.BrushStyle.NoBrush)

    def _get_widget_rect(self, global_rect: List[int]) -> QRect:
        if not self.window_rect:
            lx, ly = global_rect[0], global_rect[1]
        else:
            lx = global_rect[0] - self.window_rect[0]
            ly = global_rect[1] - self.window_rect[1]

        return QRect(
            int(lx * self.scale) + self.offset.x(),
            int(ly * self.scale) + self.offset.y(),
            int(global_rect[2] * self.scale),
            int(global_rect[3] * self.scale)
        )


    def _get_local_rect(self, global_rect: List[int]) -> QRect:
        if not self.window_rect:
            lx, ly = global_rect[0], global_rect[1]
        else:
            lx = global_rect[0] - self.window_rect[0]
            ly = global_rect[1] - self.window_rect[1]

        return QRect(
            int(lx * self.scale) + self.offset.x(),
            int(ly * self.scale) + self.offset.y(),
            int(global_rect[2] * self.scale),
            int(global_rect[3] * self.scale)
    )

    def _to_pixmap_rect(self, widget_rect: QRect) -> QRect:
        if self.scale <= 0: return widget_rect
        return QRect(
            int((widget_rect.x() - self.offset.x()) / self.scale),
            int((widget_rect.y() - self.offset.y()) / self.scale),
            int(widget_rect.width() / self.scale),
            int(widget_rect.height() / self.scale)
        )

    def _label_mouse_move_event(self, event: QMouseEvent):
        pos = event.pos()

        # emit live coordinates (new feature)
        rel_x = pos.x() / max(self.label.width(), 1)
        rel_y = pos.y() / max(self.label.height(), 1)
        self.mouse_position_changed.emit(pos.x(), pos.y(), round(rel_x, 4), round(rel_y, 4))

        if self._draw_mode and self._draw_start:
            self._draw_rect = QRect(self._draw_start, event.pos()).normalized()
            self.label.update()
            return

        if self._drag_mode and self._drag_start:
            self._drag_rect = QRect(self._drag_start, event.pos()).normalized()
            self.label.update()
            return

        # Right drag deletion rectangle
        if self._rdrag_start and (event.buttons() & Qt.MouseButton.RightButton):
            self._rdrag_rect = QRect(self._rdrag_start, event.pos()).normalized()
            # Count elements that would be deleted
            count = sum(
                1 for el in self.elements
                if self._get_widget_rect(el.rectangle).intersects(self._rdrag_rect)
            )
            self.delete_preview_count.emit(count)
            self.label.update()
            return

        found = None
        for el in reversed(self.elements):
            if self._get_widget_rect(el.rectangle).contains(pos):
                found = el
                break

        if found != self.hovered_element:
            self.hovered_element = found
            if found:
                tooltip = f"<b>{found.control_type}</b>: {found.name}<br>"
                if found.automation_id:
                    tooltip += f"ID: {found.automation_id}<br>"
                if found.logical_key:
                    tooltip += f"Key: <b>{found.logical_key}</b>"
                tooltip += "<br><i>Right-click to delete</i>"
                QToolTip.showText(event.globalPosition().toPoint(), tooltip, self.label)
            else:
                QToolTip.hideText()

            self.element_hovered.emit(found)
            self.label.update()

            
    def _label_mouse_press_event(self, event: QMouseEvent):
        self._update_scaling()

        if self._pick_mode and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            rel_x = round((pos.x() - self.offset.x()) / max(
                self.screenshot_pixmap.width() * self.scale, 1), 6)
            rel_y = round((pos.y() - self.offset.y()) / max(
                self.screenshot_pixmap.height() * self.scale, 1), 6)
            rel_x = max(0.0, min(1.0, rel_x))
            rel_y = max(0.0, min(1.0, rel_y))

            # Find element under cursor
            found = next(
                (el for el in reversed(self.elements)
                 if self._get_widget_rect(el.rectangle).contains(pos)),
                None
            )

            self._pick_mode = False
            self.label.setCursor(Qt.CursorShape.ArrowCursor)

            if self._pick_callback:
                self._pick_callback(rel_x, rel_y, found)
                self._pick_callback = None
            return   # don't trigger normal element selection

        # Draw mode - left button (check BEFORE group mode check)
        if self._draw_mode and event.button() == Qt.MouseButton.LeftButton:
            self._draw_start = event.pos()
            self._draw_rect = None
            return

        if self._drag_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            self._drag_rect = None
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.selected_element = self.hovered_element
            self.element_selected.emit(self.selected_element)
            self.label.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._rdrag_start = event.pos()
            self._rdrag_rect = None

    def _label_mouse_release_event(self, event: QMouseEvent):
        self._update_scaling()
        if self._draw_mode and self._draw_start and event.button() == Qt.MouseButton.LeftButton:
            if self._draw_rect and self._draw_rect.width() > 5 and self._draw_rect.height() > 5:
                pix_rect = self._to_pixmap_rect(self._draw_rect)
                self.element_drawn.emit(pix_rect)
            self._draw_start = None
            self._draw_rect = None
            self.label.update()
            return

        if self._drag_mode and self._drag_start and event.button() == Qt.MouseButton.LeftButton:
            if self._drag_rect and self._drag_rect.width() > 5 and self._drag_rect.height() > 5:
                pix_rect = self._to_pixmap_rect(self._drag_rect)
                self.group_zone_selected.emit(pix_rect)
            self._drag_start = None
            self._drag_rect = None
            self.label.update()
            return

        if event.button() == Qt.MouseButton.RightButton and self._rdrag_start:
            was_drag = (self._rdrag_rect is not None
                        and self._rdrag_rect.width() > 5
                        and self._rdrag_rect.height() > 5)

            to_delete = []
            if was_drag:
                # Delete all elements whose local rect overlaps the drag zone
                to_delete = [
                    el for el in self.elements
                    if self._get_local_rect(el.rectangle).intersects(self._rdrag_rect)
                ]
            else:
                # Single right-click: delete only the element under the cursor
                pos = self._rdrag_start
                found_list = [
                    el for el in reversed(self.elements)
                    if self._get_local_rect(el.rectangle).contains(pos)
                ]
                if found_list:
                    to_delete = [found_list[0]]

            if to_delete:
                for el in to_delete:
                    self.elements.remove(el)
                # Deselect if selected element was deleted
                if self.selected_element in to_delete:
                    self.selected_element = None
                    self.element_selected.emit(None)
                if self.hovered_element in to_delete:
                    self.hovered_element = None
                self.elements_deleted.emit(to_delete)
                self.label.update()

            self._rdrag_start = None
            self._rdrag_rect = None

    def add_group_overlay(self, element: UIElement):
        self.selected_element = element
        self.label.update()
