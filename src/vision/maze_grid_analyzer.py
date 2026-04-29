from __future__ import annotations

import string
import numpy as np


# Analyzes detected grid lines and converts the maze image into wall data
class MazeGridAnalyzer:

    def get_grid_size(
        self,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int]:
        # Number of columns is the number of spaces between vertical grid lines
        n_cols = len(x_lines) - 1

        # Number of rows is the number of spaces between horizontal grid lines
        n_rows = len(y_lines) - 1

        return n_rows, n_cols

    def is_wall(
        self,
        pixel_slice: np.ndarray,
        threshold: int,
    ) -> bool:
        # Check if the average pixel intensity is high enough to be considered a wall
        return np.mean(pixel_slice) > threshold

    @staticmethod
    def _band_is_wall(
        band: np.ndarray,
        axis: int,
        threshold: int,
    ) -> bool:
        # Empty slice (band ran off the image edge) -> no wall
        if band.size == 0:
            return False
        # Collapse perpendicular to the line: max picks up any wall pixel within
        # the band, even if the actual wall is slightly off the detected grid line.
        # Then average along the line so isolated noise specks don't fire.
        collapsed = np.max(band, axis=axis)
        return float(np.mean(collapsed)) > threshold

    def build_grid_walls(
        self,
        wall_clean: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
        threshold: int = 100,
        band: int = 2,
    ) -> dict[str, dict[str, bool]]:
        # Compute maze dimensions from detected grid lines
        n_rows, n_cols = self.get_grid_size(x_lines, y_lines)
        h, w = wall_clean.shape

        # Stores wall information for each cell
        grid_walls = {}

        for r in range(n_rows):
            for c in range(n_cols):
                # Get the pixel boundaries of the current cell
                x1, x2 = x_lines[c], x_lines[c + 1]
                y1, y2 = y_lines[r], y_lines[r + 1]

                # Band-sample +/- `band` pixels around each grid line so walls
                # that are slightly off the detected line are still caught.
                horiz_top = wall_clean[
                    max(0, y1 - band): min(h, y1 + band + 1), x1:x2
                ]
                horiz_bot = wall_clean[
                    max(0, y2 - band): min(h, y2 + band + 1), x1:x2
                ]
                vert_left = wall_clean[
                    y1:y2, max(0, x1 - band): min(w, x1 + band + 1)
                ]
                vert_right = wall_clean[
                    y1:y2, max(0, x2 - band): min(w, x2 + band + 1)
                ]

                walls = {
                    "bottom": self._band_is_wall(horiz_top, axis=0, threshold=threshold),
                    "top": self._band_is_wall(horiz_bot, axis=0, threshold=threshold),
                    "left": self._band_is_wall(vert_left, axis=1, threshold=threshold),
                    "right": self._band_is_wall(vert_right, axis=1, threshold=threshold),
                }

                # Create a readable cell label like A1, A2, B1, etc.
                label = f"{string.ascii_uppercase[r]}{c + 1}"

                # Save wall information for this cell
                grid_walls[label] = walls

        # The maze always has a closed outer border, so force every perimeter
        # cell-edge to True regardless of detection. Note the "bottom" / "top"
        # keys come from MazeGridAnalyzer's math-y convention (image-y is flipped):
        # outer image-top = walls["bottom"] of row 0; outer image-bottom = walls["top"] of last row.
        if n_rows > 0 and n_cols > 0:
            top_row = string.ascii_uppercase[0]
            bottom_row = string.ascii_uppercase[n_rows - 1]

            for r in range(n_rows):
                row = string.ascii_uppercase[r]
                grid_walls[f"{row}1"]["left"] = True
                grid_walls[f"{row}{n_cols}"]["right"] = True

            for c in range(n_cols):
                grid_walls[f"{top_row}{c + 1}"]["bottom"] = True
                grid_walls[f"{bottom_row}{c + 1}"]["top"] = True

        return grid_walls

    def print_maze(
        self,
        grid_walls: dict[str, dict[str, bool]],
        n_rows: int,
        n_cols: int,
    ) -> None:
        # Print rows from top to bottom so the maze matches visual orientation
        for r in reversed(range(n_rows)):

            # Print the top walls of the current row
            row_str = ""
            for c in range(n_cols):
                label = f"{string.ascii_uppercase[r]}{c + 1}"
                row_str += " ─── " if grid_walls[label]["top"] else "     "

            print(row_str)

            # Print left/right walls and cell labels
            side_str = ""
            for c in range(n_cols):
                label = f"{string.ascii_uppercase[r]}{c + 1}"

                # Add a vertical wall if the left side of the cell is blocked
                left = "│" if grid_walls[label]["left"] else " "

                # Print the cell label inside the cell area
                side_str += f"{left} {label:<3}"

            # Add the right boundary of the last cell in the row if present
            last_label = f"{string.ascii_uppercase[r]}{n_cols}"
            if grid_walls[last_label]["right"]:
                side_str += "│"

            print(side_str)

        # Print the bottom walls of the lowest row
        bottom_row = ""
        for c in range(n_cols):
            label = f"{string.ascii_uppercase[0]}{c + 1}"
            bottom_row += " ─── " if grid_walls[label]["bottom"] else "     "

        print(bottom_row)