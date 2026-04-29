from __future__ import annotations

import cv2
import numpy as np

MORPH_KERNEL = np.ones((3, 3), np.uint8)


def detect_black_mask(image: np.ndarray) -> np.ndarray:
    # Convert BGR → LAB
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    lower_black = np.array([0, 0, 0])
    upper_black = np.array([60, 255, 255])  # key: low L

    mask_black = cv2.inRange(lab, lower_black, upper_black)

    # Morphological cleaning
    mask_black = cv2.morphologyEx(mask_black, cv2.MORPH_CLOSE, MORPH_KERNEL, iterations=2)
    mask_black = cv2.morphologyEx(mask_black, cv2.MORPH_OPEN, MORPH_KERNEL, iterations=1)

    return mask_black

def extract_obstacles_from_mask(
    mask: np.ndarray,
    min_area: int = 35,
    max_area: int = 500,
    min_width: int = 6,
    min_height: int = 6,
    max_width: int = 35,
    max_height: int = 35,
    min_fill_ratio: float = 0.35,
    max_aspect_ratio: float = 1.8,
    border_margin: int = 8,
) -> list[tuple[int, int, int, int]]:

    kernel = np.ones((3, 3), np.uint8)
    mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(
        mask_clean,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    h_img, w_img = mask.shape[:2]
    obstacles = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)

        if x < border_margin or y < border_margin:
            continue
        if x + w > w_img - border_margin or y + h > h_img - border_margin:
            continue

        if not (min_area <= area <= max_area):
            continue

        if not (min_width <= w <= max_width and min_height <= h <= max_height):
            continue

        aspect = max(w / h, h / w)
        if aspect > max_aspect_ratio:
            continue

        fill_ratio = area / float(w * h)
        if fill_ratio < min_fill_ratio:
            continue

        obstacles.append((x, y, x + w, y + h))

    return obstacles