"""
ollama_suggest.py — Suggère logical_key, ui_type et action
en envoyant le crop de la bbox à un modèle Ollama vision (qwen3-vl).
"""

from __future__ import annotations

import base64
import io
import json
import re
import urllib.request
import urllib.error
from typing import Optional

from PIL import Image

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3-vl:8b"

UI_TYPES = [
    "text_input", "button", "checkbox", "radio", "dropdown",
    "label", "icon", "tab", "menu_item", "toggle",
    "date_picker", "table_cell", "other",
]
ACTIONS = [
    "click", "click_then_type", "double_click", "right_click",
    "check", "uncheck", "select", "hover", "scroll", "drag", "none",
]

PROMPT = """\
Tu analyses un élément d'interface utilisateur (extrait d'une capture d'écran).
Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans balises, sans commentaires.

Champs attendus :
- "logical_key" : identifiant snake_case en français décrivant la fonction de cet élément (ex: "bouton_valider_patient", "champ_date_naissance"). Max 5 mots.
- "ui_type" : l'un de : text_input, button, checkbox, radio, dropdown, label, icon, tab, menu_item, toggle, date_picker, table_cell, other
- "action" : l'action la plus probable parmi : click, click_then_type, double_click, right_click, check, uncheck, select, hover, scroll, drag, none

Exemple de réponse valide :
{"logical_key": "bouton_enregistrer", "ui_type": "button", "action": "click"}
"""


def _crop_to_base64(image: Image.Image, bbox: dict) -> str:
    """Crop image to bbox (relative coords) and encode as base64 PNG."""
    w, h = image.size
    x1 = int(bbox["x"] * w)
    y1 = int(bbox["y"] * h)
    x2 = int((bbox["x"] + bbox["w"]) * w)
    y2 = int((bbox["y"] + bbox["h"]) * h)
    # Add small padding
    pad = 4
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)

    crop = image.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def suggest(
    image: Image.Image,
    bbox: dict,
    model: str = DEFAULT_MODEL,
) -> Optional[dict]:
    """
    Send bbox crop to Ollama and return {"logical_key", "ui_type", "action"}.
    Returns None on any error.
    """
    img_b64 = _crop_to_base64(image, bbox)

    payload = json.dumps({
        "model": model,
        "prompt": PROMPT,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        raw = data.get("response", "")
    except urllib.error.URLError as e:
        print(f"[Ollama] Connection error: {e}")
        return None
    except Exception as e:
        print(f"[Ollama] Unexpected error: {e}")
        return None

    return _parse_response(raw)


def _parse_response(raw: str) -> Optional[dict]:
    """Extract JSON from model response, tolerating <think> blocks."""
    # Strip <think>...</think> (qwen3 reasoning tokens)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Try direct parse
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Find first {...} block
        m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if not m:
            print(f"[Ollama] No JSON found in: {raw[:200]}")
            return None
        try:
            parsed = json.loads(m.group())
        except json.JSONDecodeError:
            print(f"[Ollama] JSON parse failed: {raw[:200]}")
            return None

    # Validate and sanitize fields
    key = str(parsed.get("logical_key", "")).strip().lower().replace(" ", "_")
    ui_type = parsed.get("ui_type", "other")
    action = parsed.get("action", "click")

    if ui_type not in UI_TYPES:
        ui_type = "other"
    if action not in ACTIONS:
        action = "click"
    if not key:
        return None

    return {"logical_key": key, "ui_type": ui_type, "action": action}
