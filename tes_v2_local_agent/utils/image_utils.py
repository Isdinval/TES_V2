import cv2
import numpy as np
from PIL import Image
import imagehash
from typing import Tuple, Optional, List
from loguru import logger

def get_image_hash(image: Image.Image) -> str:
    return str(imagehash.phash(image))

def compare_hashes(hash1: str, hash2: str) -> int:
    return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)

def match_template(scene_gray: np.ndarray, template_gray: np.ndarray, threshold: float = 0.8) -> Optional[Tuple[int, int, int, int]]:
    """
    Returns (x, y, w, h) of the best match if above threshold.
    """
    if template_gray.shape[0] > scene_gray.shape[0] or template_gray.shape[1] > scene_gray.shape[1]:
        logger.warning("Template is larger than scene")
        return None

    res = cv2.matchTemplate(scene_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        h, w = template_gray.shape
        return (max_loc[0], max_loc[1], w, h)
    return None

def match_orb(scene_gray: np.ndarray, template_gray: np.ndarray, threshold: float = 0.7) -> Optional[Tuple[int, int, int, int]]:
    """
    Finds template in scene using ORB features.
    Returns (x, y, w, h) of the bounding box in the scene.
    """
    orb = cv2.ORB_create(nfeatures=1000)
    kp1, des1 = orb.detectAndCompute(template_gray, None)
    kp2, des2 = orb.detectAndCompute(scene_gray, None)

    if des1 is None or des2 is None:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)

    # Use top matches to find homography
    good_matches = matches[:50]
    if len(good_matches) < 4:
        return None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is not None:
        h, w = template_gray.shape
        pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(pts, M)

        # Calculate bounding box of the transformed points
        x_coords = dst[:, 0, 0]
        y_coords = dst[:, 0, 1]

        xmin, xmax = int(np.min(x_coords)), int(np.max(x_coords))
        ymin, ymax = int(np.min(y_coords)), int(np.max(y_coords))

        # Basic sanity check on dimensions
        if (xmax - xmin) < w * 0.5 or (xmax - xmin) > w * 1.5:
             return None

        return (xmin, ymin, xmax - xmin, ymax - ymin)

    return None

def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))

def get_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image
