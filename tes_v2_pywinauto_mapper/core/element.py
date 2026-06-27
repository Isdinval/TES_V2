from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class UIElement:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "automation_id": self.automation_id,
            "control_type": self.control_type,
            "class_name": self.class_name,
            "framework_id": self.framework_id,
            "rectangle": self.rectangle,
            "is_enabled": self.is_enabled,
            "is_visible": self.is_visible,
            "value": self.value,
            "patterns": self.patterns
        }
