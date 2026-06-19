import cv2
import numpy as np
import mss
from PIL import Image, ImageDraw
from loguru import logger
from typing import Dict, Optional, List
import yaml
import os

from tes_v2_local_agent.utils.image_utils import get_image_hash, compare_hashes, match_template
from tes_v2_local_agent.models.mapping import ScreenMapping

class ScreenDetector:
    def __init__(self, reference_images_dir: str, config_path: str = "tes_v2_local_agent/config/default_robustness.yaml"):
        self.reference_images_dir = reference_images_dir
        self.sct = mss.mss()

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}

    def capture_screenshot(self) -> Image.Image:
        monitor = self.sct.monitors[1] # Primary monitor
        sct_img = self.sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def detect_screen(self, expected_screen_name: str, reference_image_path: str, mapping: Optional[ScreenMapping] = None) -> bool:
        logger.info(f"Checking if current screen is {expected_screen_name}")

        current_img = self.capture_screenshot()
        ref_img = Image.open(reference_image_path).convert("RGB")

        # Robustness: Mask input fields to handle partially filled forms
        if self.config.get('mask_inputs_in_hash', True) and mapping:
            current_img = self._mask_elements(current_img, mapping)
            ref_img = self._mask_elements(ref_img, mapping)

        # 1. Perceptual Hash Check
        current_hash = get_image_hash(current_img)
        ref_hash = get_image_hash(ref_img)
        diff = compare_hashes(current_hash, ref_hash)

        # phash is 64 bits. Threshold of 5-8 is usually good.
        if diff < 10:
            logger.info(f"Screen match found via hash (diff={diff})")
            return True

        # 2. Template Matching Fallback
        current_cv = cv2.cvtColor(np.array(current_img), cv2.COLOR_RGB2GRAY)
        ref_cv = cv2.cvtColor(np.array(ref_img), cv2.COLOR_RGB2GRAY)

        # We try a few small stable crops if we had them,
        # but for now we try matching the whole (masked) screen
        match = match_template(current_cv, ref_cv, threshold=0.9)
        if match:
            logger.info("Screen match found via template matching")
            return True

        logger.warning(f"Screen {expected_screen_name} not detected (hash diff={diff})")
        return False

    def _mask_elements(self, img: Image.Image, mapping: ScreenMapping) -> Image.Image:
        """Masks input-like elements with black rectangles to ignore their content during hash comparison."""
        draw = ImageDraw.Draw(img)
        INPUT_TYPES = ("input", "text_area", "combobox", "date_picker")

        for element in mapping.elements:
            if element.ui_type.lower() in INPUT_TYPES:
                x = int(element.bbox_relative.x * img.width)
                y = int(element.bbox_relative.y * img.height)
                w = int(element.bbox_relative.w * img.width)
                h = int(element.bbox_relative.h * img.height)
                draw.rectangle([x, y, x + w, y + h], fill="black")

        return img
