from __future__ import annotations

from pathfinding.pathfinding import solve_from_frame

Point = tuple[int, int]


class PathPlanner:

    def plan(
        self,
        frame,
        start_cell: str,
        end_cell: str,
    ) -> list[Point] | None:
        return solve_from_frame(frame, start_cell, end_cell)