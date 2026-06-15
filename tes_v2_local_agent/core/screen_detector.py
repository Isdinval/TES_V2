import cv2
import numpy as np
import mss
from PIL import Image
from loguru import logger
from typing import Dict, Optional
from tes_v2_local_agent.utils.image_utils import get_image_hash, compare_hashes, match_template

class ScreenDetector:
    def __init__(self, reference_images_dir: str):
        self.reference_images_dir = reference_images_dir
        self.sct = mss.mss()

    def capture_screenshot(self) -> Image.Image:
        monitor = self.sct.monitors[1] # Primary monitor
        sct_img = self.sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def detect_screen(self, expected_screen_name: str, reference_image_path: str) -> bool:
        logger.info(f"Checking if current screen is {expected_screen_name}")

        current_img = self.capture_screenshot()
        ref_img = Image.open(reference_image_path).convert("RGB")

        # 1. Perceptual Hash Check
        current_hash = get_image_hash(current_img)
        ref_hash = get_image_hash(ref_img)
        diff = compare_hashes(current_hash, ref_hash)

        if diff < 5: # Threshold for similarity
            logger.info(f"Screen match found via hash (diff={diff})")
            return True

        # 2. Template Matching Fallback (e.g. searching for a unique header/logo)
        # For simplicity in V1, we'll try a partial match if hash fails significantly
        current_cv = cv2.cvtColor(np.array(current_img), cv2.COLOR_RGB2GRAY)
        ref_cv = cv2.cvtColor(np.array(ref_img), cv2.COLOR_RGB2GRAY)

        # We might want to match only a sub-region, but for now we try full
        match = match_template(current_cv, ref_cv, threshold=0.9)
        if match:
            logger.info("Screen match found via template matching")
            return True

        logger.warning(f"Screen {expected_screen_name} not detected (hash diff={diff})")
        return False
