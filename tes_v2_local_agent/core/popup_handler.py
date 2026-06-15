import os
import cv2
import numpy as np
from loguru import logger
from tes_v2_local_agent.utils.image_utils import match_template

class PopupHandler:
    def __init__(self, popup_refs_dir: str, action_executor):
        self.popup_refs_dir = popup_refs_dir
        self.executor = action_executor
        self.known_popups = []
        self._load_known_popups()

    def _load_known_popups(self):
        if os.path.exists(self.popup_refs_dir):
            for f in os.listdir(self.popup_refs_dir):
                if f.endswith(".png"):
                    self.known_popups.append(f)
        logger.info(f"Loaded {len(self.known_popups)} known popup templates")

    def check_and_handle(self, screenshot_cv: np.ndarray) -> bool:
        """
        Checks for known popups and clicks them if found.
        Returns True if a popup was handled.
        """
        for popup_file in self.known_popups:
            template_path = os.path.join(self.popup_refs_dir, popup_file)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

            match = match_template(screenshot_cv, template, threshold=0.9)
            if match:
                x, y, w, h = match
                logger.warning(f"Detected and handling known popup: {popup_file}")
                # Click center of the match (likely the 'OK' or 'Close' button)
                self.executor.click(x + w//2, y + h//2)
                return True
        return False
