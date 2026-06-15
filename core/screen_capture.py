import mss
import mss.tools
from PIL import Image
import io
import sys

def list_monitors() -> list[dict]:
    """Returns list of monitors: [{id, x, y, width, height, name}]"""
    print("DEBUG: Entering list_monitors", flush=True)
    try:
        with mss.mss() as sct:
            monitors = []
            print(f"DEBUG: Found {len(sct.monitors)} raw monitors", flush=True)
            for i, m in enumerate(sct.monitors[1:], start=1):  # skip monitor[0] (all)
                monitors.append({
                    "id": i,
                    "x": m["left"],
                    "y": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                    "name": f"Monitor {i} ({m['width']}x{m['height']})",
                })
            print(f"DEBUG: list_monitors returning {len(monitors)} monitors", flush=True)
            return monitors
    except Exception as e:
        print(f"DEBUG ERROR in list_monitors: {e}", flush=True)
        raise

def capture_monitor(monitor_id: int) -> tuple[Image.Image, tuple[int, int]]:
    """
    Capture a specific monitor.
    Returns (PIL Image, (width, height)).
    """
    print(f"DEBUG: Entering capture_monitor with id {monitor_id}", flush=True)
    try:
        with mss.mss() as sct:
            print(f"DEBUG: mss context opened. Available monitors: {len(sct.monitors)}", flush=True)
            if monitor_id >= len(sct.monitors):
                print(f"DEBUG ERROR: monitor_id {monitor_id} out of range", flush=True)
                raise IndexError(f"Monitor ID {monitor_id} out of range")

            monitor = sct.monitors[monitor_id]
            print(f"DEBUG: Grabbing monitor {monitor}", flush=True)
            screenshot = sct.grab(monitor)
            print(f"DEBUG: Screenshot grabbed. Size: {screenshot.size}", flush=True)

            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            print("DEBUG: PIL Image created from bytes", flush=True)

            return img, (monitor["width"], monitor["height"])
    except Exception as e:
        print(f"DEBUG ERROR in capture_monitor: {e}", flush=True)
        raise
