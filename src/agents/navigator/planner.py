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

        for coarse_path in self._candidate_coarse_paths(frame, start_cell, end_cell):
            point_path = self._points_from_coarse_path(
                frame=frame,
                coarse_path=coarse_path,
                start_point=start_point,
                goal_point=goal_point,
            )
            if point_path is not None:
                return self._post_process_point_path(point_path, frame)

        return None

    # Cleans up the point_path so non-corridor cells (cells that ended up with
    # multiple waypoints only because the expanded mini-grid corridor swept
    # them up) collapse to a single centre waypoint. Corridor entry/exit
    # cells (free cells grid-adjacent to a traversed blocked cell on the
    # final path) keep their mini-grid waypoints AND additionally have their
    # cell centre forced into the trail. Blocked cells keep mini-grid as-is.
    def _post_process_point_path(
        self,
        point_path: list[tuple[int, int]],
        frame,
    ) -> list[tuple[int, int]]:
        if not point_path or self.mini_grid_planner is None:
            return point_path

        mp = self.mini_grid_planner
        x_lines = frame.x_lines
        y_lines = frame.y_lines

        point_cells = [mp._point_cell(pt, x_lines, y_lines) for pt in point_path]

        blocked_cells = obstacle_cells_from_frame(frame)
        visited_cells = {c for c in point_cells if c is not None}
        traversed_blocked = blocked_cells & visited_cells
        traversed_blocked_rcs = set()
        for cell in traversed_blocked:
            rc = mp._cell_rc(cell)
            if rc is not None:
                traversed_blocked_rcs.add(rc)

        def is_pink(cell: str) -> bool:
            rc = mp._cell_rc(cell)
            if rc is None:
                return False
            return any(
                abs(rc[0] - br) + abs(rc[1] - bc) == 1
                for br, bc in traversed_blocked_rcs
            )

        new_path: list[tuple[int, int]] = []
        i = 0
        while i < len(point_path):
            cell = point_cells[i]
            if cell is None:
                new_path.append(point_path[i])
                i += 1
                continue

            run_end = i
            while run_end < len(point_path) and point_cells[run_end] == cell:
                run_end += 1
            run = list(point_path[i:run_end])

            bounds = mp._cell_bounds(cell, x_lines, y_lines)
            if bounds is not None:
                center = (
                    (bounds[0] + bounds[2]) // 2,
                    (bounds[1] + bounds[3]) // 2,
                )
            else:
                center = run[len(run) // 2]

            if cell in blocked_cells:
                new_path.extend(run)
            # TEMP TEST: free corridor entry/exit (pink) cells too -- collapse
            # them to a single centre exactly like any other free cell. The
            # original "keep mini-grid + force centre" logic is preserved
            # below for easy re-enable; remove the comments to bring it back.
            #
            # elif is_pink(cell):
            #     if center not in run:
            #         run.append(center)
            #     new_path.extend(run)
            #     logger.info(f"[PLAN-DEBUG] post-process: pink {cell} centre={center}")
            else:
                new_path.append(center)
                if len(run) > 1:
                    kind = "pink" if is_pink(cell) else "free"
                    logger.info(
                        f"[PLAN-DEBUG] post-process: collapsed {kind} {cell} "
                        f"({len(run)} pts -> 1 centre={center})"
                    )

            i = run_end

        return new_path

    def _candidate_coarse_paths(
        self,
        frame,
        start_cell: str,
        end_cell: str,
    ) -> list[list[str]]:
        paths: list[list[str]] = []
        for avoid_obstacles in (False, True):
            path = solve_from_frame(
                frame,
                start_cell,
                end_cell,
                avoid_obstacles=avoid_obstacles,
            )
            if path is not None and path not in paths:
                paths.append(path)
        return paths

    def _points_from_coarse_path(
        self,
        frame,
        coarse_path: list[str],
        start_point: tuple[int, int],
        goal_point: tuple[int, int],
    ) -> list[tuple[int, int]] | None:
        blocked_cells = obstacle_cells_from_frame(frame)
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
                expanded_cells = self._expanded_corridor_cells(frame, corridor_cells)
                if expanded_cells != corridor_cells:
                    mini_points = self.mini_grid_planner.plan_cell_sequence(
                        frame=frame,
                        cells=expanded_cells,
                        start_point=corridor_start,
                        goal_point=corridor_goal,
                    )
            if not mini_points:
                return None

            for point in mini_points:
                if not points or points[-1] != point:
                    points.append(point)

            if coarse_path[after_index] in blocked_cells:
                index = after_index + 1
            else:
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

    def _expanded_corridor_cells(
        self,
        frame,
        corridor_cells: list[str],
        padding: int = 1,
    ) -> list[str]:
        if self.mini_grid_planner is None:
            return corridor_cells

        rcs = [
            self.mini_grid_planner._cell_rc(cell)
            for cell in corridor_cells
        ]
        rcs = [rc for rc in rcs if rc is not None]
        if not rcs:
            return corridor_cells

        min_row = max(0, min(row for row, _ in rcs) - padding)
        max_row = min(frame.n_rows - 1, max(row for row, _ in rcs) + padding)
        min_col = max(0, min(col for _, col in rcs) - padding)
        max_col = min(frame.n_cols - 1, max(col for _, col in rcs) + padding)

        cells = []
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                cell = self.mini_grid_planner._rc_cell(row, col)
                if cell is not None:
                    cells.append(cell)
        return cells

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
