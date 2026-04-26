from __future__ import annotations

import cv2
import numpy as np


# =========================
# Configuration constants
# =========================

# Pink HSV ranges (handles hue wrap-around)
PINK_LOWER_1 = np.array([140, 60, 60])
PINK_UPPER_1 = np.array([179, 255, 255])

PINK_LOWER_2 = np.array([0, 60, 60])
PINK_UPPER_2 = np.array([5, 255, 255])

# Morphological kernel
MORPH_KERNEL = np.ones((3, 3), np.uint8)

# Crop regions
DEFAULT_CROP_BBOX = (20, 120, 778, 380)
LAB2_CROP_BBOX = (20, 115, 785, 370)


# Handles detection of pink regions in an image and cropping a predefined area
class ColorDetectorImageCropper:

    def detect_pink_mask(self, image: np.ndarray) -> np.ndarray:
        # Convert image from BGR (OpenCV default) to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Create binary masks for both pink ranges
        mask1 = cv2.inRange(hsv, PINK_LOWER_1, PINK_UPPER_1)
        mask2 = cv2.inRange(hsv, PINK_LOWER_2, PINK_UPPER_2)

        # Combine both masks into a single mask
        mask = cv2.bitwise_or(mask1, mask2)

        # Apply morphological operations to clean the mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, MORPH_KERNEL, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, MORPH_KERNEL, iterations=1)

        return mask

    def detect_and_crop_pink_object(
        self,
        image: np.ndarray,
    ):
        # Generate the pink mask for the full image
        pink_mask = self.detect_pink_mask(image)

        # Use predefined crop region
        x1, y1, x2, y2 = DEFAULT_CROP_BBOX

        # x1, y1, x2, y2 = LAB2_CROP_BBOX

        # Crop both the original image and its corresponding mask
        cropped = image[y1:y2, x1:x2]
        cropped_mask = pink_mask[y1:y2, x1:x2]

        # Draw crop bounding box for visualization
        boxed_image = image.copy()
        cv2.rectangle(boxed_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

        return {
            "crop_bbox": (x1, y1, x2, y2),
            "cropped": cropped,
            "cropped_mask": cropped_mask,
            "boxed_image": boxed_image,
            "pink_mask": pink_mask,
        }