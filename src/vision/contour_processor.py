from __future__ import annotations

import cv2
import numpy as np


# Handles contour extraction, filtering, drawing, and binary wall-mask cleanup
class ContourProcessor:

    def get_filtered_contours_in_crop(
        self,
        mask: np.ndarray,
        crop_bbox: tuple[int, int, int, int],
        image: np.ndarray,
        min_area,
    ):
        # Extract crop coordinates from the bounding box
        x1, y1, x2, y2 = crop_bbox

        # Crop the mask to only process the region of interest
        cropped_mask = mask[y1:y2, x1:x2]

        # Crop the original image using the same region
        # .copy() prevents changes from affecting the original image
        cropped_image = image[y1:y2, x1:x2].copy()

        # Find contours inside the cropped binary mask
        contours, _ = cv2.findContours(
            cropped_mask,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        # Keep only contours whose area is larger than the minimum threshold
        # This removes small noisy detections
        filtered = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]

        # Draw the filtered contours on top of the cropped original image
        drawn_image = cropped_image.copy()
        cv2.drawContours(drawn_image, filtered, -1, (0, 255, 0), 2)

        # Create a blank image with only the detected contours drawn on it
        blank = np.zeros_like(cropped_image)
        cv2.drawContours(blank, filtered, -1, (0, 255, 0), 2)

        # Return all useful outputs for debugging and downstream processing
        return {
            "contours": filtered,              # Filtered contours after area thresholding
            "cropped_mask": cropped_mask,      # Mask cropped to the region of interest
            "cropped_image": cropped_image,    # Original image cropped to the same region
            "drawn_image": drawn_image,        # Cropped image with contours drawn
            "contours_only_image": blank,      # Blank image containing only contour outlines
        }

    def create_wall_binary(self, cropped_mask: np.ndarray) -> np.ndarray:
        # Convert the mask into a clean binary image:
        # - pixels > 0 become 255 (white)
        # - pixels == 0 stay 0 (black)
        return (cropped_mask > 0).astype(np.uint8) * 255

    def clean_wall_mask(
        self,
        wall_bin: np.ndarray,
        kernel_size: tuple[int, int] = (3, 3),
    ) -> np.ndarray:
        # Create a morphological kernel used to clean the binary mask
        kernel = np.ones(kernel_size, np.uint8)

        # Remove small white noise from the wall mask
        wall_clean = cv2.morphologyEx(wall_bin, cv2.MORPH_OPEN, kernel)

        # Fill small gaps or holes in the detected wall regions
        wall_clean = cv2.morphologyEx(wall_clean, cv2.MORPH_CLOSE, kernel)

        # Return cleaned binary wall mask
        return wall_clean