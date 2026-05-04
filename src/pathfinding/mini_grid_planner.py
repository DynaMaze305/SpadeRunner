from __future__ import annotations

from collections import deque
import heapq
import string


Point = tuple[int, int]
Box = tuple[int, int, int, int]
MiniCell = tuple[int, int]
Node = tuple[str, int, int]


class MiniGridPlanner:
    def __init__(
        self,
        divisions: int,
        obstacle_margin_px: int = 0,
        robot_margin_px: int = 0,
    ) -> None:
        self.divisions = divisions
        self.obstacle_margin_px = obstacle_margin_px
        self.robot_margin_px = robot_margin_px

    def plan_blocked_cell(
        self,
        frame,
        current_cell: str,
        blocked_cell: str,
        exit_cell: str | None = None,
    ) -> list[Point] | None:
        bounds = self._cell_bounds(blocked_cell, frame.x_lines, frame.y_lines)
        if bounds is None:
            return None

        entry = self._entry_mini_cell(current_cell, blocked_cell)
        if entry is None:
            return None

        exit_mini = self._exit_mini_cell(blocked_cell, exit_cell)
        if exit_mini is None:
            exit_mini = (self.divisions // 2, self.divisions // 2)

        blocked = self._blocked_mini_cells(bounds, frame.obstacles)

        mini_path = self._shortest_path(entry, exit_mini, blocked)
        if mini_path is None:
            return None

        return [self._mini_cell_center(bounds, mini) for mini in mini_path]

    def plan_cell_sequence(
        self,
        frame,
        cells: list[str],
        start_point: Point,
        goal_point: Point,
    ) -> list[Point] | None:
        if len(cells) < 2:
            return None

        cell_set = set(cells)
        bounds_by_cell = {
            cell: self._cell_bounds(cell, frame.x_lines, frame.y_lines)
            for cell in cells
        }
        if any(bounds is None for bounds in bounds_by_cell.values()):
            return None

        start_cell = self._point_cell(start_point, frame.x_lines, frame.y_lines)
        goal_cell = self._point_cell(goal_point, frame.x_lines, frame.y_lines)
        if start_cell not in cell_set or goal_cell not in cell_set:
            return None

        start_mini = self._point_mini_cell(bounds_by_cell[start_cell], start_point)
        goal_mini = self._point_mini_cell(bounds_by_cell[goal_cell], goal_point)
        if start_mini is None or goal_mini is None:
            return None

        start = (start_cell, start_mini[0], start_mini[1])
        goal = (goal_cell, goal_mini[0], goal_mini[1])
        blocked = self._blocked_nodes(bounds_by_cell, frame.obstacles, frame=frame)

        if start in blocked:
            start = self._nearest_unblocked_node(start, blocked, cell_set, frame)
            if start is None:
                return None

        node_path = self._shortest_node_path(start, goal, blocked, cell_set, frame)
        if node_path is None:
            return None

        return [
            self._mini_cell_center(bounds_by_cell[cell], (row, col))
            for cell, row, col in node_path
        ]

    def plan_frame(
        self,
        frame,
        start_point: Point,
        goal_point: Point,
    ) -> list[Point] | None:
        if frame.n_rows <= 0 or frame.n_cols <= 0:
            return None

        cells = [
            self._rc_cell(row, col)
            for row in range(frame.n_rows)
            for col in range(frame.n_cols)
        ]
        cells = [cell for cell in cells if cell is not None]
        return self.plan_cell_sequence(
            frame=frame,
            cells=cells,
            start_point=start_point,
            goal_point=goal_point,
        )

    def _blocked_mini_cells(
        self,
        bounds: Box,
        obstacles: list[Box],
    ) -> set[MiniCell]:
        blocked: set[MiniCell] = set()
        relevant_obstacles = []
        for obstacle in obstacles:
            inflated = self._inflate_box(obstacle)
            if self._boxes_intersect(bounds, inflated):
                relevant_obstacles.append(inflated)
        if not relevant_obstacles:
            return blocked

        for row in range(self.divisions):
            for col in range(self.divisions):
                mini_bounds = self._mini_cell_bounds(bounds, (row, col))
                if any(self._boxes_intersect(mini_bounds, obs) for obs in relevant_obstacles):
                    blocked.add((row, col))

        return blocked

    def _shortest_path(
        self,
        start: MiniCell,
        goal: MiniCell,
        blocked: set[MiniCell],
    ) -> list[MiniCell] | None:
        if start in blocked or goal in blocked:
            return None

        clearance_distances = self._mini_clearance_distances(blocked)
        queue: list[tuple[int, int, int, MiniCell]] = [(-10**9, 0, 0, start)]
        sequence = 1
        previous: dict[MiniCell, MiniCell | None] = {start: None}
        best_score: dict[MiniCell, tuple[int, int]] = {start: (10**9, 0)}

        while queue:
            negative_clearance, cost, _, current = heapq.heappop(queue)
            clearance = -negative_clearance
            if (clearance, cost) != best_score[current]:
                continue
            if current == goal:
                break

            for neighbor in self._neighbors(current):
                if neighbor in blocked:
                    continue
                next_clearance = min(
                    clearance,
                    clearance_distances.get(neighbor, self.divisions + 1),
                )
                next_cost = cost + 1 + self._preferred_row_penalty(neighbor[0])
                best_clearance, best_cost = best_score.get(neighbor, (-1, 10**9))
                if (
                    next_clearance < best_clearance
                    or (
                        next_clearance == best_clearance
                        and next_cost >= best_cost
                    )
                ):
                    continue
                best_score[neighbor] = (next_clearance, next_cost)
                previous[neighbor] = current
                heapq.heappush(queue, (-next_clearance, next_cost, sequence, neighbor))
                sequence += 1

        if goal not in previous:
            return None

        path = []
        current: MiniCell | None = goal
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()
        return path

    def _nearest_unblocked_node(
        self,
        start: Node,
        blocked: set[Node],
        allowed_cells: set[str],
        frame,
    ) -> Node | None:
        queue = deque([start])
        seen = {start}

        while queue:
            current = queue.popleft()
            if current not in blocked:
                return current

            for neighbor in self._node_neighbors(current, allowed_cells, frame, blocked=set()):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)

        return None

    def _neighbors(self, cell: MiniCell) -> list[MiniCell]:
        row, col = cell
        neighbors = []
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nr = row + dr
            nc = col + dc
            if 0 <= nr < self.divisions and 0 <= nc < self.divisions:
                neighbors.append((nr, nc))
        return neighbors

    def _blocked_nodes(
        self,
        bounds_by_cell: dict[str, Box],
        obstacles: list[Box],
        frame=None,
    ) -> set[Node]:
        blocked: set[Node] = set()
        for cell, bounds in bounds_by_cell.items():
            for row, col in self._blocked_mini_cells(bounds, obstacles):
                blocked.add((cell, row, col))
        return blocked

    def _shortest_node_path(
        self,
        start: Node,
        goal: Node,
        blocked: set[Node],
        allowed_cells: set[str],
        frame,
    ) -> list[Node] | None:
        if start in blocked or goal in blocked:
            return None

        clearance_distances = self._node_clearance_distances(allowed_cells, blocked)
        queue: list[tuple[int, int, int, Node]] = [(-10**9, 0, 0, start)]
        sequence = 1
        previous: dict[Node, Node | None] = {start: None}
        best_score: dict[Node, tuple[int, int]] = {start: (10**9, 0)}

        while queue:
            negative_clearance, cost, _, current = heapq.heappop(queue)
            clearance = -negative_clearance
            if (clearance, cost) != best_score[current]:
                continue
            if current == goal:
                break

            for neighbor in self._node_neighbors(current, allowed_cells, frame, blocked):
                if neighbor in blocked:
                    continue
                next_clearance = min(
                    clearance,
                    clearance_distances.get(neighbor, self.divisions + 1),
                )
                next_cost = cost + 1 + self._preferred_row_penalty(neighbor[1])
                best_clearance, best_cost = best_score.get(neighbor, (-1, 10**9))
                if (
                    next_clearance < best_clearance
                    or (
                        next_clearance == best_clearance
                        and next_cost >= best_cost
                    )
                ):
                    continue
                best_score[neighbor] = (next_clearance, next_cost)
                previous[neighbor] = current
                heapq.heappush(queue, (-next_clearance, next_cost, sequence, neighbor))
                sequence += 1

        if goal not in previous:
            return None

        path = []
        current: Node | None = goal
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()
        return path

    def _node_neighbors(
        self,
        node: Node,
        allowed_cells: set[str],
        frame,
        blocked: set[Node],
    ) -> list[Node]:
        cell, row, col = node
        neighbors = []
        for dr, dc in (
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, -1), (-1, 1),
        ):
            if dr != 0 and dc != 0:
                side_a = self._step_node(cell, row, col, dr, 0, allowed_cells, frame)
                side_b = self._step_node(cell, row, col, 0, dc, allowed_cells, frame)
                if side_a is None or side_b is None:
                    continue
                if side_a in blocked or side_b in blocked:
                    continue

            next_node = self._step_node(cell, row, col, dr, dc, allowed_cells, frame)
            if next_node is not None:
                neighbors.append(next_node)
        return neighbors

    def _preferred_row_penalty(self, row: int) -> int:
        preferred_rows = {row_number - 1 for row_number in (2, 3, 4)}
        if row in preferred_rows:
            return 0
        return 100

    def _mini_clearance_distances(
        self,
        blocked: set[MiniCell],
    ) -> dict[MiniCell, int]:
        distances: dict[MiniCell, int] = {}
        if not blocked:
            return distances

        for row in range(self.divisions):
            for col in range(self.divisions):
                cell = (row, col)
                if cell in blocked:
                    continue
                distances[cell] = min(
                    max(abs(row - blocked_row), abs(col - blocked_col))
                    for blocked_row, blocked_col in blocked
                )
        return distances

    def _node_clearance_distances(
        self,
        allowed_cells: set[str],
        blocked: set[Node],
    ) -> dict[Node, int]:
        distances: dict[Node, int] = {}
        if not blocked:
            return distances

        blocked_coords = [
            self._global_mini_rc(cell, row, col)
            for cell, row, col in blocked
        ]

        for cell in allowed_cells:
            for row in range(self.divisions):
                for col in range(self.divisions):
                    node = (cell, row, col)
                    if node in blocked:
                        continue
                    global_row, global_col = self._global_mini_rc(cell, row, col)
                    distances[node] = min(
                        max(abs(global_row - blocked_row), abs(global_col - blocked_col))
                        for blocked_row, blocked_col in blocked_coords
                    )
        return distances

    def _global_mini_rc(self, cell: str, row: int, col: int) -> tuple[int, int]:
        parent_row, parent_col = self._cell_rc(cell) or (0, 0)
        return (
            parent_row * self.divisions + row,
            parent_col * self.divisions + col,
        )

    def _step_node(
        self,
        cell: str,
        row: int,
        col: int,
        dr: int,
        dc: int,
        allowed_cells: set[str],
        frame,
    ) -> Node | None:
        next_row = row + dr
        next_col = col + dc
        if 0 <= next_row < self.divisions and 0 <= next_col < self.divisions:
            return (cell, next_row, next_col)

        parent_rc = self._cell_rc(cell)
        if parent_rc is None:
            return None

        parent_row, parent_col = parent_rc
        next_parent_row = parent_row
        next_parent_col = parent_col
        wrapped_row = next_row
        wrapped_col = next_col

        if next_row < 0:
            next_parent_row -= 1
            wrapped_row = self.divisions - 1
        elif next_row >= self.divisions:
            next_parent_row += 1
            wrapped_row = 0

        if next_col < 0:
            next_parent_col -= 1
            wrapped_col = self.divisions - 1
        elif next_col >= self.divisions:
            next_parent_col += 1
            wrapped_col = 0

        next_cell = self._rc_cell(next_parent_row, next_parent_col)
        if next_cell not in allowed_cells:
            return None
        if not self._parent_step_is_open(cell, next_cell, frame):
            return None
        return (next_cell, wrapped_row, wrapped_col)

    def _parent_step_is_open(self, from_cell: str, to_cell: str, frame) -> bool:
        from_rc = self._cell_rc(from_cell)
        to_rc = self._cell_rc(to_cell)
        if from_rc is None or to_rc is None:
            return False

        dr = to_rc[0] - from_rc[0]
        dc = to_rc[1] - from_rc[1]
        if abs(dr) + abs(dc) != 1:
            return False

        walls = frame.grid_walls.get(from_cell, {})
        if dc > 0:
            return not walls.get("right", True)
        if dc < 0:
            return not walls.get("left", True)
        if dr > 0:
            return not walls.get("top", True)
        if dr < 0:
            return not walls.get("bottom", True)
        return False

    def _entry_mini_cell(
        self,
        from_cell: str | None,
        to_cell: str,
    ) -> MiniCell | None:
        from_rc = self._cell_rc(from_cell)
        to_rc = self._cell_rc(to_cell)
        if from_rc is None or to_rc is None:
            return None

        from_row, from_col = from_rc
        to_row, to_col = to_rc
        row_delta = to_row - from_row
        col_delta = to_col - from_col

        mid = self.divisions // 2
        last = self.divisions - 1

        if row_delta != 0 and col_delta != 0:
            row = 0 if row_delta > 0 else last
            col = 0 if col_delta > 0 else last
            return (row, col)
        if col_delta > 0:
            return (mid, 0)
        if col_delta < 0:
            return (mid, last)
        if row_delta > 0:
            return (0, mid)
        if row_delta < 0:
            return (last, mid)
        return None

    def _exit_mini_cell(
        self,
        from_cell: str,
        to_cell: str | None,
    ) -> MiniCell | None:
        from_rc = self._cell_rc(from_cell)
        to_rc = self._cell_rc(to_cell)
        if from_rc is None or to_rc is None:
            return None

        from_row, from_col = from_rc
        to_row, to_col = to_rc
        row_delta = to_row - from_row
        col_delta = to_col - from_col

        mid = self.divisions // 2
        last = self.divisions - 1

        if row_delta != 0 and col_delta != 0:
            row = last if row_delta > 0 else 0
            col = last if col_delta > 0 else 0
            return (row, col)
        if col_delta > 0:
            return (mid, last)
        if col_delta < 0:
            return (mid, 0)
        if row_delta > 0:
            return (last, mid)
        if row_delta < 0:
            return (0, mid)
        return None

    @staticmethod
    def _cell_rc(label: str | None) -> tuple[int, int] | None:
        if not label or len(label) < 2:
            return None
        row = string.ascii_uppercase.find(label[0].upper())
        if row < 0:
            return None
        try:
            col = int(label[1:]) - 1
        except ValueError:
            return None
        if col < 0:
            return None
        return (row, col)

    @staticmethod
    def _rc_cell(row: int, col: int) -> str | None:
        if row < 0 or row >= len(string.ascii_uppercase) or col < 0:
            return None
        return f"{string.ascii_uppercase[row]}{col + 1}"

    @staticmethod
    def _cell_bounds(
        label: str,
        x_lines: list[int],
        y_lines: list[int],
    ) -> Box | None:
        rc = MiniGridPlanner._cell_rc(label)
        if rc is None:
            return None

        row, col = rc
        if row >= len(y_lines) - 1 or col >= len(x_lines) - 1:
            return None
        return (x_lines[col], y_lines[row], x_lines[col + 1], y_lines[row + 1])

    def _mini_cell_bounds(self, cell_bounds: Box, mini: MiniCell) -> Box:
        x1, y1, x2, y2 = cell_bounds
        row, col = mini
        cell_w = (x2 - x1) / self.divisions
        cell_h = (y2 - y1) / self.divisions
        return (
            int(round(x1 + col * cell_w)),
            int(round(y1 + row * cell_h)),
            int(round(x1 + (col + 1) * cell_w)),
            int(round(y1 + (row + 1) * cell_h)),
        )

    def _mini_cell_center(self, cell_bounds: Box, mini: MiniCell) -> Point:
        x1, y1, x2, y2 = self._mini_cell_bounds(cell_bounds, mini)
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _point_mini_cell(self, cell_bounds: Box | None, point: Point) -> MiniCell | None:
        if cell_bounds is None:
            return None

        x1, y1, x2, y2 = cell_bounds
        px, py = point
        if not (x1 <= px <= x2 and y1 <= py <= y2):
            return None

        cell_w = max(1e-6, (x2 - x1) / self.divisions)
        cell_h = max(1e-6, (y2 - y1) / self.divisions)
        col = min(self.divisions - 1, max(0, int((px - x1) / cell_w)))
        row = min(self.divisions - 1, max(0, int((py - y1) / cell_h)))
        return (row, col)

    @staticmethod
    def _point_cell(
        point: Point,
        x_lines: list[int],
        y_lines: list[int],
    ) -> str | None:
        px, py = point
        col = None
        row = None

        for c in range(len(x_lines) - 1):
            if x_lines[c] <= px < x_lines[c + 1]:
                col = c
                break

        for r in range(len(y_lines) - 1):
            if y_lines[r] <= py < y_lines[r + 1]:
                row = r
                break

        if row is None or col is None:
            return None
        return MiniGridPlanner._rc_cell(row, col)

    def _inflate_box(self, box: Box) -> Box:
        margin = self.obstacle_margin_px + self.robot_margin_px
        x1, y1, x2, y2 = box
        return (x1 - margin, y1 - margin, x2 + margin, y2 + margin)

    @staticmethod
    def _boxes_intersect(a: Box, b: Box) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return ax1 <= bx2 and ax2 >= bx1 and ay1 <= by2 and ay2 >= by1
