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
    value_pattern: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
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
            "value_pattern": self.value_pattern
        }

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
            value_pattern=data.get("value_pattern", False)
        )
