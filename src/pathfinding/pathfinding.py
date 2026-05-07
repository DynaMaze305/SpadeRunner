from __future__ import annotations

import string

from vision.maze_solver import MazeSolver


# Cells the planner must never route through and the renderer paints over in a
# dark fill. Treated as "outside the playable area" - not displayed as blocked,
# not used for obstacle accounting, just unreachable.
OUT_OF_GAME_CELLS: frozenset[str] = frozenset({"A5", "A6", "A7"})


def _baseline_blocked(start_cell: str, end_cell: str) -> set[str]:
    blocked = set(OUT_OF_GAME_CELLS)
    blocked.discard(start_cell)
    blocked.discard(end_cell)
    return blocked


def solve_from_frame(
    frame,
    start_cell: str,
    end_cell: str,
    avoid_obstacles: bool = True,
    extra_blocked_cells: set[str] | None = None,
) -> list[str] | None:
    if frame.n_rows <= 0 or frame.n_cols <= 0:
        return None
    if start_cell not in frame.grid_walls or end_cell not in frame.grid_walls:
        return None

    solver = MazeSolver()

    # Hard-blocked: cells the solver MUST treat like walls regardless of the
    # avoid_obstacles flag. OUT_OF_GAME baseline plus per-step extras
    # supplied by the caller (e.g. detected enemy robots). Even the fallback
    # orthogonal-tolerant solve refuses to step on these.
    hard_blocked = _baseline_blocked(start_cell, end_cell)
    if extra_blocked_cells:
        hard_blocked = hard_blocked | (
            set(extra_blocked_cells) - {start_cell, end_cell}
        )

    # Soft-blocked: real obstacles. Avoided when avoid_obstacles=True, but
    # the fallback path is allowed to pass through them orthogonally if no
    # obstacle-free route exists. Diagonal corner-cuts always reject them.
    obstacle_blocked = obstacle_cells_from_frame(
        frame,
        ignored_cells={start_cell, end_cell},
    )

    if avoid_obstacles:
        full_blocked = hard_blocked | obstacle_blocked
        if full_blocked:
            obstacle_aware_path = solver.shortest_path(
                grid_walls=frame.grid_walls,
                start_cell=start_cell,
                end_cell=end_cell,
                n_rows=frame.n_rows,
                n_cols=frame.n_cols,
                blocked_cells=full_blocked,
            )
            if obstacle_aware_path is not None:
                return obstacle_aware_path

    # Fallback: orthogonal A* tolerates SOFT-blocked cells (so the planner
    # can still find SOMETHING when there's no obstacle-free route), but
    # hard-blocked cells (OUT_OF_GAME, enemies) stay treated as walls.
    # The diagonal corner-cut check still rejects any step where any of the
    # 4 cells touches a soft-blocked obstacle.
    return solver.shortest_path(
        grid_walls=frame.grid_walls,
        start_cell=start_cell,
        end_cell=end_cell,
        n_rows=frame.n_rows,
        n_cols=frame.n_cols,
        blocked_cells=hard_blocked,
        diagonal_block_cells=hard_blocked | obstacle_blocked,
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
