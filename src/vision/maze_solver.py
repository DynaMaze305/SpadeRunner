from __future__ import annotations

import string
import heapq


CARDINAL_DIRECTIONS = (
    (1, 0, "top"),
    (-1, 0, "bottom"),
    (0, -1, "left"),
    (0, 1, "right"),
)

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
        allow_diagonal: bool = True,
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

        # Priority queue used for Dijkstra search. Diagonal moves are longer
        # than straight moves, so plain breadth-first search would underprice them.
        queue = [(0.0, start_cell)]

        # Store where each cell was reached from, used later to rebuild the path
        parent = {start_cell: None}
        distance = {start_cell: 0.0}

        # Explore the maze layer by layer until the end cell is reached
        while queue:
            current_distance, current = heapq.heappop(queue)

            if current_distance > distance[current]:
                continue

            # Stop searching once the destination is found
            if current == end_cell:
                break

            # Convert current cell label into row/column coordinates
            r, c = label_to_rc(current)

            # Get wall information for the current cell
            walls = grid_walls[current]

            # Add reachable neighbors to the search queue
            for neighbor, move_cost in self._neighbors(
                r,
                c,
                walls,
                grid_walls,
                rc_to_label,
                in_bounds,
                blocked_cells,
                allow_diagonal,
            ):
                if neighbor in blocked_cells:
                    continue
                new_distance = current_distance + move_cost
                if new_distance < distance.get(neighbor, float("inf")):
                    distance[neighbor] = new_distance
                    parent[neighbor] = current
                    heapq.heappush(queue, (new_distance, neighbor))

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

    def _neighbors(
        self,
        r: int,
        c: int,
        walls: dict[str, bool],
        grid_walls: dict[str, dict[str, bool]],
        rc_to_label,
        in_bounds,
        blocked_cells: set[str],
        allow_diagonal: bool,
    ) -> list[tuple[str, float]]:
        neighbors: list[tuple[str, float]] = []

        for dr, dc, wall in CARDINAL_DIRECTIONS:
            nr, nc = r + dr, c + dc
            if not walls[wall] and in_bounds(nr, nc):
                neighbors.append((rc_to_label(nr, nc), 1.0))

        if not allow_diagonal:
            return neighbors

        for vertical_dr, vertical_dc, vertical_wall in CARDINAL_DIRECTIONS[:2]:
            for horizontal_dr, horizontal_dc, horizontal_wall in CARDINAL_DIRECTIONS[2:]:
                diagonal_r = r + vertical_dr + horizontal_dr
                diagonal_c = c + vertical_dc + horizontal_dc

                if not in_bounds(diagonal_r, diagonal_c):
                    continue

                diagonal_cell = rc_to_label(diagonal_r, diagonal_c)
                vertical_cell = rc_to_label(r + vertical_dr, c + vertical_dc)
                horizontal_cell = rc_to_label(r + horizontal_dr, c + horizontal_dc)

                if (
                    diagonal_cell in blocked_cells
                    or vertical_cell in blocked_cells
                    or horizontal_cell in blocked_cells
                ):
                    continue

                if self._diagonal_is_open(
                    walls,
                    grid_walls,
                    vertical_cell,
                    horizontal_cell,
                    vertical_wall,
                    horizontal_wall,
                ):
                    neighbors.append((diagonal_cell, 2 ** 0.5))

        return neighbors

    @staticmethod
    def _diagonal_is_open(
        current_walls: dict[str, bool],
        grid_walls: dict[str, dict[str, bool]],
        vertical_cell: str,
        horizontal_cell: str,
        vertical_wall: str,
        horizontal_wall: str,
    ) -> bool:
        if current_walls[vertical_wall] or current_walls[horizontal_wall]:
            return False

        vertical_walls = grid_walls.get(vertical_cell)
        horizontal_walls = grid_walls.get(horizontal_cell)
        if vertical_walls is None or horizontal_walls is None:
            return False

        via_vertical = not vertical_walls[horizontal_wall]
        via_horizontal = not horizontal_walls[vertical_wall]

        return via_vertical and via_horizontal
