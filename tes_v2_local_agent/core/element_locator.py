import cv2
import numpy as np
import time
import os
import pyautogui
import imagehash
from loguru import logger
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import yaml

from tes_v2_local_agent.models.mapping import FieldMapping, ClickTarget, BBoxRelative
from tes_v2_local_agent.utils.image_utils import (
    match_template, match_orb, pil_to_cv2, get_grayscale,
    get_image_hash
)
from tes_v2_local_agent.core.screen_detector import ScreenDetector

class ElementLocator:
    def __init__(self, screen_detector: ScreenDetector, config_path: str = "tes_v2_local_agent/config/default_robustness.yaml"):
        self.screen_detector = screen_detector
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            logger.warning(f"Config file {config_path} not found, using defaults")
            self.config = {}

        self.curr_w, self.curr_h = pyautogui.size()
        logger.info("ElementLocator initialized")

    def wait_for_stability(self) -> Image.Image:
        """Waits until the screen image stabilizes."""
        attempts = 0
        max_attempts = self.config.get('stability_max_attempts', 5)
        wait_time = self.config.get('stability_wait_time', 0.5)
        threshold = self.config.get('hash_similarity_threshold', 0.95)

        prev_img = self.screen_detector.capture_screenshot()
        prev_hash_str = get_image_hash(prev_img)
        prev_hash = imagehash.hex_to_hash(prev_hash_str)

        while attempts < max_attempts:
            time.sleep(wait_time)
            curr_img = self.screen_detector.capture_screenshot()
            curr_hash_str = get_image_hash(curr_img)
            curr_hash = imagehash.hex_to_hash(curr_hash_str)

            diff = prev_hash - curr_hash
            similarity = 1.0 - (diff / 64.0)

            if similarity >= threshold:
                logger.debug(f"Screen stabilized (similarity={similarity:.4f})")
                return curr_img

            logger.debug(f"Waiting for stability... (similarity={similarity:.4f})")
            prev_hash = curr_hash
            attempts += 1

        logger.warning("Screen did not stabilize within timeout, continuing anyway")
        return self.screen_detector.capture_screenshot()

    def locate_element(self, field: FieldMapping, mapping_dir: str, ref_screenshot: Image.Image) -> Optional[ClickTarget]:
        """
        Locates an element dynamically.
        mapping_dir: used to resolve anchor template paths.
        ref_screenshot: the original screenshot used during mapping.
        """
        if not field.requires_relocation:
            logger.debug(f"Relocation not required for {field.logical_key}")
            return field.click_target

        logger.info(f"Locating element: {field.logical_key}")

        # Try to locate with multiple attempts including scrolling
        for attempt in range(self.config.get('max_scroll_attempts', 6) + 1):
            # 1. Wait for stability and capture
            current_img = self.wait_for_stability()

            # 2. Try locating
            found_pos = self._try_locate(field, mapping_dir, ref_screenshot, current_img)

            if found_pos:
                # found_pos is in absolute pixels
                rel_x = found_pos[0] / self.curr_w
                rel_y = found_pos[1] / self.curr_h
                logger.info(f"Element {field.logical_key} located at rel({rel_x:.4f}, {rel_y:.4f})")
                return ClickTarget(x=rel_x, y=rel_y)

            # 3. Not found, try scrolling
            if attempt < self.config.get('max_scroll_attempts', 6):
                logger.info(f"Element {field.logical_key} not found, scrolling down (Attempt {attempt+1})")
                self._scroll_down()
            else:
                logger.warning(f"Failed to locate {field.logical_key} after scrolling")

        return None

    def _try_locate(self, field: FieldMapping, mapping_dir: str, ref_img: Image.Image, curr_img: Image.Image) -> Optional[Tuple[int, int]]:
        """Core logic for finding the element in the current image."""
        curr_cv = pil_to_cv2(curr_img)
        curr_gray = get_grayscale(curr_cv)

        # Region of Interest (ROI) for search
        search_margin = getattr(field, 'search_margin', self.config.get('default_search_margin', 0.25))

        # Priority 1: Label Anchor
        if field.label_anchor and field.label_anchor.template_path:
            anchor_path = os.path.join(mapping_dir, field.label_anchor.template_path)
            if os.path.exists(anchor_path):
                template = cv2.imread(anchor_path, cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    # Define search area around expected anchor position
                    anchor_bbox = field.label_anchor.bbox_relative
                    match = self._match_in_roi(curr_gray, template, anchor_bbox, search_margin, "template")
                    if match:
                        ax, ay, aw, ah = match
                        # Calculate offset from anchor to click target
                        orig_ax = anchor_bbox.x + anchor_bbox.w / 2
                        orig_ay = anchor_bbox.y + anchor_bbox.h / 2

                        orig_tx = field.click_target.x if field.click_target else (field.bbox_relative.x + field.bbox_relative.w / 2)
                        orig_ty = field.click_target.y if field.click_target else (field.bbox_relative.y + field.bbox_relative.h / 2)

                        dx = orig_tx - orig_ax
                        dy = orig_ty - orig_ay

                        new_ax_px = ax + aw / 2
                        new_ay_px = ay + ah / 2

                        target_x = new_ax_px + (dx * self.curr_w)
                        target_y = new_ay_px + (dy * self.curr_h)

                        logger.debug(f"Found via anchor. New target: {target_x}, {target_y}")
                        return int(target_x), int(target_y)
            else:
                logger.warning(f"Anchor template not found: {anchor_path}")

        # Fallback 2: Feature matching on the field itself
        ref_cv = pil_to_cv2(ref_img)
        ref_gray = get_grayscale(ref_cv)

        # Crop the element from reference
        rx, ry, rw, rh = (int(field.bbox_relative.x * ref_img.width),
                          int(field.bbox_relative.y * ref_img.height),
                          int(field.bbox_relative.w * ref_img.width),
                          int(field.bbox_relative.h * ref_img.height))
        element_template = ref_gray[ry:ry+rh, rx:rx+rw]

        match = self._match_in_roi(curr_gray, element_template, field.bbox_relative, search_margin, "orb")
        if match:
            mx, my, mw, mh = match
            target_x = mx + mw / 2
            target_y = my + mh / 2
            logger.debug(f"Found via ORB. New target: {target_x}, {target_y}")
            return int(target_x), int(target_y)

        return None

    def _match_in_roi(self, scene_gray: np.ndarray, template: np.ndarray, expected_bbox: BBoxRelative, margin: float, method: str) -> Optional[Tuple[int, int, int, int]]:
        # Define ROI
        x1 = max(0, int((expected_bbox.x - margin) * self.curr_w))
        y1 = max(0, int((expected_bbox.y - margin) * self.curr_h))
        x2 = min(self.curr_w, int((expected_bbox.x + expected_bbox.w + margin) * self.curr_w))
        y2 = min(self.curr_h, int((expected_bbox.y + expected_bbox.h + margin) * self.curr_h))

        roi = scene_gray[y1:y2, x1:x2]

        if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
            return None

        if method == "template":
            match = match_template(roi, template, self.config.get('template_matching_threshold', 0.85))
        else:
            match = match_orb(roi, template, self.config.get('orb_matching_threshold', 0.70))

        if match:
            rx, ry, rw, rh = match
            return (rx + x1, ry + y1, rw, rh)

        return None

    def _scroll_down(self):
        # Click center to ensure focus
        pyautogui.click(self.curr_w // 2, self.curr_h // 2)
        time.sleep(0.1)
        pyautogui.scroll(-self.config.get('scroll_step', 300))
        time.sleep(self.config.get('scroll_pause', 0.5))
