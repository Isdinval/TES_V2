import hashlib


def compute_stable_id(bbox_relative: dict) -> str:
    """
    Deterministic ID based on quantized bbox.
    Stable across runs as long as the UI layout doesn't change.
    Quantized to 2 decimal places (~1% of screen) to absorb sub-pixel
    jitter while still distinguishing adjacent elements.
    """
    x = round(bbox_relative["x"], 2)
    y = round(bbox_relative["y"], 2)
    w = round(bbox_relative["w"], 2)
    h = round(bbox_relative["h"], 2)
    seed = f"{x:.2f}_{y:.2f}_{w:.2f}_{h:.2f}"
    return hashlib.md5(seed.encode()).hexdigest()[:12]