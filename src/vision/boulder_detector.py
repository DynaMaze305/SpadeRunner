from __future__ import annotations

import cv2
import numpy as np

from vision.obstacles_detector import extract_obstacles_from_mask

MORPH_KERNEL = np.ones((3, 3), np.uint8)
Coordinate = tuple[int, int]


class BoulderDetector:
    def detect_green_mask(self, image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])

        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        mask_green = cv2.morphologyEx(
            mask_green,
            cv2.MORPH_CLOSE,
            MORPH_KERNEL,
            iterations=2,
        )
        mask_green = cv2.morphologyEx(
            mask_green,
            cv2.MORPH_OPEN,
            MORPH_KERNEL,
            iterations=1,
        )

        return mask_green

    def extract_boulder_coordinates(
        self,
        mask: np.ndarray,
        min_area: int = 20,
        max_area: int = 2000,
        min_width: int = 6,
        min_height: int = 6,
        max_width: int = 55,
        max_height: int = 55,
        min_fill_ratio: float = 0.15,
        max_aspect_ratio: float = 4.0,
        border_margin: int = 3,
    ) -> list[Coordinate]:
        boulder_boxes = extract_obstacles_from_mask(
            mask=mask,
            min_area=min_area,
            max_area=max_area,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            min_fill_ratio=min_fill_ratio,
            max_aspect_ratio=max_aspect_ratio,
            border_margin=border_margin,
        )

        return [
            ((x1 + x2) // 2, (y1 + y2) // 2)
            for x1, y1, x2, y2 in boulder_boxes
        ]

    def detect_boulders(self, image: np.ndarray) -> tuple[np.ndarray, list[Coordinate]]:
        boulder_mask = self.detect_green_mask(image)
        boulder_coordinates = self.extract_boulder_coordinates(boulder_mask)

        return boulder_mask, boulder_coordinates
