from loguru import logger
from typing import Optional
from tes_v2_local_agent.models.mapping import ScreenMapping, FieldMapping

class Navigator:
    def __init__(self, action_executor):
        self.executor = action_executor

    def navigate_to_screen(self, current_mapping: ScreenMapping, target_screen_name: str) -> bool:
        """
        Attempts to find a navigation link to target_screen_name in the current screen elements.
        """
        logger.info(f"Attempting to navigate to {target_screen_name}")

        nav_element = next(
            (el for el in current_mapping.elements
             if el.navigation_config and el.navigation_config.target_screen == target_screen_name),
            None
        )

        if nav_element:
            logger.info(f"Found navigation element: {nav_element.logical_key}")
            self.executor.execute_action(nav_element, None)
            return True

        logger.warning(f"No direct navigation found from current screen to {target_screen_name}")
        return False
