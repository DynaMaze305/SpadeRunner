from __future__ import annotations

import string
from collections import deque


# Solves a maze represented as cell wall data
class MazeSolver:

    def shortest_path(
        self,
        grid_walls: dict[str, dict[str, bool]],
        start_cell: str,
        end_cell: str,
        n_rows: int,
        n_cols: int,
        blocked_cells: set[str] | None = None,
    ) -> list[str] | None:
        # Create row labels based on the maze height: A, B, C, ...
        row_letters = list(string.ascii_uppercase[:n_rows])

        def label_to_rc(label: str) -> tuple[int, int]:
            # Convert a cell label like "B3" into row and column indexes
            row_letter = label[0]
            col = int(label[1:]) - 1
            row = row_letters.index(row_letter)
            return row, col

        def rc_to_label(r: int, c: int) -> str:
            # Convert row and column indexes back into a cell label like "B3"
            return f"{row_letters[r]}{c + 1}"

        def in_bounds(r: int, c: int) -> bool:
            # Check if a row/column position is inside the maze
            return 0 <= r < n_rows and 0 <= c < n_cols

        # Stop early if the start or end cell does not exist in the maze
        if start_cell not in grid_walls or end_cell not in grid_walls:
            return None

        blocked_cells = blocked_cells or set()
        if start_cell in blocked_cells or end_cell in blocked_cells:
            return None

        # Queue used for breadth-first search
        queue = deque([start_cell])

        # Keep track of cells that have already been explored
        visited = {start_cell}

        # Store where each cell was reached from, used later to rebuild the path
        parent = {start_cell: None}

        # Explore the maze layer by layer until the end cell is reached
        while queue:
            current = queue.popleft()

            # Stop searching once the destination is found
            if current == end_cell:
                break

            # Convert current cell label into row/column coordinates
            r, c = label_to_rc(current)

            # Get wall information for the current cell
            walls = grid_walls[current]

            # List of reachable neighboring cells
            neighbors = []

            # Move upward if there is no top wall
            if not walls["top"]:
                nr, nc = r + 1, c
                if in_bounds(nr, nc):
                    neighbors.append(rc_to_label(nr, nc))

            # Move downward if there is no bottom wall
            if not walls["bottom"]:
                nr, nc = r - 1, c
                if in_bounds(nr, nc):
                    neighbors.append(rc_to_label(nr, nc))

            # Move left if there is no left wall
            if not walls["left"]:
                nr, nc = r, c - 1
                if in_bounds(nr, nc):
                    neighbors.append(rc_to_label(nr, nc))

            # Move right if there is no right wall
            if not walls["right"]:
                nr, nc = r, c + 1
                if in_bounds(nr, nc):
                    neighbors.append(rc_to_label(nr, nc))

            # Add unvisited reachable neighbors to the search queue
            for neighbor in neighbors:
                if neighbor in blocked_cells:
                    continue
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = current
                    queue.append(neighbor)

        # If the end cell was never reached, no valid path exists
        if end_cell not in parent:
            return None

        # Rebuild the path by walking backward from the end cell to the start cell
        path = []
        current = end_cell

        while current is not None:
            path.append(current)
            current = parent[current]

        # Reverse the path so it goes from start to end
        path.reverse()

        return path
