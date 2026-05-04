from __future__ import annotations

import math

from pathfinding.mini_grid_planner import MiniGridPlanner
from pathfinding.pathfinding import obstacle_cells_from_frame, solve_from_frame


# Thin wrapper around solve_from_frame; here so the orchestrator depends on
# a small interface it can swap in tests rather than importing pathfinding directly.
class PathPlanner:
    def __init__(
        self,
        mini_grid_planner: MiniGridPlanner | None = None,
        safe_cell_inset_px: int = 0,
        safe_cell_inset_start_factor: float = 0.45,
    ) -> None:
        self.mini_grid_planner = mini_grid_planner
        self.safe_cell_inset_px = safe_cell_inset_px
        self.safe_cell_inset_start_factor = safe_cell_inset_start_factor

    def plan(
        self,
        frame,
        start_cell: str,
        end_cell: str,
    ) -> list[str] | None:
        return solve_from_frame(frame, start_cell, end_cell)

    def plan_points(
        self,
        frame,
        start_cell: str,
        end_cell: str,
        start_point: tuple[int, int],
        goal_point: tuple[int, int],
    ) -> list[tuple[int, int]] | None:
        if self.mini_grid_planner is None:
            return None

        coarse_path = self.plan(frame, start_cell, end_cell)
        if coarse_path is None:
            return None

        return self._points_from_coarse_path(
            frame=frame,
            coarse_path=coarse_path,
            start_point=start_point,
            goal_point=goal_point,
        )

    def _points_from_coarse_path(
        self,
        frame,
        coarse_path: list[str],
        start_point: tuple[int, int],
        goal_point: tuple[int, int],
    ) -> list[tuple[int, int]] | None:
        blocked_cells = obstacle_cells_from_frame(
            frame,
            ignored_cells={coarse_path[-1]},
        )
        points: list[tuple[int, int]] = []
        index = 0

        while index < len(coarse_path):
            cell = coarse_path[index]
            if cell not in blocked_cells:
                point = self._route_point_for_cell(frame, coarse_path, index, start_point, goal_point)
                if not points or points[-1] != point:
                    points.append(point)
                index += 1
                continue

            before_index = max(0, index - 1)
            after_index = index
            while after_index < len(coarse_path) and coarse_path[after_index] in blocked_cells:
                after_index += 1
            if after_index >= len(coarse_path):
                after_index = len(coarse_path) - 1

            corridor_cells = coarse_path[before_index:after_index + 1]
            corridor_start = self._route_point_for_cell(
                frame, coarse_path, before_index, start_point, goal_point,
            )
            corridor_goal = self._route_point_for_cell(
                frame, coarse_path, after_index, start_point, goal_point,
            )
            mini_points = self.mini_grid_planner.plan_cell_sequence(
                frame=frame,
                cells=corridor_cells,
                start_point=corridor_start,
                goal_point=corridor_goal,
            )
            if not mini_points:
                return None

            for point in mini_points:
                if not points or points[-1] != point:
                    points.append(point)

            index = after_index + 1

        return self._simplify_axis_aligned_points(points)

    @staticmethod
    def _simplify_axis_aligned_points(
        points: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if len(points) <= 2:
            return points

        simplified = [points[0]]
        for index, point in enumerate(points[1:-1], start=1):
            previous = simplified[-1]
            next_point = points[index + 1]
            if (
                previous[0] == point[0] == next_point[0]
                or previous[1] == point[1] == next_point[1]
            ):
                continue
            simplified.append(point)
        simplified.append(points[-1])
        return simplified

    def _route_point_for_cell(
        self,
        frame,
        coarse_path: list[str],
        index: int,
        start_point: tuple[int, int],
        goal_point: tuple[int, int],
    ) -> tuple[int, int]:
        if index == 0:
            return start_point
        if index == len(coarse_path) - 1:
            return goal_point
        return self._safe_cell_center(frame, coarse_path[index])

    def _safe_cell_center(self, frame, cell: str) -> tuple[int, int]:
        row = ord(cell[0].upper()) - ord("A")
        col = int(cell[1:]) - 1
        x_left = frame.x_lines[col]
        x_right = frame.x_lines[col + 1]
        y_top = frame.y_lines[row]
        y_bottom = frame.y_lines[row + 1]
        cx = (x_left + x_right) // 2
        cy = (y_top + y_bottom) // 2

        walls = frame.grid_walls.get(cell, {})
        inset = self._dynamic_safe_cell_inset(cx, cy, x_left, y_top, x_right, y_bottom, frame)
        if (
            (col == 0 and walls.get("left"))
            or (col == len(frame.x_lines) - 2 and walls.get("right"))
            or (row == 0 and walls.get("bottom"))
            or (row == len(frame.y_lines) - 2 and walls.get("top"))
        ):
            cell_limit = max(0, min(x_right - x_left, y_bottom - y_top) // 3)
            inset = min(max(inset, self.safe_cell_inset_px), cell_limit)

        if inset == 0:
            return (cx, cy)

        if walls.get("left"):
            cx += inset
        if walls.get("right"):
            cx -= inset
        if walls.get("bottom"):
            cy += inset
        if walls.get("top"):
            cy -= inset

        return (
            min(max(cx, x_left + inset), x_right - inset),
            min(max(cy, y_top + inset), y_bottom - inset),
        )

    def _dynamic_safe_cell_inset(
        self,
        cx: int,
        cy: int,
        x_left: int,
        y_top: int,
        x_right: int,
        y_bottom: int,
        frame,
    ) -> int:
        max_inset = max(0, self.safe_cell_inset_px)
        if max_inset == 0:
            return 0

        maze_x1 = frame.x_lines[0]
        maze_x2 = frame.x_lines[-1]
        maze_y1 = frame.y_lines[0]
        maze_y2 = frame.y_lines[-1]
        maze_cx = (maze_x1 + maze_x2) / 2.0
        maze_cy = (maze_y1 + maze_y2) / 2.0
        max_dist = math.hypot(maze_x2 - maze_cx, maze_y2 - maze_cy)
        if max_dist <= 0:
            return 0

        edge_factor = math.hypot(cx - maze_cx, cy - maze_cy) / max_dist
        start = min(max(self.safe_cell_inset_start_factor, 0.0), 0.99)
        if edge_factor <= start:
            return 0

        ramp = (edge_factor - start) / (1.0 - start)
        cell_limit = max(0, min(x_right - x_left, y_bottom - y_top) // 3)
        return min(int(round(max_inset * ramp)), cell_limit)
