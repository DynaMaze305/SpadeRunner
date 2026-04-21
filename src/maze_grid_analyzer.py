from __future__ import annotations
import cv2
import numpy as np


class MazeGridAnalyzer:
    """
    Analyze a binary wall mask and infer maze grid structure.

    Expected input:
        wall_mask: binary image where walls are white (255) and background is black (0)
    """

    def __init__(self, wall_mask: np.ndarray) -> None:
        if wall_mask is None:
            raise ValueError("wall_mask cannot be None.")

        if len(wall_mask.shape) != 2:
            raise ValueError("wall_mask must be a single-channel binary image.")

        self.wall_mask = wall_mask

    def get_wall_mask(self) -> np.ndarray:
        return self.wall_mask

    def extract_horizontal_vertical_walls(
        self,
        horizontal_kernel_size: int = 25,
        vertical_kernel_size: int = 25,
    ) -> dict[str, np.ndarray]:
        """
        Extract horizontal and vertical wall components from the wall mask.
        """
        h_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (horizontal_kernel_size, 1)
        )
        v_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, vertical_kernel_size)
        )

        horizontal = cv2.morphologyEx(self.wall_mask, cv2.MORPH_OPEN, h_kernel)
        vertical = cv2.morphologyEx(self.wall_mask, cv2.MORPH_OPEN, v_kernel)

        return {
            "horizontal": horizontal,
            "vertical": vertical,
        }

    def get_wall_projection_profiles(
        self,
        horizontal: np.ndarray,
        vertical: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """
        Compute projection profiles from extracted horizontal and vertical walls.
        """
        x_profile = vertical.sum(axis=0)
        y_profile = horizontal.sum(axis=1)

        return {
            "x_profile": x_profile,
            "y_profile": y_profile,
        }

    def extract_profile_peaks(
        self,
        profile: np.ndarray,
        threshold_ratio: float = 0.3,
        min_gap: int = 15,
    ) -> list[int]:
        """
        Extract grouped peak centers from a 1D projection profile.
        """
        if profile.size == 0:
            return []

        threshold = profile.max() * threshold_ratio
        raw = np.where(profile > threshold)[0]

        if len(raw) == 0:
            return []

        groups = []
        current = [raw[0]]

        for idx in raw[1:]:
            if idx - current[-1] <= min_gap:
                current.append(idx)
            else:
                groups.append(current)
                current = [idx]

        groups.append(current)

        centers = [int(np.mean(group)) for group in groups]
        return centers

    def detect_grid_lines_from_profiles(
        self,
        x_profile: np.ndarray,
        y_profile: np.ndarray,
        x_threshold_ratio: float = 0.3,
        y_threshold_ratio: float = 0.1,
        min_gap: int = 15,
    ) -> dict[str, list[int]]:
        """
        Detect candidate grid lines from x and y projection profiles.
        """
        x_lines = self.extract_profile_peaks(
            x_profile,
            threshold_ratio=x_threshold_ratio,
            min_gap=min_gap,
        )
        y_lines = self.extract_profile_peaks(
            y_profile,
            threshold_ratio=y_threshold_ratio,
            min_gap=min_gap,
        )

        return {
            "x_lines": x_lines,
            "y_lines": y_lines,
        }

    def get_cell_centers(
        self,
        x_lines: list[int],
        y_lines: list[int],
    ) -> dict[str, tuple[int, int]]:
        """
        Compute cell centers and assign labels like A1, A2, B1...
        """
        import string

        n_cols = len(x_lines) - 1
        n_rows = len(y_lines) - 1

        if n_cols <= 0 or n_rows <= 0:
            return {}

        row_labels = list(string.ascii_uppercase)[:n_rows]
        col_labels = [str(i + 1) for i in range(n_cols)]

        cell_centers = {}

        for r in range(n_rows):
            for c in range(n_cols):
                center_x = (x_lines[c] + x_lines[c + 1]) // 2
                center_y = (y_lines[r] + y_lines[r + 1]) // 2
                label = f"{row_labels[r]}{col_labels[c]}"
                cell_centers[label] = (center_x, center_y)

        return cell_centers

    def get_grid_walls(
        self,
        x_lines: list[int],
        y_lines: list[int],
        threshold: float = 100,
    ) -> dict[str, dict[str, bool]]:
        """
        Determine which sides of each cell contain walls using single-pixel borders.
        """
        import string

        n_cols = len(x_lines) - 1
        n_rows = len(y_lines) - 1

        grid_walls = {}

        def is_wall(pixel_slice: np.ndarray) -> bool:
            if pixel_slice.size == 0:
                return False
            return float(np.mean(pixel_slice)) > threshold

        for r in range(n_rows):
            for c in range(n_cols):
                x1, x2 = x_lines[c], x_lines[c + 1]
                y1, y2 = y_lines[r], y_lines[r + 1]

                walls = {
                    "bottom": is_wall(self.wall_mask[y1, x1:x2]),
                    "top": is_wall(self.wall_mask[y2, x1:x2]),
                    "left": is_wall(self.wall_mask[y1:y2, x1]),
                    "right": is_wall(self.wall_mask[y1:y2, x2]),
                }

                label = f"{string.ascii_uppercase[r]}{c + 1}"
                grid_walls[label] = walls

        return grid_walls

    def get_grid_walls_with_band(
        self,
        x_lines: list[int],
        y_lines: list[int],
        threshold: float = 100,
        band: int = 3,
    ) -> dict[str, dict[str, bool]]:
        """
        Determine which sides of each cell contain walls using a small band
        around each cell border instead of a single row/column.
        """
        import string

        h, w = self.wall_mask.shape
        n_cols = len(x_lines) - 1
        n_rows = len(y_lines) - 1

        grid_walls = {}

        def clip(a: int, low: int, high: int) -> int:
            return max(low, min(a, high))

        def is_wall(pixel_slice: np.ndarray) -> bool:
            if pixel_slice.size == 0:
                return False
            return float(np.mean(pixel_slice)) > threshold

        for r in range(n_rows):
            for c in range(n_cols):
                x1, x2 = x_lines[c], x_lines[c + 1]
                y1, y2 = y_lines[r], y_lines[r + 1]

                bottom_slice = self.wall_mask[
                    clip(y1 - band, 0, h):clip(y1 + band + 1, 0, h),
                    clip(x1, 0, w):clip(x2, 0, w),
                ]
                top_slice = self.wall_mask[
                    clip(y2 - band, 0, h):clip(y2 + band + 1, 0, h),
                    clip(x1, 0, w):clip(x2, 0, w),
                ]
                left_slice = self.wall_mask[
                    clip(y1, 0, h):clip(y2, 0, h),
                    clip(x1 - band, 0, w):clip(x1 + band + 1, 0, w),
                ]
                right_slice = self.wall_mask[
                    clip(y1, 0, h):clip(y2, 0, h),
                    clip(x2 - band, 0, w):clip(x2 + band + 1, 0, w),
                ]

                walls = {
                    "bottom": is_wall(bottom_slice),
                    "top": is_wall(top_slice),
                    "left": is_wall(left_slice),
                    "right": is_wall(right_slice),
                }

                label = f"{string.ascii_uppercase[r]}{c + 1}"
                grid_walls[label] = walls

        return grid_walls

    def print_ascii_grid_walls(
        self,
        grid_walls: dict[str, dict[str, bool]],
        n_rows: int,
        n_cols: int,
    ) -> None:
        """
        Print an ASCII preview of the maze using the wall dictionary.
        """
        import string

        for r in reversed(range(n_rows)):
            row_str = ""
            for c in range(n_cols):
                label = f"{string.ascii_uppercase[r]}{c + 1}"
                row_str += " --- " if grid_walls[label]["top"] else "     "
            print(row_str)

            side_str = ""
            for c in range(n_cols):
                label = f"{string.ascii_uppercase[r]}{c + 1}"
                left = "|" if grid_walls[label]["left"] else " "
                side_str += f"{left} {label} "

            last_label = f"{string.ascii_uppercase[r]}{n_cols}"
            if grid_walls[last_label]["right"]:
                side_str += "|"

            print(side_str)

        bottom_row = ""
        for c in range(n_cols):
            label = f"{string.ascii_uppercase[0]}{c + 1}"
            bottom_row += " --- " if grid_walls[label]["bottom"] else "     "
        print(bottom_row)