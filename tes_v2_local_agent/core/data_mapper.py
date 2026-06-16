from typing import Dict, Any, List, Optional
from loguru import logger
from tes_v2_local_agent.models.mapping import ScreenMapping, FieldMapping

class DataMapper:
    """
    Handles mapping between raw input data and screen fields using logical_key.
    Supports nested keys (e.g. "client.address.city").
    """
    def get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        if not path:
            return None
        parts = path.split('.')
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def map_record_to_screen(self, record: Dict[str, Any], screen_mapping: ScreenMapping) -> List[tuple[FieldMapping, Any]]:
        logger.debug(f"Mapping record to screen: {screen_mapping.meta.screen}")
        mapped_actions = []

        VAL_LESS_TYPES = ("button", "icon", "tab", "menu_item", "toggle", "scroll_area", "drag_handle", "label")

        for field in screen_mapping.elements:
            # Navigation elements are special - they are NOT part of the data filling sequence
            # but are handled by the Navigator to move between screens.
            if field.navigation_config:
                continue

            value = self.get_nested_value(record, field.logical_key)

            if value is None:
                if field.ui_type in VAL_LESS_TYPES:
                    mapped_actions.append((field, None))
                    continue

                if '.' not in field.logical_key and field.logical_key in record:
                    mapped_actions.append((field, value))
                else:
                    logger.warning(f"Key '{field.logical_key}' not found in record for screen '{screen_mapping.meta.screen}'")
                    continue
            else:
                mapped_actions.append((field, value))

        # Sort by Y then X
        mapped_actions.sort(key=lambda x: (x[0].bbox_relative.y, x[0].bbox_relative.x))

        return mapped_actions
