import pyautogui
import time
import random
from loguru import logger
from typing import Any, Optional, List
from tes_v2_local_agent.models.mapping import FieldMapping, ClickTarget, Choice
from tes_v2_local_agent.utils.retry import retry

class ActionExecutor:
    def __init__(self, resolution: tuple[int, int], dry_run: bool = False):
        self.res_w, self.res_h = resolution
        self.dry_run = dry_run
        if not dry_run:
            pyautogui.PAUSE = 0.5
            pyautogui.FAILSAFE = True
        logger.info(f"ActionExecutor initialized (Res: {resolution}, Dry Run: {dry_run})")

    def _human_delay(self, min_s=0.3, max_s=0.8):
        if not self.dry_run:
            time.sleep(random.uniform(min_s, max_s))

    def _get_abs_coords(self, rel_x: float, rel_y: float) -> tuple[int, int]:
        # Add a tiny random offset (1-3 pixels) for anti-bot
        offset_x = random.randint(-2, 2)
        offset_y = random.randint(-2, 2)
        return int(rel_x * self.res_w) + offset_x, int(rel_y * self.res_h) + offset_y

    def execute_action(self, field: FieldMapping, value: Any):
        if value is None or value == "":
            logger.debug(f"Skipping empty value for field {field.logical_key}")
            return

        msg = f"Action '{field.action}' on field '{field.logical_key}' (Type: {field.ui_type}) with value '{value}'"
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
        # Determine main click target
        target = field.click_target
        if not target:
            target = ClickTarget(
                x=field.bbox_relative.x + field.bbox_relative.w / 2,
                y=field.bbox_relative.y + field.bbox_relative.h / 2
            )

        abs_x, abs_y = self._get_abs_coords(target.x, target.y)

        # UI Type specific logic
        ut = field.ui_type
        if ut in ("input", "textarea", "date"):
            self.fill_text(abs_x, abs_y, str(value))
        elif ut == "button":
            self.click(abs_x, abs_y)
        elif ut == "checkbox":
            self.handle_checkbox(abs_x, abs_y, value)
        elif ut == "radio":
            self.handle_radio(field, value)
        elif ut == "dropdown":
            self.handle_dropdown(field, value)
        elif ut == "scroll_area":
            self.scroll(field)
        elif ut == "file_upload":
            self.handle_file_upload(abs_x, abs_y, str(value))
        else:
            logger.warning(f"UI Type '{ut}' is unhandled, attempting generic click")
            self.click(abs_x, abs_y)

    def click(self, x: int, y: int, clicks=1):
        self._human_delay()
        duration = random.uniform(0.3, 0.6)
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
        pyautogui.click(clicks=clicks)

    def fill_text(self, x: int, y: int, text: str):
        self.click(x, y)
        # Force focus / select all
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        self._human_delay(0.1, 0.3)
        # Type with slight variations in interval
        pyautogui.write(text, interval=random.uniform(0.02, 0.08))
        pyautogui.press('enter')

    def handle_checkbox(self, x: int, y: int, value: Any):
        # In V1, we assume 'value' means 'should be checked'
        if bool(value):
            self.click(x, y)

    def handle_radio(self, field: FieldMapping, value: str):
        if not field.choices:
            logger.warning(f"No choices for radio {field.logical_key}, clicking main target")
            abs_x, abs_y = self._get_abs_coords(field.click_target.x, field.click_target.y)
            self.click(abs_x, abs_y)
            return

        choice = self._find_choice(field.choices, str(value))
        if choice:
            cx, cy = self._get_abs_coords(choice.x, choice.y)
            self.click(cx, cy)
        else:
            raise ValueError(f"Radio choice '{value}' not found for {field.logical_key}")

    def handle_dropdown(self, field: FieldMapping, value: str):
        # 1. Open dropdown
        abs_x, abs_y = self._get_abs_coords(field.click_target.x, field.click_target.y)
        self.click(abs_x, abs_y)
        self._human_delay(0.5, 1.0) # Wait for animation

        # 2. Select choice
        if field.choices:
            choice = self._find_choice(field.choices, str(value))
            if choice:
                cx, cy = self._get_abs_coords(choice.x, choice.y)
                self.click(cx, cy)
            else:
                # Fallback: try typing the value to filter or select (depends on UI)
                pyautogui.write(str(value))
                pyautogui.press('enter')
        else:
            # No choices mapped, try typing
            pyautogui.write(str(value))
            pyautogui.press('enter')

    def handle_file_upload(self, x: int, y: int, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for upload: {file_path}")

        # Click the upload button to open dialog
        self.click(x, y)
        self._human_delay(1.0, 2.0) # Wait for dialog

        # Type path and enter (works on most Windows/Linux dialogs)
        pyautogui.write(file_path)
        pyautogui.press('enter')

    def scroll(self, field: FieldMapping):
        if not field.scroll_config:
            return
        # Move to center of scroll area first
        abs_x, abs_y = self._get_abs_coords(
            field.bbox_relative.x + field.bbox_relative.w / 2,
            field.bbox_relative.y + field.bbox_relative.h / 2
        )
        pyautogui.moveTo(abs_x, abs_y, duration=0.3)

        clicks = field.scroll_config.amount * (-1 if field.scroll_config.direction == "down" else 1)
        pyautogui.scroll(clicks)

    def _find_choice(self, choices: List[Choice], label: str) -> Optional[Choice]:
        # Simple exact match or case-insensitive
        for c in choices:
            if c.label.strip().lower() == label.strip().lower():
                return c
        return None
