import hashlib


def compute_stable_id(bbox_relative: dict) -> str:
    """
    Deterministic ID based on quantized bbox.
    Stable across runs as long as the UI layout doesn't change.
    Quantized to 2 decimal places to absorb sub-pixel jitter.
    """
    # Quantize to 1 decimal place to absorb YOLO sub-pixel jitter (~10% of screen)
    # Fine enough to distinguish close elements, coarse enough to be stable
    x = round(bbox_relative["x"], 1)
    y = round(bbox_relative["y"], 1)
    w = round(bbox_relative["w"], 1)
    h = round(bbox_relative["h"], 1)
    seed = f"{x:.1f}_{y:.1f}_{w:.1f}_{h:.1f}"
    return hashlib.md5(seed.encode()).hexdigest()[:10]
