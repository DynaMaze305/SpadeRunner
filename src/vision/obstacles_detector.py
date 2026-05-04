from __future__ import annotations

import cv2
import numpy as np

from common.config import ARUCO_ID
from vision.aruco_detector import ArucoDetector

MORPH_KERNEL = np.ones((3, 3), np.uint8)
ROBOT_EXCLUSION_PADDING_PX = 18
Box = tuple[int, int, int, int]


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
    min_area: int = 30,
    max_area: int = 500,
    min_width: int = 6,
    min_height: int = 6,
    max_width: int = 35,
    max_height: int = 35,
    min_fill_ratio: float = 0.35,
    max_aspect_ratio: float = 1.8,
    border_margin: int = 8,
) -> list[Box]:

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


def detect_robot_exclusion_boxes(
    image: np.ndarray,
    aruco_detector: ArucoDetector | None = None,
    aruco_id: int = ARUCO_ID,
    padding_px: int = ROBOT_EXCLUSION_PADDING_PX,
) -> list[Box]:
    detector = aruco_detector or ArucoDetector()
    result = detector.detect_pose(image, target_id=aruco_id)
    pose = result["pose"]
    if pose is None:
        return []

    h_img, w_img = image.shape[:2]
    corners = pose["corners"]
    x1 = max(0, int(np.floor(corners[:, 0].min())) - padding_px)
    y1 = max(0, int(np.floor(corners[:, 1].min())) - padding_px)
    x2 = min(w_img - 1, int(np.ceil(corners[:, 0].max())) + padding_px)
    y2 = min(h_img - 1, int(np.ceil(corners[:, 1].max())) + padding_px)

    return [(x1, y1, x2, y2)]


def mask_robot_exclusions(
    mask: np.ndarray,
    exclusion_boxes: list[Box],
) -> np.ndarray:
    output = mask.copy()
    for x1, y1, x2, y2 in exclusion_boxes:
        cv2.rectangle(output, (x1, y1), (x2, y2), 0, -1)
    return output


def detect_obstacles(
    image: np.ndarray,
    aruco_detector: ArucoDetector | None = None,
    aruco_id: int = ARUCO_ID,
    robot_padding_px: int = ROBOT_EXCLUSION_PADDING_PX,
) -> tuple[np.ndarray, list[Box], list[Box]]:
    obstacle_mask = detect_black_mask(image)
    robot_exclusion_boxes = detect_robot_exclusion_boxes(
        image,
        aruco_detector=aruco_detector,
        aruco_id=aruco_id,
        padding_px=robot_padding_px,
    )
    obstacle_mask = mask_robot_exclusions(obstacle_mask, robot_exclusion_boxes)
    obstacles = extract_obstacles_from_mask(obstacle_mask)

    return obstacle_mask, obstacles, robot_exclusion_boxes
