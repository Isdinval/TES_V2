"""
MainWindow: orchestration of the application.
"""

from __future__ import annotations
import os
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QComboBox, QSplitter,
    QStatusBar, QMessageBox, QFileDialog, QProgressBar, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core import screen_capture, mapping_store
from ui.canvas_view import CanvasView
from ui.element_form import ElementForm
from ui.mapping_list import MappingList


class DetectionWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, image: Image.Image, yolo, caption):
        super().__init__()
        self.image = image
        self.yolo = yolo
        self.caption = caption

    def run(self):
        try:
            from core import omniparser_bridge
            candidates = omniparser_bridge.detect_elements(self.image, self.yolo, self.caption)
            self.finished.emit(candidates)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, yolo=None, caption=None):
        super().__init__()
        self.setWindowTitle("TES V2 - Precision Element Mapping")
        self.resize(1280, 850)

        self._yolo = yolo
        self._caption = caption
        self._current_image: Image.Image | None = None
        self._current_resolution: tuple[int, int] = (0, 0)

        # UI State for special modes
        self._expecting_scroll_container = False
        self._expecting_scrollbar_target = False

        self._setup_ui()

    def _setup_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("App:"))
        self._app_input = QLineEdit("orthokis")
        self._app_input.setFixedWidth(100)
        toolbar.addWidget(self._app_input)

        toolbar.addWidget(QLabel("Écran:"))
        self._screen_input = QLineEdit("fiche_patient")
        self._screen_input.setFixedWidth(120)
        toolbar.addWidget(self._screen_input)

        toolbar.addWidget(QLabel("Monitor:"))
        self._monitor_combo = QComboBox()
        self._refresh_monitors()
        toolbar.addWidget(self._monitor_combo)

        self._capture_btn = QPushButton("📸 Capturer")
        self._capture_btn.clicked.connect(self._capture)
        toolbar.addWidget(self._capture_btn)

        self._detect_btn = QPushButton("🔍 Détecter (IA)")
        self._detect_btn.clicked.connect(self._detect)
        self._detect_btn.setEnabled(False)
        toolbar.addWidget(self._detect_btn)

        self._yolo_toggle = QPushButton("Afficher YOLO")
        self._yolo_toggle.setCheckable(True)
        self._yolo_toggle.setChecked(True)
        self._yolo_toggle.clicked.connect(self._on_yolo_toggle)
        toolbar.addWidget(self._yolo_toggle)

        toolbar.addStretch()

        self._candidate_count = QLabel("0 candidats")
        toolbar.addWidget(self._candidate_count)

        self._export_btn = QPushButton("💾 Exporter JSON")
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet("background: #2b5b84; color: white; font-weight: bold;")
        toolbar.addWidget(self._export_btn)

        root.addLayout(toolbar)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── Splitters ──────────────────────────────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = CanvasView()
        self._canvas.candidate_selected.connect(self._on_candidate_selected)
        self._canvas.bbox_drawn.connect(self._on_bbox_drawn)
        self._canvas.selection_cleared.connect(self._on_selection_cleared)
        self._canvas.point_sampled.connect(self._on_point_sampled)
        main_splitter.addWidget(self._canvas)

        self._form = ElementForm()
        self._form.element_confirmed.connect(self._on_element_confirmed)
        self._form.sampling_toggled.connect(self._on_sampling_toggled)
        self._form.scroll_container_requested.connect(self._on_scroll_container_requested)
        self._form.scrollbar_target_requested.connect(self._on_scrollbar_target_requested)
        self._form.setMinimumWidth(260)
        self._form.setMaximumWidth(340)
        main_splitter.addWidget(self._form)

        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)

        # ── Vertical splitter ─────────────────────────────────────────
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(main_splitter)

        self._mapping_list = MappingList()
        self._mapping_list.element_deleted.connect(self._on_element_deleted)
        # Handle internal export button
        self._mapping_list.export_requested.connect(self._on_export_clicked)

        self._mapping_list.setMaximumHeight(220)
        v_splitter.addWidget(self._mapping_list)

        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 1)

        root.addWidget(v_splitter)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(
            "Renseigne App + Écran, puis clique sur Capturer"
        )

        self._refresh_form_suggestions()

    # ------------------------------------------------------------------
    # Monitor management
    # ------------------------------------------------------------------

    def _refresh_monitors(self):
        self._monitor_combo.clear()
        try:
            monitors = screen_capture.list_monitors()
            for m in monitors:
                self._monitor_combo.addItem(m["name"], userData=m["id"])
        except Exception:
            self._monitor_combo.addItem("Monitor 1", userData=1)

    # ------------------------------------------------------------------
    # Capture & Detection
    # ------------------------------------------------------------------

    def _app_name(self) -> str:
        return self._app_input.text().strip()

    def _screen_name(self) -> str:
        return self._screen_input.text().strip()

    def _context_valid(self) -> bool:
        return bool(self._app_name() and self._screen_name())

    def _capture(self):
        if not self._context_valid():
            QMessageBox.warning(
                self,
                "Contexte manquant",
                "Renseigne les champs App et Écran avant de capturer.\n\n"
                "Exemple :\n  App → orthokis\n  Écran → fiche_patient",
            )
            return

        monitor_id = self._monitor_combo.currentData() or 1
        try:
            self._current_image, self._current_resolution = screen_capture.capture_monitor(monitor_id)
            self._canvas.set_image(self._current_image)

            # Restore mapped elements for this specific app::screen context
            self._restore_session()

            self._detect_btn.setEnabled(True)
            self._statusbar.showMessage(
                f"[{self._app_name()}::{self._screen_name()}] "
                f"Capture OK — {self._current_resolution[0]}×{self._current_resolution[1]}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur capture", str(e))

    def _restore_session(self):
        """
        Load previously mapped elements for the current app::screen context.
        Called after each capture so the correct elements are shown as green overlays.
        """
        try:
            elements = mapping_store.load_session(self._app_name(), self._screen_name())
            self._mapping_list.load_from_elements(elements)
            self._canvas.set_mapped_elements(self._mapping_list.get_elements())
            self._export_btn.setEnabled(len(elements) > 0)
            if elements:
                self._statusbar.showMessage(
                    f"[{self._app_name()}::{self._screen_name()}] "
                    f"{len(elements)} élément(s) restaurés"
                )
        except Exception as e:
            self._statusbar.showMessage(f"Erreur restauration session: {e}")

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
        self._progress.setRange(0, 0)
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
        self._statusbar.showMessage(
            f"[{self._app_name()}::{self._screen_name()}] "
            f"Détection terminée — {len(candidates)} éléments trouvés"
        )

    def _on_detection_error(self, msg: str):
        self._progress.setVisible(False)
        self._detect_btn.setEnabled(True)
        self._statusbar.showMessage(f"Erreur détection: {msg}")

    def _on_yolo_toggle(self, checked: bool):
        self._canvas.set_candidates_visible(checked)

    # ------------------------------------------------------------------
    # Canvas → Form wiring
    # ------------------------------------------------------------------

    def _on_candidate_selected(self, candidate: dict):
        bbox = {k: candidate[k] for k in ("x", "y", "w", "h")}
        correction = mapping_store.lookup_correction(bbox, self._app_name(), self._screen_name())
        self._form.set_bbox(bbox, source="yolo_accepted", correction=correction)
        self._canvas.set_active_overlays(self._form._scroll_container, self._form._scrollbar_target)

    def _on_bbox_drawn(self, bbox: dict):
        if self._expecting_scroll_container:
            self._form.set_scroll_container(bbox)
            self._expecting_scroll_container = False
            self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
            self._canvas.set_active_overlays(self._form._scroll_container, self._form._scrollbar_target)
            return

        correction = mapping_store.lookup_correction(bbox, self._app_name(), self._screen_name())
        self._form.set_bbox(bbox, source="human", correction=correction)
        self._canvas.set_active_overlays(self._form._scroll_container, self._form._scrollbar_target)

    def _on_selection_cleared(self):
        pass

    def _on_point_sampled(self, point: dict):
        if self._expecting_scrollbar_target:
            self._form.set_scrollbar_target(point)
            self._expecting_scrollbar_target = False
            self._canvas.set_sampling_mode(False)
            self._canvas.set_active_overlays(self._form._scroll_container, self._form._scrollbar_target)
            return

        self._form.add_sampled_point(point)
        # Update canvas to show the dots we just added
        self._canvas.set_sampled_points(self._form.get_sampled_points())

    # ------------------------------------------------------------------
    # Form → List wiring
    # ------------------------------------------------------------------

    def _on_element_confirmed(self, element: dict):
        self._mapping_list.add_element(element)
        self._canvas.set_mapped_elements(self._mapping_list.get_elements())
        self._export_btn.setEnabled(True)
        self._statusbar.showMessage(
            f"[{self._app_name()}::{self._screen_name()}] "
            f"Élément '{element['logical_key']}' ajouté"
        )
        # Refresh suggestions as a new screen might have been created (or context updated)
        self._refresh_form_suggestions()
        self._canvas.set_active_overlays(None, None)

    def _on_sampling_toggled(self, enabled: bool):
        self._canvas.set_sampling_mode(enabled)
        if enabled:
            # Show existing points if any
            self._canvas.set_sampled_points(self._form.get_sampled_points())
        else:
            self._canvas.set_sampled_points([])

    def _on_scroll_container_requested(self):
        self._expecting_scroll_container = True
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)
        self._statusbar.showMessage("Dessine la ZONE de scroll sur le canvas...")

    def _on_scrollbar_target_requested(self):
        self._expecting_scrollbar_target = True
        self._canvas.set_sampling_mode(True)
        self._statusbar.showMessage("Clique sur le POINT de la scrollbar...")

    def _refresh_form_suggestions(self):
        screens = mapping_store.get_all_screens_for_app(self._app_name())
        self._form.set_screen_suggestions(screens)

    def _on_element_deleted(self, _idx: int):
        self._canvas.set_mapped_elements(self._mapping_list.get_elements())
        self._export_btn.setEnabled(len(self._mapping_list.get_elements()) > 0)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export_clicked(self, _path=None, _app=None, _screen=None):
        """Note: arguments ignored as context is owned by MainWindow."""
        if not self._context_valid():
            QMessageBox.warning(
                self,
                "Contexte manquant",
                "Renseigne les champs App et Écran avant d'exporter.",
            )
            return

        elements = self._mapping_list.get_elements()
        if not elements:
            QMessageBox.warning(self, "Rien à exporter", "Aucun élément mappé.")
            return

        default_name = f"{self._app_name()}_{self._screen_name()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le mapping", default_name, "JSON (*.json)"
        )
        if not path:
            return

        try:
            mapping_store.export_mapping(
                elements=elements,
                app_name=self._app_name(),
                screen_name=self._screen_name(),
                resolution=self._current_resolution,
                output_path=path,
            )
            QMessageBox.information(
                self,
                "Export réussi",
                f"{len(elements)} élément(s) exportés vers:\n{path}\n\n"
                f"Contexte: {self._app_name()}::{self._screen_name()}\n"
                "Le corrections_store a été mis à jour.",
            )
            self._statusbar.showMessage(f"Exporté → {path}")
            self._refresh_form_suggestions()
        except Exception as e:
            QMessageBox.critical(self, "Erreur export", str(e))
