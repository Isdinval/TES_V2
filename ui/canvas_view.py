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
COLOR_CANDIDATE = QColor(100, 149, 237, 160)   # cornflower blue, semi-transparent
COLOR_CANDIDATE_HOVER = QColor(100, 149, 237, 220)
COLOR_SELECTED = QColor(255, 165, 0, 220)       # orange
COLOR_MAPPED = QColor(50, 205, 50, 180)         # green
COLOR_NAVIGATION = QColor(255, 140, 0, 200)     # DarkOrange for nav buttons
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
        self.update()

    def set_candidates(self, candidates: list[dict]) -> None:
        self._candidates = candidates
        self._selected_idx = None
        self.update()

    def set_mapped_elements(self, elements: list[dict]) -> None:
        """Pass list of full element dicts for already-mapped elements."""
        self._mapped_elements = elements
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

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _image_rect(self) -> QRect:
        """Scaled image rect, centered in widget."""
        if self._pixmap is None:
            return QRect(0, 0, self.width(), self.height())
        scaled = self._pixmap.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _rel_to_screen(self, rx: float, ry: float, rw: float = 0, rh: float = 0) -> QRect:
        ir = self._image_rect()
        x = ir.x() + int(rx * ir.width())
        y = ir.y() + int(ry * ir.height())
        w = int(rw * ir.width())
        h = int(rh * ir.height())
        return QRect(x, y, w, h)

    def _screen_to_rel(self, p: QPoint) -> tuple[float, float]:
        ir = self._image_rect()
        rx = (p.x() - ir.x()) / ir.width()
        ry = (p.y() - ir.y()) / ir.height()
        return max(0.0, min(1.0, rx)), max(0.0, min(1.0, ry))

    def _hit_candidate(self, pos: QPoint) -> int | None:
        for i, c in enumerate(self._candidates):
            rect = self._rel_to_screen(c["x"], c["y"], c["w"], c["h"])
            if rect.contains(pos):
                return i
        return None

    def _hit_mapped(self, pos: QPoint) -> dict | None:
        """Returns the first mapped element that contains the screen position."""
        for el in self._mapped_elements:
            bbox = el.get("bbox_relative", {})
            rect = self._rel_to_screen(bbox.get("x", 0), bbox.get("y", 0), bbox.get("w", 0), bbox.get("h", 0))
            if rect.contains(pos):
                return el
        return None

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._sampling_mode:
            rx, ry = self._screen_to_rel(event.pos())
            self.point_sampled.emit({"x": round(rx, 4), "y": round(ry, 4)})
            return

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
        else:
            self._hover_idx = self._hit_candidate(event.pos())

            # Tooltip for mapped elements
            mapped = self._hit_mapped(event.pos())
            if mapped:
                QToolTip.showText(event.globalPosition().toPoint(), mapped.get("logical_key", ""), self)
            else:
                QToolTip.hideText()

            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._drawing:
            return

        self._drawing = False
        if self._draw_start is None or self._draw_end is None:
            return

        # Normalize rect (handle drag in any direction)
        x1 = min(self._draw_start.x(), self._draw_end.x())
        y1 = min(self._draw_start.y(), self._draw_end.y())
        x2 = max(self._draw_start.x(), self._draw_end.x())
        y2 = max(self._draw_start.y(), self._draw_end.y())

        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            # Too small — ignore
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
        self.update()
        self.bbox_drawn.emit(bbox)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap is None:
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Capture un écran pour commencer")
            return

        # Draw scaled image
        ir = self._image_rect()
        scaled = self._pixmap.scaled(
            ir.width(), ir.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(ir.x(), ir.y(), scaled)

        # Draw mapped elements (green or orange for navigation)
        for el in self._mapped_elements:
            bbox = el.get("bbox_relative", {})
            rect = self._rel_to_screen(bbox.get("x", 0), bbox.get("y", 0), bbox.get("w", 0), bbox.get("h", 0))

            is_nav = "navigation_config" in el
            base_color = COLOR_NAVIGATION if is_nav else COLOR_MAPPED

            pen = QPen(base_color, 2)
            painter.setPen(pen)
            painter.fillRect(rect, QColor(base_color.red(), base_color.green(), base_color.blue(), 30))
            painter.drawRect(rect)

            # Draw ALL click targets permanently (yellow circles)
            painter.setPen(QPen(COLOR_SAMPLED, 1.5))
            painter.setBrush(COLOR_SAMPLED)

            # Main click target
            target = el.get("click_target")
            if target:
                t_pos = self._rel_to_screen(target["x"], target["y"])
                painter.drawEllipse(t_pos.topLeft(), 3, 3)

            # Choice targets
            for choice in el.get("choices", []):
                if choice.get("x") is not None:
                    c_pos = self._rel_to_screen(choice["x"], choice["y"])
                    painter.drawEllipse(c_pos.topLeft(), 3, 3)

        # Draw candidates
        for i, c in enumerate(self._candidates):
            rect = self._rel_to_screen(c["x"], c["y"], c["w"], c["h"])
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
            painter.fillRect(rect, QColor(color.red(), color.green(), color.blue(), 25))
            painter.drawRect(rect)

            # Confidence label on hover/selected
            if i in (self._selected_idx, self._hover_idx):
                painter.setFont(QFont("monospace", 8))
                label = f"{c.get('confidence', 0):.2f}"
                painter.setPen(color)
                painter.drawText(rect.x() + 2, rect.y() - 3, label)

        # Draw currently sampling points (yellow circles)
        painter.setPen(QPen(COLOR_SAMPLED, 2))
        painter.setBrush(COLOR_SAMPLED)
        for p in self._sampled_points:
            pos = self._rel_to_screen(p["x"], p["y"])
            painter.drawEllipse(pos.topLeft(), 5, 5)

        # Live draw rect
        if self._drawing and self._draw_start and self._draw_end:
            x1 = min(self._draw_start.x(), self._draw_end.x())
            y1 = min(self._draw_start.y(), self._draw_end.y())
            x2 = max(self._draw_start.x(), self._draw_end.x())
            y2 = max(self._draw_start.y(), self._draw_end.y())
            draw_rect = QRect(x1, y1, x2 - x1, y2 - y1)
            painter.setPen(QPen(COLOR_DRAW, 2, Qt.PenStyle.DashLine))
            painter.fillRect(draw_rect, QColor(255, 69, 0, 30))
            painter.drawRect(draw_rect)

        painter.end()
