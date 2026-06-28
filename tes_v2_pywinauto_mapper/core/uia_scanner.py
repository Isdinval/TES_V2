import pywinauto
from pywinauto import Desktop
from PIL import ImageGrab
import win32gui
import win32api
import win32con
from core.element import UIElement
from core.utils import name_to_logical_key
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

            # Post-process: group radio buttons and tab items
            window_rect = win32gui.GetWindowRect(handle)  # (left, top, right, bottom)
            # Find groupboxes from the raw scan (stored in elements if interactive or has name, but we need all)
            # Actually _get_elements now returns groupboxes too.
            groupbox_elements = [el for el in elements if el.control_type in ("Group", "GroupBox")]
            elements = self._group_elements(elements, groupbox_elements, window_rect)

            return elements
        except Exception as e:
            print(f"Scan error: {e}")
            try:
                window = Desktop(backend="uia").window(handle=handle)
                elements = self._get_elements(window, show_all)
                window_rect = win32gui.GetWindowRect(handle)
                groupbox_elements = [el for el in elements if el.control_type in ("Group", "GroupBox")]
                return self._group_elements(elements, groupbox_elements, window_rect)
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

    def _build_uia_path(self, ctrl, window_ctrl) -> str:
        """
        Build a UIA path string by ascending the element's ancestor chain.
        Returns a string like:
        "Dialog[@title='Login'] > GroupBox[@title='Credentials'] > Edit[@auto_id='txtUser']"
        """
        # Meaningless control types to skip in the path (pure structural containers)
        SKIP_TYPES = {"Pane", "Custom", "Unknown"}
        MAX_DEPTH = 6

        segments = []
        current = ctrl
        depth = 0

        while current and depth < MAX_DEPTH:
            try:
                # Stop if we've reached the window root
                if current.element_info == window_ctrl.element_info:
                    break

                ct = current.element_info.control_type or "Unknown"
                auto_id = getattr(current.element_info, "automation_id", "") or ""
                name = getattr(current.element_info, "name", "") or ""
                class_name = getattr(current.element_info, "class_name", "") or ""

                # Skip featureless Pane/Custom containers
                if ct in SKIP_TYPES and not auto_id and not name:
                    current = current.parent()
                    depth += 1
                    continue

                # Build segment attributes
                attrs = ""
                if auto_id and not auto_id.isdigit():
                    escaped = auto_id.replace("'", "\\'")
                    attrs += f"[@auto_id='{escaped}']"
                if name.strip():
                    escaped = name.strip().replace("'", "\\'")
                    attrs += f"[@title='{escaped}']"
                if class_name and class_name not in ("Pane", "Window", "Custom", ""):
                    attrs += f"[@class='{class_name}']"

                segments.append(f"{ct}{attrs}")
                current = current.parent()
                depth += 1

            except Exception:
                break

        segments.reverse()
        return " > ".join(segments) if segments else ""

    def _group_elements(self, elements: List[UIElement], groupbox_elements: List[UIElement], window_rect) -> List[UIElement]:
        """
        Post-process: merge RadioButtons and TabItems that belong to the same logical group
        into single ChoiceGroup UIElement entries. Remove the individual elements from the list.
        Returns a new list with individual radio/tab elements replaced by group entries.
        """
        result = []
        radio_groups = {}   # key: parent_stable_id → list of UIElement
        tab_groups = {}     # key: parent_stable_id → list of UIElement
        ungrouped = []

        for el in elements:
            # Skip groupboxes themselves in the final interactive list unless they were interactive
            if el.control_type in ("Group", "GroupBox") and not el.logical_key:
                continue

            ct = el.control_type
            if ct == "RadioButton":
                parent_key = getattr(el, "_parent_stable_id", "")
                if not parent_key:
                    ungrouped.append(el)
                    continue
                radio_groups.setdefault(parent_key, []).append(el)
            elif ct == "TabItem":
                parent_key = getattr(el, "_parent_stable_id", "")
                if not parent_key:
                    ungrouped.append(el)
                    continue
                tab_groups.setdefault(parent_key, []).append(el)
            else:
                ungrouped.append(el)

        # Process radio groups
        for parent_key, radios in radio_groups.items():
            if len(radios) < 2:
                ungrouped.extend(radios)
                continue

            # Bounding box = union of all member rectangles
            left   = min(r.rectangle[0] for r in radios)
            top    = min(r.rectangle[1] for r in radios)
            right  = max(r.rectangle[0] + r.rectangle[2] for r in radios)
            bottom = max(r.rectangle[1] + r.rectangle[3] for r in radios)
            group_rect = [left, top, right - left, bottom - top]

            # Relative coordinates
            rw, rh = (window_rect[2] - window_rect[0], window_rect[3] - window_rect[1])                      if window_rect else (1, 1)

            choices = []
            for r in radios:
                cx = r.rectangle[0] + r.rectangle[2] / 2
                cy = r.rectangle[1] + r.rectangle[3] / 2
                choices.append({
                    "label": r.name or r.logical_key or f"option_{len(choices)}",
                    "x": round(cx / rw, 6),
                    "y": round(cy / rh, 6),
                    "stable_id": r.automation_id or f"{r.name}_{r.control_type}"
                })

            group_name = getattr(radios[0], "_parent_name", "") or radios[0].name

            # GroupBox visual containment fallback
            if not getattr(radios[0], "_parent_name", ""):
                for candidate in groupbox_elements:
                    gb_left, gb_top, gb_w, gb_h = candidate.rectangle
                    gb_right, gb_bottom = gb_left + gb_w, gb_top + gb_h
                    members_inside = [
                        r for r in radios
                        if gb_left <= r.rectangle[0] and gb_top <= r.rectangle[1]
                        and r.rectangle[0] + r.rectangle[2] <= gb_right
                        and r.rectangle[1] + r.rectangle[3] <= gb_bottom
                    ]
                    if len(members_inside) == len(radios):
                        group_name = candidate.name or group_name
                        break

            group_key = name_to_logical_key(group_name) or f"radio_group_{len(result)}"

            group_el = UIElement(
                name=group_name,
                automation_id="",
                control_type="RadioGroup",
                class_name="",
                framework_id=radios[0].framework_id,
                rectangle=group_rect,
                is_enabled=True,
                is_visible=True,
                ui_type="radio_group",
                action="select_by_label",
                logical_key=group_key,
                choices=choices,
                supported_patterns=[],
                execution_hint="pyautogui_fallback",
                path=radios[0].path,
            )
            result.append(group_el)

        # Process tab groups
        for parent_key, tabs in tab_groups.items():
            if len(tabs) < 2:
                ungrouped.extend(tabs)
                continue

            left   = min(t.rectangle[0] for t in tabs)
            top    = min(t.rectangle[1] for t in tabs)
            right  = max(t.rectangle[0] + t.rectangle[2] for t in tabs)
            bottom = max(t.rectangle[1] + t.rectangle[3] for t in tabs)
            group_rect = [left, top, right - left, bottom - top]

            rw, rh = (window_rect[2] - window_rect[0], window_rect[3] - window_rect[1])                      if window_rect else (1, 1)

            choices = []
            for t in tabs:
                cx = t.rectangle[0] + t.rectangle[2] / 2
                cy = t.rectangle[1] + t.rectangle[3] / 2
                choices.append({
                    "label": t.name or f"tab_{len(choices)}",
                    "x": round(cx / rw, 6),
                    "y": round(cy / rh, 6),
                    "stable_id": t.automation_id or f"{t.name}_{t.control_type}"
                })

            group_name = getattr(tabs[0], "_parent_name", "") or "tabs"
            group_key = name_to_logical_key(group_name) or f"tab_bar_{len(result)}"

            group_el = UIElement(
                name=group_name,
                automation_id="",
                control_type="TabGroup",
                class_name="",
                framework_id=tabs[0].framework_id,
                rectangle=group_rect,
                is_enabled=True,
                is_visible=True,
                ui_type="tab_bar",
                action="click_by_label",
                logical_key=group_key,
                choices=choices,
                supported_patterns=[],
                execution_hint="pyautogui_fallback",
                path=tabs[0].path,
            )
            result.append(group_el)

        result.extend(ungrouped)
        return result

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
                        is_group = control_type in ("Group", "GroupBox")
                        if not (is_interactive or has_name or is_group): continue

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

                    # Compute logical_key cascade
                    suggested_key = ""
                    if automation_id and not automation_id.isdigit():
                        suggested_key = automation_id
                    elif name.strip():
                        suggested_key = name_to_logical_key(name)
                    else:
                        rect_hash = abs(hash(f"{rect.left},{rect.top}")) % 10000
                        suggested_key = f"{control_type.lower()}_{rect_hash}"

                    # Compute path
                    path = self._build_uia_path(ctrl, window)

                    ui_element = UIElement(
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
                        ui_type=inferred_ui_type or control_type,
                        action=inferred_action,
                        logical_key=suggested_key,
                        path=path,
                        execution_hint=execution_hint
                    )

                    # Parent info for grouping
                    if control_type in ("RadioButton", "TabItem"):
                        try:
                            parent_ctrl = ctrl.parent()
                            if parent_ctrl:
                                p_auto_id = getattr(parent_ctrl.element_info, "automation_id", "") or ""
                                p_name = getattr(parent_ctrl.element_info, "name", "") or ""
                                p_ct = getattr(parent_ctrl.element_info, "control_type", "") or ""
                                p_rect = getattr(parent_ctrl.element_info, "rectangle", None)
                                if p_auto_id and not p_auto_id.isdigit():
                                    parent_stable = p_auto_id
                                elif p_name:
                                    parent_stable = f"{p_name}_{p_ct}"
                                elif p_rect:
                                    parent_stable = f"{p_ct}_{p_rect.left}_{p_rect.top}"
                                else:
                                    parent_stable = f"{p_ct}_unknown"
                                ui_element._parent_stable_id = parent_stable
                                ui_element._parent_name = p_name
                        except Exception:
                            ui_element._parent_stable_id = ""
                            ui_element._parent_name = ""

                    ui_elements.append(ui_element)
                except Exception: continue
        except Exception as e:
            print(f"Error in _get_elements: {e}")
        return ui_elements
