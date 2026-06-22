from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class BBoxRelative(BaseModel):
    x: float
    y: float
    w: float
    h: float

class ClickTarget(BaseModel):
    x: float
    y: float

class ScrollConfig(BaseModel):
    direction: str = "down"
    amount: int = 1
    strategy: Optional[str] = "wheel"
    max_attempts: Optional[int] = 8

class NavigationConfig(BaseModel):
    target_screen: str

class Choice(BaseModel):
    label: str
    x: Optional[float] = None
    y: Optional[float] = None
    scroll_steps: int = 0

class FieldMapping(BaseModel):
    stable_id: str
    logical_key: str
    ui_type: str
    action: str
    path: Optional[str] = None
    bbox_relative: BBoxRelative
    source: str = "human"
    click_target: Optional[ClickTarget] = None
    scroll_config: Optional[ScrollConfig] = None
    navigation_config: Optional[NavigationConfig] = None
    choices: Optional[List[Choice]] = None
    expected_value: Optional[str] = None
    is_scrollable: Optional[bool] = False
    scroll_container: Optional[Dict[str, Any]] = None
    scrollbar_target: Optional[Dict[str, Any]] = None
    drag_target: Optional[str] = None

class ScreenMeta(BaseModel):
    app: str
    screen: str
    created_at: str
    resolution: List[int]

class ScreenMapping(BaseModel):
    meta: ScreenMeta
    elements: List[FieldMapping]

class SoftwareMapping(BaseModel):
    app_name: str
    screens: Dict[str, ScreenMapping]

class AutomationScenario(BaseModel):
    name: str
    steps: List[str] # List of screen names
