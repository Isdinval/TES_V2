from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import hashlib

@dataclass
class UIElement:
    # UIA / Technical properties
    name: str
    automation_id: str
    control_type: str
    class_name: str
    framework_id: str
    rectangle: List[int]  # [x, y, width, height]
    is_enabled: bool
    is_visible: bool
    value: Optional[str] = None
    patterns: List[str] = field(default_factory=list)
    handle: Any = None # Native handle if available

    # Business / Mapping properties
    logical_key: str = ""
    ui_type: str = ""
    action: str = ""
    notes: str = ""
    path: str = ""
    expected_value: str = ""
    value_pattern: bool = False

    # New fields
    choices: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    # Each item: {"label": str, "x": float (abs), "y": float (abs)}

    toggle_state: Optional[str] = None
    # For CheckBox: "on", "off", "indeterminate"
    # For RadioButton: "selected" or "unselected"

    pywinauto_selector: Optional[Dict[str, Any]] = None
    # Built during scan from: automation_id, control_type, title (name)

    # Reference resolution for relative conversion
    ref_resolution: Optional[List[int]] = None

    def generate_stable_id(self) -> str:
        """
        Priority 1: automation_id if non-empty and not a generic integer string
        Priority 2: f"{self.class_name}_{self.name}" if both are meaningful
        Priority 3: f"{self.control_type}_{self.class_name}_{rect_hash}"
        Priority 4: hash of (name + control_type + rectangle)
        """
        rect_str = f"{self.rectangle[0]},{self.rectangle[1]},{self.rectangle[2]},{self.rectangle[3]}"
        rect_hash = hashlib.md5(rect_str.encode()).hexdigest()[:8]

        # Priority 1
        if self.automation_id and not self.automation_id.isdigit():
            return self.automation_id

        # Priority 2
        if self.class_name and self.name.strip():
            return f"{self.class_name}_{self.name.strip()}"

        # Priority 3
        if self.control_type and self.class_name:
            return f"{self.control_type}_{self.class_name}_{rect_hash}"

        # Priority 4
        combined = f"{self.name}{self.control_type}{rect_str}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "logical_key": self.logical_key,
            "ui_type": self.ui_type,
            "action": self.action,
            "name": self.name,
            "automation_id": self.automation_id,
            "control_type": self.control_type,
            "class_name": self.class_name,
            "framework_id": self.framework_id,
            "rectangle": self.rectangle,
            "is_enabled": self.is_enabled,
            "is_visible": self.is_visible,
            "value": self.value,
            "patterns": self.patterns,
            "notes": self.notes,
            "path": self.path,
            "expected_value": self.expected_value,
            "value_pattern": self.value_pattern,
            "stable_id": self.generate_stable_id()
        }

        # Convert rectangle [x, y, w, h] to bbox_relative [x, y, w, h] as floats (0..1)
        if self.ref_resolution and len(self.ref_resolution) == 2:
            rw, rh = self.ref_resolution
            rx, ry, rw_el, rh_el = self.rectangle
            data["bbox_relative"] = {
                "x": round(rx / rw, 6),
                "y": round(ry / rh, 6),
                "w": round(rw_el / rw, 6),
                "h": round(rh_el / rh, 6)
            }
            # Also add source for local agent compatibility
            data["source"] = "human"

            if self.choices:
                data["choices"] = [
                    {
                        "label": c["label"],
                        "x": round(c["x"] / rw, 6),
                        "y": round(c["y"] / rh, 6)
                    }
                    for c in self.choices
                ]

        if self.toggle_state:
            data["toggle_state"] = self.toggle_state

        if self.pywinauto_selector:
            data["pywinauto_selector"] = self.pywinauto_selector

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIElement':
        return cls(
            logical_key=data.get("logical_key", ""),
            ui_type=data.get("ui_type", ""),
            action=data.get("action", ""),
            name=data.get("name", ""),
            automation_id=data.get("automation_id", ""),
            control_type=data.get("control_type", ""),
            class_name=data.get("class_name", ""),
            framework_id=data.get("framework_id", ""),
            rectangle=data.get("rectangle", [0, 0, 0, 0]),
            is_enabled=data.get("is_enabled", True),
            is_visible=data.get("is_visible", True),
            value=data.get("value"),
            patterns=data.get("patterns", []),
            notes=data.get("notes", ""),
            path=data.get("path", ""),
            expected_value=data.get("expected_value", ""),
            value_pattern=data.get("value_pattern", False),
            choices=data.get("choices", []),
            toggle_state=data.get("toggle_state"),
            pywinauto_selector=data.get("pywinauto_selector")
        )
