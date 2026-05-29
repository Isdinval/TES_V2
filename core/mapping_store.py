import json
import os
from datetime import datetime
from typing import Optional

from core.stable_id import compute_stable_id

CORRECTIONS_FILE = "corrections_store.json"


def load_corrections() -> dict:
    """
    Returns {stable_id: {logical_key, ui_type, action, path}}
    Persists human-validated mappings across runs.
    """
    if os.path.exists(CORRECTIONS_FILE):
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_corrections(corrections: dict) -> None:
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)


def update_corrections(elements: list[dict]) -> None:
    """
    Merge human-validated elements into the corrections store.
    Called on export.
    """
    corrections = load_corrections()
    for el in elements:
        sid = el.get("stable_id")
        if sid:
            corrections[sid] = {
                "logical_key": el.get("logical_key", ""),
                "ui_type": el.get("ui_type", ""),
                "action": el.get("action", ""),
                "path": el.get("path", ""),
            }
    save_corrections(corrections)


def lookup_correction(bbox_relative: dict) -> Optional[dict]:
    """
    Given a bbox, check if we have a prior human correction for it.
    Returns the correction dict or None.
    """
    sid = compute_stable_id(bbox_relative)
    corrections = load_corrections()
    result = corrections.get(sid)
    if result:
        return {"stable_id": sid, **result}
    return None


def build_element(
    bbox_relative: dict,
    logical_key: str,
    ui_type: str,
    action: str,
    path: str,
    source: str,
) -> dict:
    sid = compute_stable_id(bbox_relative)
    bx = bbox_relative
    click_target = {
        "x": round(bx["x"] + bx["w"] / 2, 4),
        "y": round(bx["y"] + bx["h"] / 2, 4),
    }
    return {
        "stable_id": sid,
        "logical_key": logical_key,
        "ui_type": ui_type,
        "action": action,
        "path": path,
        "bbox_relative": bbox_relative,
        "click_target": click_target,
        "source": source,
    }


def export_mapping(
    elements: list[dict],
    app_name: str,
    screen_name: str,
    resolution: tuple[int, int],
    output_path: str,
) -> None:
    payload = {
        "meta": {
            "app": app_name,
            "screen": screen_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "resolution": list(resolution),
        },
        "elements": elements,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    update_corrections(elements)
