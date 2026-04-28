from __future__ import annotations

from pathfinding.pathfinding import solve_from_frame


# Thin wrapper around solve_from_frame; here so the orchestrator depends on
# a small interface it can swap in tests rather than importing pathfinding directly.
class PathPlanner:

    def plan(
        self,
        frame,
        start_cell: str,
        end_cell: str,
    ) -> list[str] | None:
        return solve_from_frame(frame, start_cell, end_cell)
