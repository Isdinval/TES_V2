"""
Thin wrapper around OmniParser V2 (YOLO + Florence-2).
Returns a list of bbox candidates for the GUI to display.
No auto-mapping logic here — that's the human's job.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

YOLO_WEIGHT_FILENAMES = ("model.pt", "best.pt")


@dataclass
class BboxCandidate:
    # All coords are relative (0.0–1.0)
    x: float
    y: float
    w: float
    h: float
    description: str      # Florence-2 caption
    confidence: float     # YOLO detection confidence
    interactable: bool    # YOLO interactable prediction (V2)

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "description": self.description,
            "confidence": self.confidence,
            "interactable": self.interactable,
        }


def run_detection(
    image: Image.Image,
    yolo_model,
    caption_model_processor,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    imgsz: int = 1920,
) -> list[BboxCandidate]:
    """
    Run OmniParser V2 detection on image.
    Returns list of BboxCandidate (relative coords).
    
    yolo_model and caption_model_processor are loaded once at startup
    and passed in to avoid reloading on each call.
    """
    try:
        from util.utils import get_som_labeled_img, check_ocr_box
    except ImportError:
        # OmniParser utils not available — return empty list gracefully
        return []

    w, h = image.size

    draw_bbox_config = {
        "text_scale": 0.8,
        "text_thickness": 2,
        "text_padding": 3,
        "thickness": 3,
    }

    try:
        ocr_bbox_rslt, _ = check_ocr_box(
            image,
            display_img=False,
            output_bb_format="xyxy",
            goal_filtering=None,
            easyocr_args={"paragraph": False, "text_threshold": 0.9},
            use_paddleocr=False,
        )
        ocr_text, ocr_bbox = ocr_bbox_rslt

        _, label_coordinates, filtered_boxes_elem = get_som_labeled_img(
            image,
            yolo_model,
            BOX_TRESHOLD=box_threshold,
            output_coord_in_ratio=True,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=caption_model_processor,
            ocr_text=ocr_text,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
        )
    except Exception as e:
        print(f"[OmniParser] Detection error: {e}")
        return []

    # filtered_boxes_elem: list of {type, bbox, content, interactivity}
    # bbox is already in xyxy ratio (output_coord_in_ratio=True)
    candidates = []
    for box in filtered_boxes_elem:
        coords = box.get("bbox")
        if not coords or len(coords) != 4:
            continue
        x1, y1, x2, y2 = coords
        bx = round(float(x1), 4)
        by = round(float(y1), 4)
        bw = round(float(x2) - float(x1), 4)
        bh = round(float(y2) - float(y1), 4)
        if bw <= 0 or bh <= 0 or bx < 0 or by < 0 or bx + bw > 1.01 or by + bh > 1.01:
            continue
        candidates.append(
            BboxCandidate(
                x=bx, y=by, w=bw, h=bh,
                description=str(box.get("content") or ""),
                confidence=1.0,
                interactable=bool(box.get("interactivity", True)),
            )
        )

    print(f"[OmniParser] {len(candidates)} candidates returned")
    return candidates


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate_weights_dirs(weights_dir: str | os.PathLike[str] | None) -> list[Path]:
    candidates: list[Path] = []

    def add(path: str | os.PathLike[str] | None):
        if not path:
            return
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            # Prefer paths relative to the project root so launching main.py from
            # another working directory still finds the local OmniParser weights.
            resolved = _project_root() / resolved
        if resolved not in candidates:
            candidates.append(resolved)

    add(os.environ.get("TES_OMNIPARSER_WEIGHTS_DIR"))
    add(os.environ.get("OMNIPARSER_WEIGHTS_DIR"))
    add(weights_dir)

    if weights_dir is None:
        # OmniParser releases and older TES installs are commonly named either
        # `weight` (singular) or `weights` (plural). Support both layouts.
        add("weight")
        add("weights")

    for dirname in ("weight", "weights"):
        cwd_candidate = Path.cwd() / dirname
        if cwd_candidate not in candidates:
            candidates.append(cwd_candidate)

    return candidates


def _resolve_yolo_weights_path(weights_root: Path) -> Path | None:
    for filename in YOLO_WEIGHT_FILENAMES:
        yolo_path = weights_root / "icon_detect" / filename
        if yolo_path.exists():
            return yolo_path
    return None


def _resolve_weights_dir(weights_dir: str | os.PathLike[str] | None = None) -> Path | None:
    for candidate in _candidate_weights_dirs(weights_dir):
        yolo_path = _resolve_yolo_weights_path(candidate)
        florence_path = candidate / "icon_caption_florence"
        if yolo_path is not None and florence_path.exists():
            return candidate
    return None


def load_models(weights_dir: str | os.PathLike[str] | None = None):
    """
    Load YOLO and Florence-2 models once at startup.
    Returns (yolo_model, caption_model_processor) or (None, None) if unavailable.
    """
    try:
        from ultralytics import YOLO
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        resolved_weights_dir = _resolve_weights_dir(weights_dir)
        if resolved_weights_dir is None:
            checked = ", ".join(str(path) for path in _candidate_weights_dirs(weights_dir))
            print(
                "[OmniParser] Weights not found. Expected "
                "icon_detect/model.pt (or best.pt) and icon_caption_florence "
                "in one of: "
                f"{checked}"
            )
            return None, None

        yolo_path = _resolve_yolo_weights_path(resolved_weights_dir)
        florence_path = resolved_weights_dir / "icon_caption_florence"

        yolo_model = YOLO(str(yolo_path))

        device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = AutoProcessor.from_pretrained(str(florence_path), trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            str(florence_path), trust_remote_code=True
        ).to(device).float()  # force float32 — avoids half/float bias mismatch on CUDA
        caption_model_processor = {"processor": processor, "model": model}

        print(f"[OmniParser] Models loaded from {resolved_weights_dir} on {device}")
        return yolo_model, caption_model_processor

    except Exception as e:
        print(f"[OmniParser] Could not load models: {e}")
        return None, None