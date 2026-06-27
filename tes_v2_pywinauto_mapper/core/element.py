from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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

    # Reference resolution for relative conversion
    ref_resolution: Optional[List[int]] = None

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
            "stable_id": self.automation_id if self.automation_id else f"{self.name}_{self.control_type}"
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
            value_pattern=data.get("value_pattern", False)
        )
