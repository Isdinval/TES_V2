import cv2
import numpy as np
from PIL import Image
import imagehash
from typing import Tuple, Optional

def get_image_hash(image: Image.Image) -> str:
    return str(imagehash.phash(image))

def compare_hashes(hash1: str, hash2: str) -> int:
    return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)

def match_template(scene_gray: np.ndarray, template_gray: np.ndarray, threshold: float = 0.8) -> Optional[Tuple[int, int, int, int]]:
    """
    Returns (x, y, w, h) of the best match if above threshold.
    """
    res = cv2.matchTemplate(scene_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        h, w = template_gray.shape
        return (max_loc[0], max_loc[1], w, h)
    return None
