import pywinauto
from pywinauto import Desktop
from PIL import ImageGrab
import win32gui
import win32api
import win32con
from core.element import UIElement
from typing import List, Tuple, Optional

class UIAScanner:
    INTERACTIVE_TYPES = {
        "Button", "Edit", "ComboBox", "CheckBox", "RadioButton",
        "List", "DataGrid", "TabItem", "MenuItem", "Hyperlink", "TreeItem",
        "ListItem", "HeaderItem"
    }

    def __init__(self):
        self.backend = "uia"

    def capture_window(self, handle: int) -> Tuple[Optional[ImageGrab.Image.Image], Optional[Tuple[int, int, int, int]]]:
        """Captures a screenshot of the specified window."""
        try:
            if not win32gui.IsWindow(handle):
                return None, None

            # Ensure window is not minimized
            if win32gui.IsIconic(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)

            rect = win32gui.GetWindowRect(handle) # (L, T, R, B)
            # ImageGrab.grab takes (L, T, R, B)
            screenshot = ImageGrab.grab(bbox=rect, all_screens=True)
            return screenshot, rect
        except Exception as e:
            print(f"Error capturing window: {e}")
            return None, None

    def scan(self, handle: int, show_all: bool = False) -> List[UIElement]:
        """Scans elements of the window using pywinauto."""
        elements = []
        try:
            # We connect to the process owning the handle
            app = pywinauto.Application(backend="uia").connect(handle=handle, timeout=2)
            window = app.window(handle=handle)

            self.backend = "uia"
            elements = self._get_elements(window, show_all)

            # Fallback if too few elements
            if len(elements) < 3:
                print("UIA returned few elements, trying win32 fallback...")
                try:
                    app_win32 = pywinauto.Application(backend="win32").connect(handle=handle, timeout=2)
                    window_win32 = app_win32.window(handle=handle)
                    elements_win32 = self._get_elements(window_win32, show_all)
                    if len(elements_win32) > len(elements):
                        elements = elements_win32
                        self.backend = "win32"
                except Exception as e:
                    print(f"Win32 fallback failed: {e}")

            return elements
        except Exception as e:
            print(f"Scan error: {e}")
            # Try to just use Desktop if application connect fails
            try:
                print("Trying to scan via Desktop...")
                window = Desktop(backend="uia").window(handle=handle)
                return self._get_elements(window, show_all)
            except:
                return []

    def _get_elements(self, window, show_all: bool) -> List[UIElement]:
        ui_elements = []
        try:
            # descendants() is thorough
            all_ctrls = window.descendants()

            for ctrl in all_ctrls:
                try:
                    props = ctrl.get_properties()

                    control_type = props.get("control_type", "Unknown")
                    name = props.get("texts", [""])[0] if props.get("texts") else ""
                    automation_id = props.get("automation_id", "")
                    class_name = props.get("class_name", "")
                    framework_id = props.get("framework_id", "")

                    rect = props.get("rectangle")
                    if not rect:
                        continue

                    if not show_all:
                        # Filter: interactive type OR has a name (labels)
                        is_interactive = control_type in self.INTERACTIVE_TYPES
                        has_name = bool(name.strip())
                        if not (is_interactive or has_name):
                            continue

                    # Extract Patterns (UIA specific)
                    patterns = []
                    if self.backend == "uia":
                        try:
                            # Accessing UIA element directly to see patterns
                            elem = ctrl.element_info.element
                            # This is a bit advanced, but we can check for common patterns
                            # In pywinauto, we can check wrapper methods
                            if hasattr(ctrl, 'get_value'): patterns.append("Value")
                            if hasattr(ctrl, 'invoke'): patterns.append("Invoke")
                            if hasattr(ctrl, 'select'): patterns.append("SelectionItem")
                            if hasattr(ctrl, 'toggle'): patterns.append("Toggle")
                            if hasattr(ctrl, 'scroll'): patterns.append("Scroll")
                        except:
                            pass

                    value = ""
                    try:
                        if hasattr(ctrl, 'get_value'):
                            value = str(ctrl.get_value())
                        elif hasattr(ctrl, 'texts'):
                            txts = ctrl.texts()
                            if txts: value = txts[0]
                    except:
                        pass

                    ui_elements.append(UIElement(
                        name=name,
                        automation_id=automation_id,
                        control_type=control_type,
                        class_name=class_name,
                        framework_id=framework_id,
                        rectangle=[rect.left, rect.top, rect.width(), rect.height()],
                        is_enabled=props.get("is_enabled", True),
                        is_visible=props.get("is_visible", True),
                        value=value,
                        patterns=patterns
                    ))
                except Exception:
                    continue
        except Exception as e:
            print(f"Error in _get_elements: {e}")

        return ui_elements
