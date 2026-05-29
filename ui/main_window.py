"""
MainWindow: assembles CanvasView + ElementForm + MappingList.
Handles capture, detection, and wiring between components.
"""

from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QProgressBar,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject

from ui.canvas_view import CanvasView
from ui.element_form import ElementForm
from ui.mapping_list import MappingList
from core import screen_capture, omniparser_bridge, mapping_store


# ------------------------------------------------------------------
# Worker thread for detection (keeps UI responsive)
# ------------------------------------------------------------------

class DetectionWorker(QObject):
    finished = pyqtSignal(list)   # list of BboxCandidate dicts
    error = pyqtSignal(str)

    def __init__(self, image, yolo_model, caption_model_processor):
        super().__init__()
        self._image = image
        self._yolo = yolo_model
        self._caption = caption_model_processor

    def run(self):
        try:
            candidates = omniparser_bridge.run_detection(
                self._image, self._yolo, self._caption
            )
            self.finished.emit([c.to_dict() for c in candidates])
        except Exception as e:
            self.error.emit(str(e))


# ------------------------------------------------------------------
# Main window
# ------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, yolo_model=None, caption_model_processor=None):
        super().__init__()
        self._yolo = yolo_model
        self._caption = caption_model_processor
        self._current_image = None
        self._current_resolution = (1920, 1080)
        self._detection_thread: QThread | None = None

        self.setWindowTitle("TES v2 — UI Mapper")
        self.resize(1400, 900)
        self._setup_ui()
        self._refresh_monitors()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Toolbar ──────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Moniteur:"))
        self._monitor_combo = QComboBox()
        self._monitor_combo.setMinimumWidth(220)
        toolbar.addWidget(self._monitor_combo)

        self._capture_btn = QPushButton("📸 Capturer")
        self._capture_btn.clicked.connect(self._capture)
        self._capture_btn.setStyleSheet(
            "QPushButton { background: #3a5a3a; color: white; padding: 5px 12px; border-radius: 4px; }"
            "QPushButton:hover { background: #4a7a4a; }"
        )
        toolbar.addWidget(self._capture_btn)

        self._detect_btn = QPushButton("🔍 Détecter (YOLO)")
        self._detect_btn.clicked.connect(self._detect)
        self._detect_btn.setEnabled(False)
        self._detect_btn.setStyleSheet(
            "QPushButton { background: #3a3a6a; color: white; padding: 5px 12px; border-radius: 4px; }"
            "QPushButton:hover { background: #4a4a8a; }"
            "QPushButton:disabled { background: #333; color: #666; }"
        )
        toolbar.addWidget(self._detect_btn)

        self._candidate_count = QLabel("—")
        self._candidate_count.setStyleSheet("color: #aaa;")
        toolbar.addWidget(self._candidate_count)

        toolbar.addStretch()

        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setVisible(False)
        toolbar.addWidget(self._progress)

        root.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        root.addWidget(sep)

        # ── Main area ─────────────────────────────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Canvas (left, large)
        self._canvas = CanvasView()
        self._canvas.candidate_selected.connect(self._on_candidate_selected)
        self._canvas.bbox_drawn.connect(self._on_bbox_drawn)
        self._canvas.selection_cleared.connect(self._on_selection_cleared)
        main_splitter.addWidget(self._canvas)

        # Form (right, narrow)
        self._form = ElementForm()
        self._form.element_confirmed.connect(self._on_element_confirmed)
        self._form.setMinimumWidth(260)
        self._form.setMaximumWidth(340)
        main_splitter.addWidget(self._form)

        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)

        # ── Vertical splitter (canvas+form top, list bottom) ──────────
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(main_splitter)

        self._mapping_list = MappingList()
        self._mapping_list.export_requested.connect(self._on_export)
        self._mapping_list.setMaximumHeight(220)
        v_splitter.addWidget(self._mapping_list)

        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 1)

        root.addWidget(v_splitter)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Prêt")

    # ------------------------------------------------------------------
    # Monitor management
    # ------------------------------------------------------------------

    def _refresh_monitors(self):
        self._monitor_combo.clear()
        try:
            monitors = screen_capture.list_monitors()
            for m in monitors:
                self._monitor_combo.addItem(m["name"], userData=m["id"])
        except Exception as e:
            self._monitor_combo.addItem("Monitor 1", userData=1)

    # ------------------------------------------------------------------
    # Capture & Detection
    # ------------------------------------------------------------------

    def _capture(self):
        monitor_id = self._monitor_combo.currentData() or 1
        try:
            self._current_image, self._current_resolution = screen_capture.capture_monitor(monitor_id)
            self._canvas.set_image(self._current_image)
            self._canvas.set_mapped_bboxes([])
            self._detect_btn.setEnabled(True)
            self._statusbar.showMessage(
                f"Capture OK — {self._current_resolution[0]}×{self._current_resolution[1]}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur capture", str(e))

    def _detect(self):
        if self._current_image is None:
            return
        if self._yolo is None:
            QMessageBox.warning(
                self,
                "Modèles non chargés",
                "Les modèles YOLO/Florence ne sont pas chargés.\n"
                "Place les poids OmniParser V2 dans le dossier `weights` ou `weight` "
                "à la racine du projet, avec `icon_detect/model.pt` "
                "(ou `best.pt`), puis relance main.py.",
            )
            return

        self._detect_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # indeterminate
        self._statusbar.showMessage("Détection en cours…")

        self._worker = DetectionWorker(self._current_image, self._yolo, self._caption)
        self._detection_thread = QThread()
        self._worker.moveToThread(self._detection_thread)
        self._detection_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_detection_done)
        self._worker.error.connect(self._on_detection_error)
        self._worker.finished.connect(self._detection_thread.quit)
        self._detection_thread.start()

    def _on_detection_done(self, candidates: list[dict]):
        self._progress.setVisible(False)
        self._detect_btn.setEnabled(True)
        self._canvas.set_candidates(candidates)
        self._candidate_count.setText(f"{len(candidates)} candidats")
        self._statusbar.showMessage(f"Détection terminée — {len(candidates)} éléments trouvés")

    def _on_detection_error(self, msg: str):
        self._progress.setVisible(False)
        self._detect_btn.setEnabled(True)
        self._statusbar.showMessage(f"Erreur détection: {msg}")

    # ------------------------------------------------------------------
    # Canvas → Form wiring
    # ------------------------------------------------------------------

    def _on_candidate_selected(self, candidate: dict):
        bbox = {k: candidate[k] for k in ("x", "y", "w", "h")}
        correction = mapping_store.lookup_correction(bbox)
        self._form.set_bbox(bbox, source="yolo_accepted", correction=correction)

    def _on_bbox_drawn(self, bbox: dict):
        correction = mapping_store.lookup_correction(bbox)
        self._form.set_bbox(bbox, source="human", correction=correction)

    def _on_selection_cleared(self):
        pass  # form stays as-is until user draws

    # ------------------------------------------------------------------
    # Form → List wiring
    # ------------------------------------------------------------------

    def _on_element_confirmed(self, element: dict):
        self._mapping_list.add_element(element)
        # Refresh green overlay on canvas
        self._canvas.set_mapped_bboxes(self._mapping_list.get_bboxes())
        self._statusbar.showMessage(f"Élément '{element['logical_key']}' ajouté")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export(self, output_path: str, app_name: str, screen_name: str):
        elements = self._mapping_list.get_elements()
        try:
            mapping_store.export_mapping(
                elements=elements,
                app_name=app_name,
                screen_name=screen_name,
                resolution=self._current_resolution,
                output_path=output_path,
            )
            QMessageBox.information(
                self,
                "Export réussi",
                f"{len(elements)} élément(s) exportés vers:\n{output_path}\n\n"
                f"Le corrections_store a été mis à jour.",
            )
            self._statusbar.showMessage(f"Exporté → {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export", str(e))
