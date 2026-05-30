"""
Thin wrapper around OmniParser V2 (YOLO + Florence-2).
Returns a list of bbox candidates for the GUI to display.
No auto-mapping logic here — that's the human's job.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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


def _clip(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _xyxy_to_candidate(
    box: Iterable[float],
    image_size: tuple[int, int],
    description: str,
    confidence: float = 1.0,
    interactable: bool = True,
) -> BboxCandidate | None:
    width, height = image_size
    x1, y1, x2, y2 = [float(v) for v in box]
    x1, x2 = sorted((_clip(x1, 0, width), _clip(x2, 0, width)))
    y1, y2 = sorted((_clip(y1, 0, height), _clip(y2, 0, height)))
    if x2 <= x1 or y2 <= y1:
        return None
    return BboxCandidate(
        x=round(x1 / width, 4),
        y=round(y1 / height, 4),
        w=round((x2 - x1) / width, 4),
        h=round((y2 - y1) / height, 4),
        description=description,
        confidence=round(float(confidence), 4),
        interactable=interactable,
    )


def _bbox_area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(box1: list[float], box2: list[float]) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _overlap_ratio(box1: list[float], box2: list[float]) -> float:
    intersection = _intersection_area(box1, box2)
    area1 = _bbox_area(box1)
    area2 = _bbox_area(box2)
    union = area1 + area2 - intersection + 1e-6
    if area1 <= 0 or area2 <= 0:
        return 0.0
    return max(intersection / union, intersection / area1, intersection / area2)


def _ocr_quad_to_xyxy(quad) -> list[float]:
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    return [min(xs), min(ys), max(xs), max(ys)]


def _run_easyocr(
    image: Image.Image, weights_root: Path | None
) -> tuple[list[str], list[list[float]]]:
    try:
        import easyocr
        import numpy as np
    except ImportError as e:
        print(f"[OmniParser] EasyOCR unavailable, continuing without OCR boxes: {e}")
        return [], []

    kwargs = {"download_enabled": False}
    easyocr_dir = weights_root / "EasyOCR" if weights_root else None
    if easyocr_dir and easyocr_dir.exists():
        kwargs["model_storage_directory"] = str(easyocr_dir)
        kwargs["user_network_directory"] = str(easyocr_dir)

    try:
        reader = easyocr.Reader(["en"], **kwargs)
        result = reader.readtext(
            np.array(image.convert("RGB")), paragraph=False, text_threshold=0.9
        )
    except Exception as e:
        print(f"[OmniParser] EasyOCR failed, continuing without OCR boxes: {e}")
        return [], []

    texts = [item[1] for item in result]
    boxes = [_ocr_quad_to_xyxy(item[0]) for item in result]
    return texts, boxes


def _predict_yolo_boxes(
    image: Image.Image,
    yolo_model,
    box_threshold: float,
    iou_threshold: float,
    imgsz: int,
) -> list[dict]:
    result = yolo_model.predict(
        source=image,
        conf=box_threshold,
        imgsz=imgsz,
        iou=iou_threshold,
    )
    boxes = result[0].boxes
    xyxy = boxes.xyxy.detach().cpu().tolist()
    confidences = boxes.conf.detach().cpu().tolist()
    return [
        {
            "bbox": [float(v) for v in box],
            "confidence": float(confidence),
            "description": "",
            "interactable": True,
        }
        for box, confidence in zip(xyxy, confidences)
    ]


def _box_inside(inner: list[float], outer: list[float], threshold: float = 0.8) -> bool:
    area = _bbox_area(inner)
    if area <= 0:
        return False
    return _intersection_area(inner, outer) / area >= threshold


def _merge_ocr_and_yolo_boxes(
    yolo_boxes: list[dict],
    ocr_text: list[str],
    ocr_boxes: list[list[float]],
    iou_threshold: float,
) -> list[dict]:
    candidates = [
        {
            "bbox": [float(v) for v in box],
            "confidence": 1.0,
            "description": text,
            "interactable": False,
        }
        for text, box in zip(ocr_text, ocr_boxes)
        if _bbox_area([float(v) for v in box]) > 0
    ]

    for yolo_box in yolo_boxes:
        box = yolo_box["bbox"]
        if _bbox_area(box) <= 0:
            continue

        # OmniParser merges OCR text into a detected icon/button when the text is
        # inside the YOLO box. That is important for buttons: the final candidate
        # should be the clickable UI element, not only the text glyphs.
        contained_ocr = [ocr for ocr in candidates if _box_inside(ocr["bbox"], box)]
        if contained_ocr:
            for ocr in contained_ocr:
                candidates.remove(ocr)
            yolo_box["description"] = " ".join(ocr["description"] for ocr in contained_ocr)
            candidates.append(yolo_box)
            continue

        # If the YOLO box is fully inside an OCR box, keep the OCR element only.
        if any(_box_inside(box, ocr["bbox"]) for ocr in candidates):
            continue

        # Suppress duplicate YOLO boxes, keeping the smaller one like OmniParser's
        # overlap pruning.
        duplicate = False
        for existing in list(candidates):
            if _overlap_ratio(box, existing["bbox"]) <= iou_threshold:
                continue
            if _bbox_area(box) > _bbox_area(existing["bbox"]):
                duplicate = True
                break
            candidates.remove(existing)
        if not duplicate:
            candidates.append(yolo_box)

    return candidates


def _caption_icon_boxes(
    image: Image.Image,
    candidates: list[dict],
    caption_model_processor,
    batch_size: int = 128,
) -> None:
    if not caption_model_processor:
        return

    try:
        import torch
    except ImportError as e:
        print(f"[OmniParser] Torch unavailable, skipping Florence captions: {e}")
        return

    model = caption_model_processor["model"]
    processor = caption_model_processor["processor"]
    device = model.device
    icon_candidates = [c for c in candidates if c["interactable"] and not c["description"]]
    if not icon_candidates:
        return

    crops: list[Image.Image] = []
    for candidate in icon_candidates:
        x1, y1, x2, y2 = [int(v) for v in candidate["bbox"]]
        crop = image.crop((x1, y1, x2, y2)).resize((64, 64))
        crops.append(crop)

    generated_texts: list[str] = []
    prompt = ""
    for start in range(0, len(crops), batch_size):
        batch = crops[start:start + batch_size]
        if device.type == "cuda":
            inputs = processor(
                images=batch,
                text=[prompt] * len(batch),
                return_tensors="pt",
                do_resize=False,
            ).to(device=device, dtype=torch.float16)
        else:
            inputs = processor(
                images=batch,
                text=[prompt] * len(batch),
                return_tensors="pt",
            ).to(device=device)
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=20,
            num_beams=1,
            do_sample=False,
        )
        generated_texts.extend(
            text.strip()
            for text in processor.batch_decode(generated_ids, skip_special_tokens=True)
        )

    for candidate, text in zip(icon_candidates, generated_texts):
        candidate["description"] = text


def _run_detection_local(
    image: Image.Image,
    yolo_model,
    caption_model_processor,
    box_threshold: float,
    iou_threshold: float,
    imgsz: int,
) -> list[BboxCandidate]:
    image = image.convert("RGB")
    weights_root = None
    if caption_model_processor:
        weights_root = caption_model_processor.get("weights_dir")

    ocr_text, ocr_bbox = _run_easyocr(image, weights_root)
    yolo_boxes = _predict_yolo_boxes(image, yolo_model, box_threshold, iou_threshold, imgsz)
    parsed_candidates = _merge_ocr_and_yolo_boxes(
        yolo_boxes, ocr_text, ocr_bbox, iou_threshold
    )
    _caption_icon_boxes(image, parsed_candidates, caption_model_processor)

    candidates: list[BboxCandidate] = []
    for candidate in parsed_candidates:
        bbox_candidate = _xyxy_to_candidate(
            candidate["bbox"],
            image.size,
            candidate["description"],
            candidate["confidence"],
            candidate["interactable"],
        )
        if bbox_candidate:
            candidates.append(bbox_candidate)
    return candidates


def _run_detection_with_omniparser_utils(
    image: Image.Image,
    yolo_model,
    caption_model_processor,
    box_threshold: float,
    iou_threshold: float,
    imgsz: int,
) -> list[BboxCandidate]:
    from util.utils import get_som_labeled_img, check_ocr_box

    w, h = image.size
    box_overlay_ratio = w / 3200
    draw_bbox_config = {
        "text_scale": 0.8 * box_overlay_ratio,
        "text_thickness": max(int(2 * box_overlay_ratio), 1),
        "text_padding": max(int(3 * box_overlay_ratio), 1),
        "thickness": max(int(3 * box_overlay_ratio), 1),
    }

    ocr_bbox_rslt, _ = check_ocr_box(
        image,
        display_img=False,
        output_bb_format="xyxy",
        goal_filtering=None,
        easyocr_args={"paragraph": False, "text_threshold": 0.9},
        use_paddleocr=False,
    )
    ocr_text, ocr_bbox = ocr_bbox_rslt

    _, label_coordinates, parsed_content_list = get_som_labeled_img(
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

    candidates = []
    for coords, content in zip(label_coordinates.values(), parsed_content_list):
        if len(coords) != 4:
            continue
        cx, cy, bw, bh = coords
        description = content.get("content", "") if isinstance(content, dict) else str(content)
        interactable = content.get("interactivity", True) if isinstance(content, dict) else True
        confidence = content.get("confidence", 1.0) if isinstance(content, dict) else 1.0
        candidates.append(
            BboxCandidate(
                x=round(cx - bw / 2, 4),
                y=round(cy - bh / 2, 4),
                w=round(bw, 4),
                h=round(bh, 4),
                description=description,
                confidence=confidence,
                interactable=interactable,
            )
        )
    return candidates


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
        candidates = _run_detection_with_omniparser_utils(
            image,
            yolo_model,
            caption_model_processor,
            box_threshold,
            iou_threshold,
            imgsz,
        )
        if candidates:
            return candidates
        print("[OmniParser] util pipeline returned 0 candidates; trying local pipeline")
    except ImportError as e:
        print(f"[OmniParser] util pipeline unavailable; trying local pipeline: {e}")
    except Exception as e:
        print(f"[OmniParser] util pipeline failed; trying local pipeline: {e}")

    try:
        return _run_detection_local(
            image,
            yolo_model,
            caption_model_processor,
            box_threshold,
            iou_threshold,
            imgsz,
        )
    except Exception as e:
        print(f"[OmniParser] Detection error: {e}")
        return []


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
        ).to(device)
        caption_model_processor = {
            "processor": processor,
            "model": model,
            "weights_dir": resolved_weights_dir,
        }

        print(f"[OmniParser] Models loaded from {resolved_weights_dir} on {device}")
        return yolo_model, caption_model_processor

    except Exception as e:
        print(f"[OmniParser] Could not load models: {e}")
        return None, None
