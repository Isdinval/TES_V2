"""
CanvasView: custom widget to display the screenshot, YOLO candidates,
and allow the user to draw/click bboxes.
"""

from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QCursor, QFont
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint


COLOR_CANDIDATE = QColor(255, 255, 0, 180)        # Yellow (YOLO)
COLOR_CANDIDATE_HOVER = QColor(255, 255, 0, 255)  # Bright Yellow
COLOR_SELECTED = QColor(255, 165, 0, 255)         # Orange
COLOR_MAPPED = QColor(0, 255, 0, 255)             # Green
COLOR_DRAW = QColor(255, 69, 0, 255)              # OrangeRed
COLOR_SAMPLED = QColor(255, 255, 0, 255)          # Yellow for dots
COLOR_SCROLL_CONTAINER = QColor(150, 150, 255, 255) # Light Blue/Purple


class CanvasView(QWidget):
    bbox_drawn = pyqtSignal(dict)           # {x, y, w, h} in relative coords
    candidate_selected = pyqtSignal(dict)   # {x, y, w, h, description, ...}
    selection_cleared = pyqtSignal()
    point_sampled = pyqtSignal(dict)        # {x, y} in relative coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap: QPixmap | None = None
        self._candidates: list[dict] = []
        self._mapped_elements: list[dict] = []
        self._show_candidates = True

        self._hover_idx: int | None = None
        self._selected_idx: int | None = None

        self._drawing = False
        self._draw_start: QPoint | None = None
        self._draw_end: QPoint | None = None

        self._sampling_mode = False
        self._sampled_points: list[dict] = []

        self._active_scroll_container: dict | None = None
        self._active_scrollbar_target: dict | None = None

        # Geometry cache (screen space)
        self._cached_image_rect = QRect()
        self._candidate_rects: list[QRect] = []
        self._mapped_rects: list[QRect] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_image(self, pil_image) -> None:
        if pil_image is None:
            self._pixmap = None
        else:
            # Convert PIL to QPixmap
            from PIL.ImageQt import ImageQt
            qimg = ImageQt(pil_image)
            self._pixmap = QPixmap.fromImage(qimg)

        self._update_geometry_cache()
        self.update()

    def set_candidates(self, candidates: list[dict]) -> None:
        self._candidates = candidates
        self._selected_idx = None
        self._update_geometry_cache()
        self.update()

    def set_mapped_elements(self, elements: list[dict]) -> None:
        self._mapped_elements = elements
        self._update_geometry_cache()
        self.update()

    def set_sampling_mode(self, enabled: bool) -> None:
        self._sampling_mode = enabled
        if enabled:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.unsetCursor()
            self._sampled_points = []
        self.update()

    def set_sampled_points(self, points: list[dict]) -> None:
        """Update the list of points to display (relative coords)."""
        self._sampled_points = points
        self.update()

    def set_active_overlays(self, scroll_container: dict | None, scrollbar_target: dict | None):
        self._active_scroll_container = scroll_container
        self._active_scrollbar_target = scrollbar_target
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

            # Draw scroll container if present
            sc = el.get("scroll_container")
            if sc and "bbox_relative" in sc:
                sc_bbox = sc["bbox_relative"]
                sc_rect = self._rel_to_screen(sc_bbox["x"], sc_bbox["y"], sc_bbox["w"], sc_bbox["h"])
                painter.setPen(QPen(COLOR_SCROLL_CONTAINER, 2, Qt.PenStyle.DashLine))
                painter.drawRect(sc_rect)

            # Draw scrollbar target if present
            sb = el.get("scrollbar_target")
            if sb:
                sb_pos = self._rel_to_screen(sb["x"], sb["y"])
                painter.setPen(QPen(COLOR_SCROLL_CONTAINER, 2))
                painter.setBrush(COLOR_SCROLL_CONTAINER)
                painter.drawEllipse(sb_pos.topLeft(), 4, 4)

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
                    # Display scroll step if > 0
                    step = choice.get("scroll_steps", 0)
                    if step > 0:
                        painter.setPen(QPen(Qt.GlobalColor.white))
                        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                        painter.drawText(c_pos.topLeft() + QPoint(5, 0), str(step))

        # Draw active overlays (being edited)
        if self._active_scroll_container:
            sc_bbox = self._active_scroll_container
            if "bbox_relative" in sc_bbox: sc_bbox = sc_bbox["bbox_relative"]
            sc_rect = self._rel_to_screen(sc_bbox["x"], sc_bbox["y"], sc_bbox["w"], sc_bbox["h"])
            painter.setPen(QPen(COLOR_SCROLL_CONTAINER, 3, Qt.PenStyle.DashLine))
            painter.drawRect(sc_rect)

        if self._active_scrollbar_target:
            sb = self._active_scrollbar_target
            sb_pos = self._rel_to_screen(sb["x"], sb["y"])
            painter.setPen(QPen(COLOR_SCROLL_CONTAINER, 3))
            painter.setBrush(COLOR_SCROLL_CONTAINER)
            painter.drawEllipse(sb_pos.topLeft(), 6, 6)

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
