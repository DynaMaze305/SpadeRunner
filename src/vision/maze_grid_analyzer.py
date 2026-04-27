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

    def build_grid_walls(
        self,
        wall_clean: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
        threshold: int = 100,
    ) -> dict[str, dict[str, bool]]:
        # Compute maze dimensions from detected grid lines
        n_rows, n_cols = self.get_grid_size(x_lines, y_lines)

        # Stores wall information for each cell
        grid_walls = {}

        for r in range(n_rows):
            for c in range(n_cols):
                # Get the pixel boundaries of the current cell
                x1, x2 = x_lines[c], x_lines[c + 1]
                y1, y2 = y_lines[r], y_lines[r + 1]

                # Check each side of the current cell for wall pixels
                walls = {
                    "bottom": self.is_wall(wall_clean[y1, x1:x2], threshold),
                    "top": self.is_wall(wall_clean[y2, x1:x2], threshold),
                    "left": self.is_wall(wall_clean[y1:y2, x1], threshold),
                    "right": self.is_wall(wall_clean[y1:y2, x2], threshold),
                }

                # Create a readable cell label like A1, A2, B1, etc.
                label = f"{string.ascii_uppercase[r]}{c + 1}"

                # Save wall information for this cell
                grid_walls[label] = walls

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