from __future__ import annotations

from pathfinding.mini_grid_planner import MiniGridPlanner
from pathfinding.pathfinding import obstacle_cells_from_frame, solve_from_frame


# Thin wrapper around solve_from_frame; here so the orchestrator depends on
# a small interface it can swap in tests rather than importing pathfinding directly.
class PathPlanner:
    def __init__(
        self,
        mini_grid_planner: MiniGridPlanner | None = None,
    ) -> None:
        self.mini_grid_planner = mini_grid_planner

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
            ignored_cells={coarse_path[0], coarse_path[-1]},
        )
        points: list[tuple[int, int]] = []
        protected_points: set[tuple[int, int]] = set()
        index = 0

        while index < len(coarse_path):
            cell = coarse_path[index]
            if cell not in blocked_cells:
                point = self._route_point_for_cell(frame, coarse_path, index, start_point, goal_point)
                if not points or points[-1] != point:
                    points.append(point)
                protected_points.add(point)
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
            corridor_goal = self._blocked_corridor_goal(
                frame=frame,
                coarse_path=coarse_path,
                blocked_cells=blocked_cells,
                blocked_end_index=after_index - 1,
                after_index=after_index,
                goal_point=goal_point,
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

            index = after_index

        if not blocked_cells:
            return points

        return self._simplify_axis_aligned_points(points, protected_points)

    def _blocked_corridor_goal(
        self,
        frame,
        coarse_path: list[str],
        blocked_cells: set[str],
        blocked_end_index: int,
        after_index: int,
        goal_point: tuple[int, int],
    ) -> tuple[int, int]:
        if (
            self.mini_grid_planner is None
            or after_index >= len(coarse_path)
            or after_index == len(coarse_path) - 1
            or coarse_path[after_index] in blocked_cells
            or blocked_end_index < 0
        ):
            if after_index == len(coarse_path) - 1:
                return goal_point
            return self._cell_center(frame, coarse_path[after_index])

        from_cell = coarse_path[blocked_end_index]
        to_cell = coarse_path[after_index]
        entry = self.mini_grid_planner._entry_mini_cell(from_cell, to_cell)
        bounds = self.mini_grid_planner._cell_bounds(to_cell, frame.x_lines, frame.y_lines)
        if entry is None or bounds is None:
            return self._cell_center(frame, to_cell)
        return self.mini_grid_planner._mini_cell_center(bounds, entry)

    @staticmethod
    def _simplify_axis_aligned_points(
        points: list[tuple[int, int]],
        protected_points: set[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]]:
        if len(points) <= 2:
            return points

        protected_points = protected_points or set()
        simplified = [points[0]]
        last_kept_index = 0
        for index, point in enumerate(points[1:-1], start=1):
            if point in protected_points:
                simplified.append(point)
                last_kept_index = index
                continue

            previous = simplified[-1]
            next_point = points[index + 1]
            if (
                index - last_kept_index == 1
                and (
                    previous[0] == point[0] == next_point[0]
                    or previous[1] == point[1] == next_point[1]
                )
            ):
                continue
            simplified.append(point)
            last_kept_index = index
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
        return self._cell_center(frame, coarse_path[index])

    def _cell_center(self, frame, cell: str) -> tuple[int, int]:
        row = ord(cell[0].upper()) - ord("A")
        col = int(cell[1:]) - 1
        x_left = frame.x_lines[col]
        x_right = frame.x_lines[col + 1]
        y_top = frame.y_lines[row]
        y_bottom = frame.y_lines[row + 1]
        return ((x_left + x_right) // 2, (y_top + y_bottom) // 2)
