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
        "ListItem", "HeaderItem", "ListBox", "Slider", "Spinner"
    }

    def __init__(self):
        self.backend = "uia"

    def capture_window(self, handle: int) -> Tuple[Optional[ImageGrab.Image.Image], Optional[Tuple[int, int, int, int]]]:
        try:
            if not win32gui.IsWindow(handle):
                return None, None
            if win32gui.IsIconic(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            rect = win32gui.GetWindowRect(handle)
            screenshot = ImageGrab.grab(bbox=rect, all_screens=True)
            return screenshot, rect
        except Exception as e:
            print(f"Error capturing window: {e}")
            return None, None

    def scan(self, handle: int, show_all: bool = False) -> List[UIElement]:
        elements = []
        try:
            app = pywinauto.Application(backend="uia").connect(handle=handle, timeout=2)
            window = app.window(handle=handle)
            self.backend = "uia"
            elements = self._get_elements(window, show_all)
            if len(elements) < 3:
                print("UIA returned few elements, trying win32 fallback...")
                try:
                    app_win32 = pywinauto.Application(backend="win32").connect(handle=handle, timeout=2)
                    window_win32 = app_win32.window(handle=handle)
                    elements_win32 = self._get_elements(window_win32, show_all)
                    if len(elements_win32) > len(elements):
                        elements = elements_win32
                        self.backend = "win32"
                except: pass
            return elements
        except Exception as e:
            print(f"Scan error: {e}")
            try:
                window = Desktop(backend="uia").window(handle=handle)
                return self._get_elements(window, show_all)
            except: return []

    def _extract_choices(self, ctrl, window_rect: Optional[tuple] = None) -> List[dict]:
        """
        For ComboBox, List, RadioButton (and RadioButton siblings): extract child items.
        Returns list of {"label": str, "x": float_absolute, "y": float_absolute}
        where x, y are the CENTER of each child item's rectangle (absolute screen coords).
        """
        choices = []
        try:
            target_ctrls = []
            control_type = ctrl.element_info.control_type

            if control_type in ("ComboBox", "List", "ListBox"):
                target_ctrls = [child for child in ctrl.children() if child.element_info.control_type == "ListItem"]
            elif control_type == "RadioButton":
                parent = ctrl.parent()
                if parent:
                    target_ctrls = [child for child in parent.children() if child.element_info.control_type == "RadioButton"]

            for item in target_ctrls:
                try:
                    i_rect = item.rectangle()
                    center_x = i_rect.left + i_rect.width() / 2
                    center_y = i_rect.top + i_rect.height() / 2
                    label = item.window_text() or ""
                    choices.append({
                        "label": label,
                        "x": float(center_x),
                        "y": float(center_y)
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return choices

    def _get_elements(self, window, show_all: bool) -> List[UIElement]:
        ui_elements = []
        try:
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
                    if not rect: continue

                    if not show_all:
                        is_interactive = control_type in self.INTERACTIVE_TYPES
                        has_name = bool(name.strip())
                        if not (is_interactive or has_name): continue

                    patterns = []
                    value_pattern = False
                    toggle_state = None
                    if self.backend == "uia":
                        if hasattr(ctrl, 'get_value'):
                            patterns.append("Value")
                            value_pattern = True
                        if hasattr(ctrl, 'invoke'): patterns.append("Invoke")
                        if hasattr(ctrl, 'select'): patterns.append("SelectionItem")
                        if hasattr(ctrl, 'toggle'): patterns.append("Toggle")
                        if hasattr(ctrl, 'scroll'): patterns.append("Scroll")

                        # P1-B: Read toggle_state
                        try:
                            if control_type == "CheckBox":
                                # TogglePattern: toggle_state() returns 0 (off), 1 (on), 2 (indeterminate)
                                ts = ctrl.get_toggle_state()
                                toggle_state = {0: "off", 1: "on", 2: "indeterminate"}.get(ts, None)
                            elif control_type == "RadioButton":
                                # SelectionItemPattern
                                toggle_state = "selected" if ctrl.is_selected() else "unselected"
                        except Exception:
                            pass

                    value = ""
                    try:
                        if hasattr(ctrl, 'get_value'): value = str(ctrl.get_value())
                        elif hasattr(ctrl, 'texts'):
                            txts = ctrl.texts()
                            if txts: value = txts[0]
                    except: pass

                    # P1-A: Populate pywinauto_selector
                    selector = {}
                    if automation_id and not automation_id.isdigit():
                        selector["automation_id"] = automation_id
                    if control_type and control_type != "Unknown":
                        selector["control_type"] = control_type
                    if name.strip():
                        selector["title"] = name.strip()
                    if class_name.strip():
                        selector["class_name"] = class_name.strip()
                    pywinauto_selector = selector if selector else None

                    # P0-B: Extract choices
                    choices = []
                    if self.backend == "uia" and control_type in ("ComboBox", "List", "RadioButton", "ListBox"):
                        choices = self._extract_choices(ctrl)

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
                        patterns=patterns,
                        value_pattern=value_pattern,
                        ui_type=control_type, # Default ui_type to control_type
                        toggle_state=toggle_state,
                        pywinauto_selector=pywinauto_selector,
                        choices=choices
                    ))
                except Exception: continue
        except Exception as e:
            print(f"Error in _get_elements: {e}")
        return ui_elements
