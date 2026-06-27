import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.element import UIElement

class MappingStore:
    def __init__(self, base_dir: str = "mappings"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _get_file_path(self, app_name: str, screen_name: str) -> str:
        # Sanitize names
        safe_app = "".join([c for c in app_name if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
        safe_screen = "".join([c for c in screen_name if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
        return os.path.join(self.base_dir, f"{safe_app}_{safe_screen}.json")

    def save_mapping(self, app_name: str, screen_name: str, backend: str, window_title: str, elements: List[UIElement], resolution: tuple[int, int]):
        # Structure compatible with tes_v2_local_agent
        data = {
            "meta": {
                "app": app_name,
                "screen": screen_name,
                "backend": backend,
                "window_title": window_title,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "resolution": list(resolution)
            },
            "elements": []
        }

        for el in elements:
            if el.logical_key:
                el.ref_resolution = list(resolution)
                data["elements"].append(el.to_dict())

        file_path = self._get_file_path(app_name, screen_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return file_path

    def load_mapping(self, app_name: str, screen_name: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_file_path(app_name, screen_name)
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading mapping: {e}")
            return None

    def merge_with_scanned_elements(self, scanned_elements: List[UIElement], saved_mapping: Dict[str, Any]):
        """
        Merges scanned elements with saved mapping data based on identity.
        """
        if not saved_mapping:
            return scanned_elements

        saved_elements = saved_mapping.get("elements", [])
        # Build lookup table for saved elements
        # Priority 1: AutomationId
        # Priority 2: Name + ControlType
        lookup_auto_id = {el["automation_id"]: el for el in saved_elements if el.get("automation_id")}
        lookup_name_type = {(el["name"], el["control_type"]): el for el in saved_elements if el.get("name")}

        for el in scanned_elements:
            match = None
            if el.automation_id and el.automation_id in lookup_auto_id:
                match = lookup_auto_id[el.automation_id]
            elif (el.name, el.control_type) in lookup_name_type:
                match = lookup_name_type[(el.name, el.control_type)]

            if match:
                el.logical_key = match.get("logical_key", "")
                el.ui_type = match.get("ui_type", "")
                el.action = match.get("action", "")
                el.notes = match.get("notes", "")
                el.path = match.get("path", "")
                el.expected_value = match.get("expected_value", "")
                el.value_pattern = match.get("value_pattern", False)

        return scanned_elements
