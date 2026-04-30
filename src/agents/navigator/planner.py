from __future__ import annotations

from pathfinding.pathfinding import solve_from_frame


class PathPlanner:

    def plan(
        self,
        frame,
        start_cell: str,
        end_cell: str,
    ) -> list[str] | None:
        return solve_from_frame(frame, start_cell, end_cell)