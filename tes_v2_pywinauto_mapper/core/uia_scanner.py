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

    def _detect_true_patterns(self, ctrl) -> List[str]:
        """
        Probe which UIA Control Patterns the element truly supports by attempting
        to access the COM interface for each pattern.
        Uses pywinauto's iface_* properties which internally call get_elem_interface()
        and raise NoPatternInterfaceError if the COM interface is absent.
        This avoids false positives from hasattr() which finds inherited base class methods.
        """
        from pywinauto.uia_defines import NoPatternInterfaceError

        detected = []
        probes = [
            ("Invoke",         lambda c: c.iface_invoke),
            ("Toggle",         lambda c: c.iface_toggle),
            ("SelectionItem",  lambda c: c.iface_selection_item),
            ("Selection",      lambda c: c.iface_selection),
            ("Value",          lambda c: c.iface_value),
            ("RangeValue",     lambda c: c.iface_range_value),
            ("ExpandCollapse", lambda c: c.iface_expand_collapse),
            ("Text",           lambda c: c.iface_text),
            ("Grid",           lambda c: c.iface_grid),
            ("Scroll",         lambda c: c.iface_scroll),
        ]

        for pattern_name, probe_fn in probes:
            try:
                iface = probe_fn(ctrl)
                if iface is not None:
                    detected.append(pattern_name)
            except (NoPatternInterfaceError, Exception):
                pass

        return detected

    def _infer_action_from_patterns(self, patterns: List[str], control_type: str) -> tuple:
        """
        Infer the best default (ui_type, action) from confirmed UIA patterns.
        Returns ("", "") if no inference is possible (caller falls back to control_type mapping).
        """
        ctype = control_type.lower()

        if "Toggle" in patterns:
            return ("checkbox", "check")

        if "SelectionItem" in patterns and "Toggle" not in patterns:
            if ctype in ("radiobutton",):
                return ("radio", "select")
            if ctype in ("tabitem",):
                return ("tab", "click")
            return ("radio", "select")  # Default to radio for SelectionItem

        if "RangeValue" in patterns:
            return ("slider", "set_value")

        if "Grid" in patterns:
            return ("table_cell", "click")

        if "ExpandCollapse" in patterns and "Selection" in patterns:
            return ("dropdown", "select")

        if "ExpandCollapse" in patterns:
            return ("tree_item", "expand")

        if "Value" in patterns and "Invoke" not in patterns:
            return ("text_input", "click_then_type")

        if "Invoke" in patterns:
            if ctype in ("menuitem",):
                return ("menu_item", "click")
            return ("button", "click")

        if "Scroll" in patterns:
            return ("scroll_area", "scroll")

        return ("", "")  # No inference possible

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

                    supported_patterns = []
                    value_pattern = False
                    execution_hint = "pyautogui_fallback"

                    if self.backend == "uia":
                        supported_patterns = self._detect_true_patterns(ctrl)
                        value_pattern = "Value" in supported_patterns
                        if supported_patterns:
                            execution_hint = "uia_native"

                    value = ""
                    try:
                        if hasattr(ctrl, 'get_value'): value = str(ctrl.get_value())
                        elif hasattr(ctrl, 'texts'):
                            txts = ctrl.texts()
                            if txts: value = txts[0]
                    except: pass

                    # Infer ui_type and action from confirmed patterns
                    inferred_ui_type, inferred_action = self._infer_action_from_patterns(
                        supported_patterns, control_type
                    )

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
                        supported_patterns=supported_patterns,
                        value_pattern=value_pattern,
                        ui_type=inferred_ui_type or control_type,   # use inference or fall back to raw control_type
                        action=inferred_action,
                        execution_hint=execution_hint
                    ))
                except Exception: continue
        except Exception as e:
            print(f"Error in _get_elements: {e}")
        return ui_elements
