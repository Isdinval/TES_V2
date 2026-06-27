import win32gui
import win32api
import win32con
from typing import Optional, Tuple

class WindowSelector:
    @staticmethod
    def get_window_at_mouse() -> Optional[int]:
        """Returns the handle of the window under the mouse cursor."""
        x, y = win32api.GetCursorPos()
        handle = win32gui.WindowFromPoint((x, y))

        # We want the top-level window, not a child control if possible
        # but for UIA, sometimes we start from the handle found.
        # Actually, pywinauto's connect(handle=...) works well with top-level.

        if not handle:
            return None

        # Get the root owner if it's a child
        root_handle = win32gui.GetAncestor(handle, win32con.GA_ROOT)
        return root_handle if root_handle else handle

    @staticmethod
    def get_window_info(handle: int) -> dict:
        """Returns basic info about a window handle."""
        try:
            title = win32gui.GetWindowText(handle)
            rect = win32gui.GetWindowRect(handle) # (left, top, right, bottom)
            return {
                "handle": handle,
                "title": title,
                "rect": rect
            }
        except Exception:
            return {}
