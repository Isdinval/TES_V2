import pyautogui
import time
import random
import os
from loguru import logger
from typing import Any, Optional, List
from tes_v2_local_agent.models.mapping import FieldMapping, ClickTarget, Choice
from tes_v2_local_agent.utils.retry import retry

class ActionExecutor:
    def __init__(self, resolution: Optional[tuple[int, int]] = None, dry_run: bool = False):
        self.curr_w, self.curr_h = pyautogui.size()
        self.mapping_res = resolution
        self.elements: List[FieldMapping] = []
        self.dry_run = dry_run
        if not dry_run:
            pyautogui.PAUSE = 0.2
            pyautogui.FAILSAFE = True
        logger.info(f"ActionExecutor initialized (Current Res: {self.curr_w}x{self.curr_h}, Mapping Res: {resolution}, Dry Run: {dry_run})")

    def set_screen_elements(self, elements: List[FieldMapping]):
        self.elements = elements
        logger.debug(f"ActionExecutor: screen elements set ({len(elements)} elements)")

    def _human_delay(self, min_s=0.1, max_s=0.3):
        if not self.dry_run:
            time.sleep(random.uniform(min_s, max_s))

    def _get_abs_coords(self, rel_x: float, rel_y: float) -> tuple[int, int]:
        return int(round(rel_x * self.curr_w)), int(round(rel_y * self.curr_h))

    def execute_action(self, field: FieldMapping, value: Any):
        # Valueless types or elements with navigation should ALWAYS be processed
        VAL_LESS_TYPES = ("button", "icon", "tab", "menu_item", "toggle", "scroll_area", "drag_handle", "label")

        is_nav = field.navigation_config is not None
        has_value = value is not None and value != ""

        if not has_value and not is_nav and field.ui_type not in VAL_LESS_TYPES:
            logger.debug(f"Skipping field {field.logical_key} (Type: {field.ui_type}) - no value and not navigation/valueless")
            return

        msg = f"Action '{field.action}' on field '{field.logical_key}' (Type: {field.ui_type}) with value '{value}'"
        if is_nav:
            msg += f" [NAVIGATION -> {field.navigation_config.target_screen}]"

        if self.dry_run:
            logger.info(f"[DRY RUN] {msg}")
            return

        logger.info(f"Executing: {msg}")
        try:
            self._execute_with_retry(field, value)
        except Exception as e:
            logger.error(f"Action failed after retries: {e}")
            raise

    @retry(Exception, tries=3, delay=1, backoff=2)
    def _execute_with_retry(self, field: FieldMapping, value: Any):
        target = field.click_target
        if not target:
            target = ClickTarget(
                x=field.bbox_relative.x + field.bbox_relative.w / 2,
                y=field.bbox_relative.y + field.bbox_relative.h / 2
            )

        abs_x, abs_y = self._get_abs_coords(target.x, target.y)
        action = field.action.lower() if field.action else "click"
        ui_type = field.ui_type.lower()

        # Prioritize 'select' logic for complex components
        if action == "select" or (action == "click" and ui_type in ("radio", "dropdown", "date_picker") and value):
            if ui_type == "radio":
                self.handle_radio(field, value)
                return
            elif ui_type == "dropdown" or ui_type == "date_picker":
                self.handle_dropdown(field, value)
                return

        # Action Dispatch
        if action == "click":
            self.click(abs_x, abs_y)
        elif action == "double_click":
            self.click(abs_x, abs_y, clicks=2)
        elif action == "right_click":
            self.right_click(abs_x, abs_y)
        elif action == "triple_click":
            self.click(abs_x, abs_y, clicks=3)
        elif action == "hover":
            self.hover(abs_x, abs_y)
        elif action in ("click_then_type", "type"):
            self.fill_text(abs_x, abs_y, str(value))
        elif action == "triple_click_then_type":
            self.fill_text(abs_x, abs_y, str(value), triple=True)
        elif action in ("check", "uncheck"):
            # Assume click toggles, but we could add logic if we knew state
            self.click(abs_x, abs_y)
        elif action == "scroll":
            self.scroll(field)
        elif action == "drag":
            self.drag(field)
        elif action == "none":
            logger.debug(f"Action 'none' for {field.logical_key}")
        else:
            logger.warning(f"Action '{action}' is unhandled, attempting generic click")
            self.click(abs_x, abs_y)

    def click(self, x: int, y: int, clicks=1):
        self._human_delay()
        pyautogui.moveTo(x, y, duration=0.15)
        pyautogui.click(clicks=clicks)

    def right_click(self, x: int, y: int):
        self._human_delay()
        pyautogui.moveTo(x, y, duration=0.15)
        pyautogui.rightClick()

    def hover(self, x: int, y: int):
        self._human_delay()
        pyautogui.moveTo(x, y, duration=0.15)

    def fill_text(self, x: int, y: int, text: str, triple=False):
        if triple:
            self.click(x, y, clicks=3)
        else:
            self.click(x, y)
            pyautogui.hotkey('ctrl', 'a')

        self._human_delay(0.05, 0.1)
        pyautogui.press('backspace')
        self._human_delay(0.05, 0.1)
        pyautogui.write(text, interval=0.01)

    def handle_radio(self, field: FieldMapping, value: str):
        if not field.choices:
            logger.warning(f"No choices for radio {field.logical_key}, clicking main target")
            target = field.click_target or ClickTarget(
                x=field.bbox_relative.x + field.bbox_relative.w / 2,
                y=field.bbox_relative.y + field.bbox_relative.h / 2
            )
            abs_x, abs_y = self._get_abs_coords(target.x, target.y)
            self.click(abs_x, abs_y)
            return

        choice = self._find_choice(field.choices, str(value))
        if not choice:
            available = [c.label for c in field.choices]
            logger.error(f"Radio choice '{value}' not found for {field.logical_key}. Available: {available}")
            raise ValueError(f"Radio choice '{value}' not found for {field.logical_key}")

        if choice.scroll_steps > 0:
            self._scroll_steps_in_container(field, choice.scroll_steps)
            # Re-find choice coordinates after scrolling
            choice = self._find_choice(field.choices, str(value))

        if choice and choice.x is not None and choice.y is not None:
            cx, cy = self._get_abs_coords(choice.x, choice.y)
            self.click(cx, cy)
        else:
            logger.warning(f"Choice '{value}' has no coordinates after scrolling (x={choice.x if choice else 'N/A'}, y={choice.y if choice else 'N/A'})")

    def handle_dropdown(self, field: FieldMapping, value: str):
        target = field.click_target or ClickTarget(
            x=field.bbox_relative.x + field.bbox_relative.w / 2,
            y=field.bbox_relative.y + field.bbox_relative.h / 2
        )
        abs_x, abs_y = self._get_abs_coords(target.x, target.y)
        self.click(abs_x, abs_y)
        self._human_delay(0.4, 0.6)

        if field.choices:
            choice = self._find_choice(field.choices, str(value))
            if choice:
                if choice.scroll_steps > 0:
                    self._scroll_steps_in_container(field, choice.scroll_steps)
                    # Re-find choice coordinates after scrolling
                    choice = self._find_choice(field.choices, str(value))

                if choice and choice.x is not None and choice.y is not None:
                    cx, cy = self._get_abs_coords(choice.x, choice.y)
                    self.click(cx, cy)
                else:
                    logger.warning(f"Choice '{value}' has no coordinates after scrolling, falling back to typing")
                    pyautogui.write(str(value))
                    pyautogui.press('enter')
            else:
                pyautogui.write(str(value))
                pyautogui.press('enter')
        else:
            pyautogui.write(str(value))
            pyautogui.press('enter')

    def _scroll_steps_in_container(self, field: FieldMapping, n_steps: int):
        logger.info(f"Scrolling container for {field.logical_key} ({n_steps} steps)")
        for i in range(n_steps):
            self.scroll(field, step_mode=True)
            self._human_delay(0.1, 0.2)

    def scroll(self, field: FieldMapping, step_mode: bool = False):
        if not field.scroll_config:
            return

        strategy = field.scroll_config.strategy or "wheel"
        amount = 1 if step_mode else field.scroll_config.amount

        if strategy == "scrollbar" and field.scrollbar_target:
            sx, sy = self._get_abs_coords(field.scrollbar_target['x'], field.scrollbar_target['y'])
            for _ in range(amount):
                self.click(sx, sy)
                time.sleep(0.1)
        elif strategy == "drag_thumb":
            if not field.scrollbar_target:
                logger.warning(f"drag_thumb strategy requested for {field.logical_key} but no scrollbar_target defined. Falling back to wheel.")
                self._wheel_scroll(field, amount)
            else:
                sx, sy = self._get_abs_coords(field.scrollbar_target['x'], field.scrollbar_target['y'])
                direction = field.scroll_config.direction or "down"
                dist = field.scroll_config.amount if not step_mode else 10 # heuristic for 1 step in drag thumb
                if direction == "up":
                    dist = -dist

                self._human_delay()
                pyautogui.moveTo(sx, sy, duration=0.2)
                pyautogui.mouseDown()
                self._human_delay(0.1, 0.2)
                pyautogui.moveTo(sx, sy + dist, duration=0.4)
                self._human_delay(0.05, 0.1)
                pyautogui.mouseUp()
        else:
            # Default wheel scroll
            self._wheel_scroll(field, amount)

    def _wheel_scroll(self, field: FieldMapping, amount: int):
        # Determine scroll region
        if field.scroll_container:
            # Use scroll_container center
            cx = field.scroll_container['x'] + field.scroll_container['w'] / 2
            cy = field.scroll_container['y'] + field.scroll_container['h'] / 2
            abs_x, abs_y = self._get_abs_coords(cx, cy)
        else:
            # Use element bbox center
            abs_x, abs_y = self._get_abs_coords(
                field.bbox_relative.x + field.bbox_relative.w / 2,
                field.bbox_relative.y + field.bbox_relative.h / 2
            )

        pyautogui.moveTo(abs_x, abs_y, duration=0.15)
        direction = field.scroll_config.direction or "down"
        clicks = amount * (-1 if direction == "down" else 1)
        pyautogui.scroll(clicks)

    def drag(self, field: FieldMapping):
        if not field.drag_target:
            logger.error(f"Drag action called for {field.logical_key} but no drag_target defined")
            return

        target_element = next((e for e in self.elements if e.logical_key == field.drag_target), None)
        if not target_element:
            logger.error(f"Drag target '{field.drag_target}' not found in current screen elements")
            raise ValueError(f"Drag target '{field.drag_target}' not found")

        # Source coordinates
        src_target = field.click_target or ClickTarget(
            x=field.bbox_relative.x + field.bbox_relative.w / 2,
            y=field.bbox_relative.y + field.bbox_relative.h / 2
        )
        src_x, src_y = self._get_abs_coords(src_target.x, src_target.y)

        # Target coordinates
        tgt_target = target_element.click_target or ClickTarget(
            x=target_element.bbox_relative.x + target_element.bbox_relative.w / 2,
            y=target_element.bbox_relative.y + target_element.bbox_relative.h / 2
        )
        tgt_x, tgt_y = self._get_abs_coords(tgt_target.x, tgt_target.y)

        logger.info(f"Dragging from {field.logical_key} to {field.drag_target} ({src_x},{src_y} -> {tgt_x},{tgt_y})")

        self._human_delay()
        pyautogui.moveTo(src_x, src_y, duration=0.2)
        pyautogui.mouseDown()
        self._human_delay(0.1, 0.2)
        pyautogui.moveTo(tgt_x, tgt_y, duration=0.4)
        self._human_delay(0.05, 0.1)
        pyautogui.mouseUp()

    def _find_choice(self, choices: List[Choice], label: str) -> Optional[Choice]:
        for c in choices:
            if c.label.strip().lower() == label.strip().lower():
                return c
        return None
