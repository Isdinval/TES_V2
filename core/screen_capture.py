import mss
import mss.tools
from PIL import Image
import io


def list_monitors() -> list[dict]:
    """Returns list of monitors: [{id, x, y, width, height, name}]"""
    with mss.mss() as sct:
        monitors = []
        for i, m in enumerate(sct.monitors[1:], start=1):  # skip monitor[0] (all)
            monitors.append({
                "id": i,
                "x": m["left"],
                "y": m["top"],
                "width": m["width"],
                "height": m["height"],
                "name": f"Monitor {i} ({m['width']}x{m['height']})",
            })
        return monitors


def capture_monitor(monitor_id: int) -> tuple[Image.Image, tuple[int, int]]:
    """
    Capture a specific monitor.
    Returns (PIL Image, (width, height)).
    """
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_id]
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return img, (monitor["width"], monitor["height"])
