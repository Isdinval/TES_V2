"""
CanvasView: displays the screenshot, overlays YOLO bbox candidates,
allows the user to:
  - click a candidate bbox to select it
  - click+drag to draw a new bbox manually
  - sample points for specific click targets (sampling mode)
Emits signals to the main window.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QLabel, QSizePolicy, QToolTip
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPixmap, QImage, QFont, QCursor
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PIL import Image


# Colors
COLOR_CANDIDATE = QColor(255, 255, 0, 180)      # yellow contour
COLOR_CANDIDATE_HOVER = QColor(255, 255, 0, 255)
COLOR_SELECTED = QColor(255, 165, 0, 220)       # orange
COLOR_MAPPED = QColor(50, 205, 50, 180)         # green
COLOR_DRAW = QColor(255, 69, 0, 220)            # red-orange for live draw
COLOR_SAMPLED = QColor(255, 255, 0, 220)        # yellow for sampled targets


class CanvasView(QWidget):
    # Signals
    candidate_selected = pyqtSignal(dict)   # emitted when user clicks a candidate
    bbox_drawn = pyqtSignal(dict)           # emitted when user finishes drawing a bbox
    point_sampled = pyqtSignal(dict)        # emitted in sampling mode: {"x", "y"} relative
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self._pixmap: QPixmap | None = None
        self._img_w: int = 1
        self._img_h: int = 1

        self._candidates: list[dict] = []   # [{x,y,w,h,description,confidence,interactable}]
        self._mapped_elements: list[dict] = []  # already mapped elements
        self._selected_idx: int | None = None
        self._hover_idx: int | None = None

        # Performance cache
        self._cached_image_rect = QRect()
        self._candidate_rects: list[QRect] = []
        self._mapped_rects: list[QRect] = []
        self._show_candidates = True

        # Sampling state
        self._sampling_mode = False
        self._sampled_points: list[dict] = [] # list of {"x", "y"} relative

        # Draw state
        self._drawing = False
        self._draw_start: QPoint | None = None
        self._draw_end: QPoint | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_image(self, pil_image: Image.Image) -> None:
        self._img_w, self._img_h = pil_image.size
        rgb = pil_image.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, self._img_w, self._img_h, self._img_w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._candidates = []
        self._mapped_elements = []
        self._selected_idx = None
        self._hover_idx = None
        self._sampled_points = []
        self._update_geometry_cache()
        self.update()

    def set_candidates(self, candidates: list[dict]) -> None:
        self._candidates = candidates
        self._selected_idx = None
        self._update_geometry_cache()
        self.update()

    def set_mapped_elements(self, elements: list[dict]) -> None:
        """Pass list of full element dicts for already-mapped elements."""
        self._mapped_elements = elements
        self._update_geometry_cache()
        self.update()

    def clear_selection(self) -> None:
        self._selected_idx = None
        self.update()

    def set_sampling_mode(self, enabled: bool) -> None:
        self._sampling_mode = enabled
        if enabled:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self._sampled_points = []
        self.update()

    def set_sampled_points(self, points: list[dict]) -> None:
        """Update the list of points to display (relative coords)."""
        self._sampled_points = points
        self.update()

    def set_candidates_visible(self, visible: bool) -> None:
        self._show_candidates = visible
        self.update()

    # ------------------------------------------------------------------
    # Coordinate helpers & Cache
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_geometry_cache()

    def _update_geometry_cache(self) -> None:
        """Pre-calculate screen-space rectangles for all elements."""
        if self._pixmap is None:
            self._cached_image_rect = QRect(0, 0, self.width(), self.height())
            return

        # 1. Scaled image rect
        scaled_size = self._pixmap.size().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        x = (self.width() - scaled_size.width()) // 2
        y = (self.height() - scaled_size.height()) // 2
        self._cached_image_rect = QRect(x, y, scaled_size.width(), scaled_size.height())

        ir = self._cached_image_rect

        # 2. Candidates rects
        self._candidate_rects = []
        for c in self._candidates:
            rx, ry, rw, rh = c["x"], c["y"], c["w"], c["h"]
            rect = QRect(
                ir.x() + int(rx * ir.width()),
                ir.y() + int(ry * ir.height()),
                int(rw * ir.width()),
                int(rh * ir.height())
            )
            self._candidate_rects.append(rect)

        # 3. Mapped rects
        self._mapped_rects = []
        for el in self._mapped_elements:
            bbox = el.get("bbox_relative", {})
            rx, ry, rw, rh = bbox.get("x", 0), bbox.get("y", 0), bbox.get("w", 0), bbox.get("h", 0)
            rect = QRect(
                ir.x() + int(rx * ir.width()),
                ir.y() + int(ry * ir.height()),
                int(rw * ir.width()),
                int(rh * ir.height())
            )
            self._mapped_rects.append(rect)

    def _rel_to_screen(self, rx: float, ry: float, rw: float = 0, rh: float = 0) -> QRect:
        ir = self._cached_image_rect
        x = ir.x() + int(rx * ir.width())
        y = ir.y() + int(ry * ir.height())
        w = int(rw * ir.width())
        h = int(rh * ir.height())
        return QRect(x, y, w, h)

    def _screen_to_rel(self, p: QPoint) -> tuple[float, float]:
        ir = self._cached_image_rect
        if ir.width() <= 0 or ir.height() <= 0:
            return 0.0, 0.0
        rx = (p.x() - ir.x()) / ir.width()
        ry = (p.y() - ir.y()) / ir.height()
        return max(0.0, min(1.0, rx)), max(0.0, min(1.0, ry))

    def _hit_candidate(self, pos: QPoint) -> int | None:
        if not self._show_candidates:
            return None
        # Iterate backwards to pick the "top-most" (often smallest) bbox first
        for i in reversed(range(len(self._candidate_rects))):
            if self._candidate_rects[i].contains(pos):
                return i
        return None

    def _hit_mapped(self, pos: QPoint) -> int | None:
        for i in reversed(range(len(self._mapped_rects))):
            if self._mapped_rects[i].contains(pos):
                return i
        return None

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self._sampling_mode and event.button() == Qt.MouseButton.LeftButton:
            rx, ry = self._screen_to_rel(event.pos())
            self.point_sampled.emit({"x": round(rx, 4), "y": round(ry, 4)})
            return

        if event.button() == Qt.MouseButton.RightButton:
            # Mask candidate
            hit = self._hit_candidate(event.pos())
            if hit is not None:
                self._candidates.pop(hit)
                self._update_geometry_cache()
                self._hover_idx = None
                self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_candidate(event.pos())
            if hit is not None:
                self._selected_idx = hit
                self._drawing = False
                self.update()
                self.candidate_selected.emit(self._candidates[hit])
            else:
                # Start drawing
                self._drawing = True
                self._draw_start = event.pos()
                self._draw_end = event.pos()
                self._selected_idx = None
                self.update()
                self.selection_cleared.emit()

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._draw_end = event.pos()
            self.update()
            return

        # 1. Update hover state
        old_hover = self._hover_idx
        self._hover_idx = self._hit_candidate(event.pos())
        if old_hover != self._hover_idx:
            self.update()

        # 2. Tooltip logic
        # Priority: Mapped elements > Candidates
        mapped_idx = self._hit_mapped(event.pos())
        if mapped_idx is not None:
            el = self._mapped_elements[mapped_idx]
            QToolTip.showText(event.globalPosition().toPoint(), el.get("logical_key", ""), self)
        elif self._hover_idx is not None:
            c = self._candidates[self._hover_idx]
            desc = c.get("description", "")
            conf = c.get("confidence", 0)
            text = f"IA: {desc}\nConf: {conf:.2f}"
            QToolTip.showText(event.globalPosition().toPoint(), text, self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._drawing:
            return

        self._drawing = False
        if self._draw_start is None or self._draw_end is None:
            return

        # Normalize rect
        x1 = min(self._draw_start.x(), self._draw_end.x())
        y1 = min(self._draw_start.y(), self._draw_end.y())
        x2 = max(self._draw_start.x(), self._draw_end.x())
        y2 = max(self._draw_start.y(), self._draw_end.y())

        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            self._draw_start = None
            self._draw_end = None
            self.update()
            return

        rx1, ry1 = self._screen_to_rel(QPoint(x1, y1))
        rx2, ry2 = self._screen_to_rel(QPoint(x2, y2))

        bbox = {
            "x": round(rx1, 4),
            "y": round(ry1, 4),
            "w": round(rx2 - rx1, 4),
            "h": round(ry2 - ry1, 4),
        }
        self._draw_start = None
        self._draw_end = None
        self._update_geometry_cache()
        self.update()
        self.bbox_drawn.emit(bbox)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ir = self._cached_image_rect

        if self._pixmap is None:
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Capture un écran pour commencer")
            return

        # Draw image
        painter.drawPixmap(ir, self._pixmap)

        # Draw mapped elements (always green)
        for i, el in enumerate(self._mapped_elements):
            rect = self._mapped_rects[i]
            base_color = COLOR_MAPPED

            painter.setPen(QPen(base_color, 2))
            painter.fillRect(rect, QColor(base_color.red(), base_color.green(), base_color.blue(), 30))
            painter.drawRect(rect)

            # Draw ALL click targets permanently (yellow dots)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(COLOR_SAMPLED)

            target = el.get("click_target")
            if target:
                t_pos = self._rel_to_screen(target["x"], target["y"])
                painter.drawEllipse(t_pos.topLeft(), 3, 3)

            for choice in el.get("choices", []):
                if choice.get("x") is not None:
                    c_pos = self._rel_to_screen(choice["x"], choice["y"])
                    painter.drawEllipse(c_pos.topLeft(), 3, 3)

        # Draw candidates (YOLO)
        if self._show_candidates:
            for i, rect in enumerate(self._candidate_rects):
                if i == self._selected_idx:
                    color = COLOR_SELECTED
                    pen_width = 2
                elif i == self._hover_idx:
                    color = COLOR_CANDIDATE_HOVER
                    pen_width = 2
                else:
                    color = COLOR_CANDIDATE
                    pen_width = 1

                painter.setPen(QPen(color, pen_width))
                # Yellow transparent interior
                painter.fillRect(rect, QColor(255, 255, 0, 40))
                painter.drawRect(rect)

        # Draw currently sampling points (yellow circles)
        painter.setPen(QPen(COLOR_SAMPLED, 2))
        painter.setBrush(COLOR_SAMPLED)
        for p in self._sampled_points:
            pos = self._rel_to_screen(p["x"], p["y"])
            painter.drawEllipse(pos.topLeft(), 5, 5)

        # Live draw rect
        if self._drawing and self._draw_start and self._draw_end:
            draw_rect = QRect(self._draw_start, self._draw_end).normalized()
            painter.setPen(QPen(COLOR_DRAW, 2, Qt.PenStyle.DashLine))
            painter.fillRect(draw_rect, QColor(255, 69, 0, 30))
            painter.drawRect(draw_rect)

        painter.end()
