from __future__ import annotations

import string

from vision.maze_solver import MazeSolver


def solve_from_frame(
    frame,
    start_cell: str,
    end_cell: str,
) -> list[str] | None:
    if frame.n_rows <= 0 or frame.n_cols <= 0:
        return None
    if start_cell not in frame.grid_walls or end_cell not in frame.grid_walls:
        return None

    solver = MazeSolver()
    blocked_cells = obstacle_cells_from_frame(
        frame,
        ignored_cells={start_cell, end_cell},
    )

    if blocked_cells:
        obstacle_aware_path = solver.shortest_path(
            grid_walls=frame.grid_walls,
            start_cell=start_cell,
            end_cell=end_cell,
            n_rows=frame.n_rows,
            n_cols=frame.n_cols,
            blocked_cells=blocked_cells,
        )
        if obstacle_aware_path is not None:
            return obstacle_aware_path

    return solver.shortest_path(
        grid_walls=frame.grid_walls,
        start_cell=start_cell,
        end_cell=end_cell,
        n_rows=frame.n_rows,
        n_cols=frame.n_cols,
    )


def obstacle_cells_from_frame(
    frame,
    ignored_cells: set[str] | None = None,
) -> set[str]:
    ignored_cells = ignored_cells or set()
    blocked_cells: set[str] = set()

    for obstacle in getattr(frame, "obstacles", []):
        cell = obstacle_cell(
            obstacle,
            x_lines=frame.x_lines,
            y_lines=frame.y_lines,
        )
        if cell is not None and cell not in ignored_cells:
            blocked_cells.add(cell)

    return blocked_cells


def obstacle_cell(
    obstacle: tuple[int, int, int, int],
    x_lines: list[int],
    y_lines: list[int],
) -> str | None:
    x1, y1, x2, y2 = obstacle
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0

    col = _line_interval_index(center_x, x_lines)
    row = _line_interval_index(center_y, y_lines)
    if row is None or col is None:
        return None
    if row >= len(string.ascii_uppercase):
        return None

    return f"{string.ascii_uppercase[row]}{col + 1}"


def _line_interval_index(value: float, lines: list[int]) -> int | None:
    for index in range(len(lines) - 1):
        if lines[index] <= value < lines[index + 1]:
            return index
    return None
