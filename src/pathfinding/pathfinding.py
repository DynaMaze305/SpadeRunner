from __future__ import annotations

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

    return MazeSolver().shortest_path(
        grid_walls=frame.grid_walls,
        start_cell=start_cell,
        end_cell=end_cell,
        n_rows=frame.n_rows,
        n_cols=frame.n_cols,
    )