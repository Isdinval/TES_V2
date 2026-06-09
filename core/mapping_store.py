import json
import os
import uuid
from datetime import datetime
from typing import Optional

from core.stable_id import compute_stable_id

CORRECTIONS_FILE = "corrections_store.json"


# ------------------------------------------------------------------
# Low-level store access
# ------------------------------------------------------------------

def _context_key(app_name: str, screen_name: str) -> str:
    """Composite key used as top-level dict key in corrections_store.json."""
    return f"{app_name.strip()}::{screen_name.strip()}"


def load_corrections() -> dict:
    """
    Returns the full corrections store:
    { "app::screen": { stable_id: {logical_key, ui_type, action, path, bbox_relative, source, ...} } }
    """
    if os.path.exists(CORRECTIONS_FILE):
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_corrections(corrections: dict) -> None:
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)


def load_corrections_for(app_name: str, screen_name: str) -> dict:
    """
    Returns { stable_id: {...} } for a specific app/screen context.
    Returns empty dict if context not found.
    """
    key = _context_key(app_name, screen_name)
    return load_corrections().get(key, {})


def get_all_screens_for_app(app_name: str) -> list[str]:
    """
    Scans the full corrections store and returns a list of unique screen names
    for the given app.
    """
    corrections = load_corrections()
    screens = set()
    prefix = f"{app_name.strip()}::"
    for key in corrections.keys():
        if key.startswith(prefix):
            screen_name = key.replace(prefix, "", 1)
            screens.add(screen_name)
    return sorted(list(screens))


def update_corrections(
    elements: list[dict],
    app_name: str,
    screen_name: str,
) -> None:
    """
    Merge human-validated elements into the corrections store
    under the correct app::screen context.
    """
    corrections = load_corrections()
    key = _context_key(app_name, screen_name)
    if key not in corrections:
        corrections[key] = {}

    for el in elements:
        sid = el.get("stable_id")
        if sid:
            # Store all relevant fields for session restoration
            data = {
                "logical_key": el.get("logical_key", ""),
                "ui_type": el.get("ui_type", ""),
                "action": el.get("action", ""),
                "path": el.get("path", ""),
                "source": el.get("source", "human"),
                "created_at": el.get("created_at", datetime.now().isoformat()),
            }
            # Optional fields
            if "bbox_relative" in el:
                data["bbox_relative"] = el["bbox_relative"]
            if "expected_value" in el:
                data["expected_value"] = el["expected_value"]
            if "scroll_config" in el:
                data["scroll_config"] = el["scroll_config"]
            if "drag_target" in el:
                data["drag_target"] = el["drag_target"]
            if "choices" in el:
                data["choices"] = el["choices"]
            if "parent_scroll_area" in el:
                data["parent_scroll_area"] = el["parent_scroll_area"]
            if "requires_scroll" in el:
                data["requires_scroll"] = el["requires_scroll"]
            if "navigation_config" in el:
                data["navigation_config"] = el["navigation_config"]

            corrections[key][sid] = data

    save_corrections(corrections)


# ------------------------------------------------------------------
# Session restore
# ------------------------------------------------------------------

def load_session(app_name: str, screen_name: str) -> list[dict]:
    """
    Reconstruit la liste des éléments depuis corrections_store.json
    pour un contexte app/screen donné, triée par created_at.
    """
    context = load_corrections_for(app_name, screen_name)
    elements_data = []
    for sid, data in context.items():
        elements_data.append({"stable_id": sid, **data})

    # Sort by created_at to preserve sequence
    elements_data.sort(key=lambda x: x.get("created_at", ""))

    elements = []
    for data in elements_data:
        bbox = data.get("bbox_relative")

        # Build based on whether it is a standard element or an instruction
        if bbox:
            scroll_cfg = data.get("scroll_config", {})
            nav_cfg = data.get("navigation_config", {})

            element = build_element(
                bbox_relative=bbox,
                logical_key=data.get("logical_key", ""),
                ui_type=data.get("ui_type", ""),
                action=data.get("action", ""),
                path=data.get("path", ""),
                source=data.get("source", "human"),
                expected_value=data.get("expected_value", ""),
                scroll_direction=scroll_cfg.get("direction", "down"),
                scroll_amount=scroll_cfg.get("amount", 1),
                drag_target=data.get("drag_target", ""),
                choices=data.get("choices", []),
                navigation_target=nav_cfg.get("target_screen", "") if nav_cfg else "",
                parent_scroll_area=data.get("parent_scroll_area", ""),
                requires_scroll=data.get("requires_scroll", False),
                created_at=data.get("created_at"),
            )
        else:
            # Instruction element
            element = build_scroll_instruction(
                target_scroll_area=data.get("parent_scroll_area", ""),
                direction=data.get("scroll_config", {}).get("direction", "down"),
                amount=data.get("scroll_config", {}).get("amount", 1),
                created_at=data.get("created_at"),
            )
            element["stable_id"] = data["stable_id"] # Preserve ID

        elements.append(element)
    return elements


# ------------------------------------------------------------------
# Element helpers
# ------------------------------------------------------------------

def lookup_correction(
    bbox_relative: dict,
    app_name: str,
    screen_name: str,
) -> Optional[dict]:
    """
    Check if we have a prior human correction for this bbox
    in the given app/screen context.
    Returns the correction dict or None.
    """
    sid = compute_stable_id(bbox_relative)
    context = load_corrections_for(app_name, screen_name)
    result = context.get(sid)
    if result:
        return {"stable_id": sid, **result}
    return None


def compute_click_target(bbox_relative: dict, ui_type: str, extra_params: Optional[dict] = None) -> Optional[dict]:
    """
    Calcule le point de clic optimal selon le type d'UI.
    """
    bx = bbox_relative
    if ui_type == "scroll_area":
        return None

    if ui_type in ("checkbox", "radio"):
        return {
            "x": round(bx["x"] + bx["w"] * 0.15, 4),
            "y": round(bx["y"] + bx["h"] * 0.5, 4),
        }

    # Default: center
    return {
        "x": round(bx["x"] + bx["w"] / 2, 4),
        "y": round(bx["y"] + bx["h"] / 2, 4),
    }


def build_element(
    bbox_relative: dict,
    logical_key: str,
    ui_type: str,
    action: str,
    path: str,
    source: str,
    expected_value: str = "",
    scroll_direction: str = "down",
    scroll_amount: int = 1,
    drag_target: str = "",
    choices: Optional[list[dict]] = None,
    navigation_target: str = "",
    parent_scroll_area: str = "",
    requires_scroll: bool = False,
    created_at: str = None,
) -> dict:
    sid = compute_stable_id(bbox_relative)

    element = {
        "stable_id": sid,
        "logical_key": logical_key,
        "ui_type": ui_type,
        "action": action,
        "path": path,
        "bbox_relative": bbox_relative,
        "source": source,
        "created_at": created_at or datetime.now().isoformat(),
    }

    click_target = compute_click_target(bbox_relative, ui_type)
    if click_target is not None:
        element["click_target"] = click_target

    if ui_type == "scroll_area":
        element["scroll_config"] = {
            "direction": scroll_direction,
            "amount": scroll_amount
        }

    if ui_type == "drag_handle" and drag_target:
        element["drag_target"] = drag_target

    if ui_type in ("dropdown", "radio", "checkbox"):
        if expected_value:
            element["expected_value"] = expected_value
        if choices:
            element["choices"] = choices

    if ui_type == "button" and navigation_target:
        element["navigation_config"] = {
            "target_screen": navigation_target
        }

    if parent_scroll_area:
        element["parent_scroll_area"] = parent_scroll_area
        element["requires_scroll"] = requires_scroll

    return element


def build_scroll_instruction(
    target_scroll_area: str,
    direction: str = "down",
    amount: int = 1,
    created_at: str = None,
) -> dict:
    """Creates a virtual instruction element for the sequence."""
    created_at = created_at or datetime.now().isoformat()
    return {
        "stable_id": f"instr_{uuid.uuid4().hex[:8]}",
        "ui_type": "instruction",
        "action": "scroll",
        "parent_scroll_area": target_scroll_area,
        "scroll_config": {
            "direction": direction,
            "amount": amount
        },
        "created_at": created_at,
        "source": "human"
    }


def export_mapping(
    elements: list[dict],
    app_name: str,
    screen_name: str,
    resolution: tuple[int, int],
    output_path: str,
) -> None:
    # Sort elements by created_at to ensure sequence in export
    sorted_elements = sorted(elements, key=lambda x: x.get("created_at", ""))

    payload = {
        "meta": {
            "app": app_name,
            "screen": screen_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "resolution": list(resolution),
        },
        "elements": sorted_elements,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    update_corrections(sorted_elements, app_name, screen_name)
