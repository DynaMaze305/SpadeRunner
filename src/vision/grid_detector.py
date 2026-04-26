from __future__ import annotations

import cv2
import numpy as np


# Detects maze grid lines from a cleaned binary wall mask
class GridDetector:

    def extract_horizontal_vertical_lines(
        self,
        wall_clean: np.ndarray,
        horizontal_kernel_size: tuple[int, int] = (25, 1),
        vertical_kernel_size: tuple[int, int] = (1, 25),
    ):
        # Create a horizontal kernel to isolate long horizontal wall segments
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, horizontal_kernel_size)

        # Create a vertical kernel to isolate long vertical wall segments
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, vertical_kernel_size)

        # Keep mainly horizontal structures from the wall mask
        horizontal = cv2.morphologyEx(wall_clean, cv2.MORPH_OPEN, h_kernel)

        # Keep mainly vertical structures from the wall mask
        vertical = cv2.morphologyEx(wall_clean, cv2.MORPH_OPEN, v_kernel)

        # Return separated horizontal and vertical line masks
        return horizontal, vertical

    def get_projection_profiles(
        self,
        horizontal: np.ndarray,
        vertical: np.ndarray,
    ):
        # Sum vertical-line pixels column by column
        # Peaks in this profile represent x positions of vertical grid lines
        x_profile = vertical.sum(axis=0)

        # Sum horizontal-line pixels row by row
        # Peaks in this profile represent y positions of horizontal grid lines
        y_profile = horizontal.sum(axis=1)

        return x_profile, y_profile

    def extract_peaks(
        self,
        profile: np.ndarray,
        threshold_ratio: float = 0.1,
        min_gap: int = 15,
    ) -> list[int]:
        # Compute threshold as a fraction of the strongest detected line response
        threshold = profile.max() * threshold_ratio

        # Find all indices where the projection profile is above the threshold
        raw = np.where(profile > threshold)[0]

        # If no peaks are found, return an empty list
        if len(raw) == 0:
            return []

        # Group nearby indices that belong to the same thick grid line
        groups = []
        current = [raw[0]]

        for idx in raw[1:]:
            # If the next index is close enough, keep it in the same group
            if idx - current[-1] <= min_gap:
                current.append(idx)

            # Otherwise, start a new group
            else:
                groups.append(current)
                current = [idx]

        # Add the last group after the loop
        groups.append(current)

        # Convert each group into one center coordinate
        return [int(np.mean(group)) for group in groups]

    def detect_grid_lines(
        self,
        wall_clean: np.ndarray,
        threshold_ratio: float = 0.1,
        min_gap: int = 15,
    ):
        # Separate the cleaned wall mask into horizontal and vertical components
        horizontal, vertical = self.extract_horizontal_vertical_lines(wall_clean)

        # Build projection profiles to locate grid-line positions
        x_profile, y_profile = self.get_projection_profiles(horizontal, vertical)

        # Extract x coordinates of vertical grid lines
        x_lines = self.extract_peaks(x_profile, threshold_ratio, min_gap)

        # Extract y coordinates of horizontal grid lines
        y_lines = self.extract_peaks(y_profile, threshold_ratio, min_gap)

        # Return intermediate outputs and final detected grid coordinates
        return {
            "horizontal": horizontal,        # Mask containing horizontal wall lines
            "vertical": vertical,            # Mask containing vertical wall lines
            "x_profile": x_profile,          # Column-wise projection profile
            "y_profile": y_profile,          # Row-wise projection profile
            "x_lines": sorted(x_lines),      # Detected vertical grid-line positions
            "y_lines": sorted(y_lines),      # Detected horizontal grid-line positions
        }

    def draw_grid_lines(
        self,
        wall_clean: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
    ) -> np.ndarray:
        # Get image height and width
        h, w = wall_clean.shape

        # Convert grayscale wall mask to RGB so colored lines can be drawn
        overlay = cv2.cvtColor(wall_clean, cv2.COLOR_GRAY2RGB)

        # Draw vertical grid lines in blue
        for xg in x_lines:
            cv2.line(overlay, (xg, 0), (xg, h - 1), (255, 0, 0), 1)

        # Draw horizontal grid lines in green
        for yg in y_lines:
            cv2.line(overlay, (0, yg), (w - 1, yg), (0, 255, 0), 1)

        # Return wall mask with grid lines overlaid
        return overlay