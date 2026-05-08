from __future__ import annotations

from collections import deque
import heapq
import logging
import math
import string


logger = logging.getLogger(__name__)

Point = tuple[int, int]
Box = tuple[int, int, int, int]
MiniCell = tuple[int, int]
Node = tuple[str, int, int]


class MiniGridPlanner:
    # Soft repulsion weights and radius for forbidden mini-cells.
    OBSTACLE_REPULSION_WEIGHT: float = 1.5
    WALL_REPULSION_WEIGHT: float = 1.0
    REPULSION_RADIUS: int = 2

    def __init__(
        self,
        divisions: int,
        obstacle_margin_px: int = 0,
        robot_margin_px: int = 0,
        portal_indexes: set[int] | None = None,
    ) -> None:
        self.divisions = divisions
        self.obstacle_margin_px = obstacle_margin_px
        self.robot_margin_px = robot_margin_px
        self.portal_indexes = (
            portal_indexes
            if portal_indexes is not None
            else {row_number - 1 for row_number in (2, 3, 4)}
        )

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

        # Forbidden set covers obstacle-margin and wall-adjacent mini-cells.
        blocked = self._blocked_mini_cells(bounds, frame.obstacles)
        blocked |= self._wall_adjacent_mini_cells(blocked_cell, frame)

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
        obstacle_blocked, wall_blocked = self._classify_blocked_nodes(
            bounds_by_cell, frame.obstacles, frame=frame,
        )
        blocked = obstacle_blocked | wall_blocked

        if start in blocked:
            start = self._nearest_unblocked_node(start, blocked, cell_set, frame)
            if start is None:
                return None
        if goal in blocked:
            goal = self._nearest_unblocked_node(goal, blocked, {goal_cell}, frame)
            if goal is None:
                return None

        node_path = self._shortest_node_path(
            start, goal, blocked,
            obstacle_blocked, wall_blocked,
            cell_set, frame,
        )
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

    # A* over the mini-cells of one parent cell.
    def _shortest_path(
        self,
        start: MiniCell,
        goal: MiniCell,
        blocked: set[MiniCell],
    ) -> list[MiniCell] | None:
        if start in blocked or goal in blocked:
            return None

        # A* with euclidean step cost and euclidean heuristic to goal.
        def heuristic(cell: MiniCell) -> float:
            return math.hypot(cell[0] - goal[0], cell[1] - goal[1])

        queue: list[tuple[float, int, MiniCell]] = [(heuristic(start), 0, start)]
        sequence = 1
        previous: dict[MiniCell, MiniCell | None] = {start: None}
        best_cost: dict[MiniCell, float] = {start: 0.0}

        while queue:
            _, _, current = heapq.heappop(queue)
            if current == goal:
                break

            current_cost = best_cost[current]
            for neighbor in self._neighbors(current):
                if neighbor in blocked:
                    continue
                step = math.hypot(neighbor[0] - current[0], neighbor[1] - current[1])
                next_cost = current_cost + step
                if next_cost >= best_cost.get(neighbor, float("inf")):
                    continue
                best_cost[neighbor] = next_cost
                previous[neighbor] = current
                heapq.heappush(queue, (next_cost + heuristic(neighbor), sequence, neighbor))
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

    # Split forbidden mini-cells into obstacle and wall-adjacent sets.
    def _classify_blocked_nodes(
        self,
        bounds_by_cell: dict[str, Box],
        obstacles: list[Box],
        frame=None,
    ) -> tuple[set[Node], set[Node]]:
        obstacle: set[Node] = set()
        wall: set[Node] = set()
        for cell, bounds in bounds_by_cell.items():
            for row, col in self._blocked_mini_cells(bounds, obstacles):
                obstacle.add((cell, row, col))
            if frame is not None:
                for row, col in self._wall_adjacent_mini_cells(cell, frame):
                    wall.add((cell, row, col))
        return obstacle, wall

    # Mini-cells touching a wall on the parent perimeter or corner.
    def _wall_adjacent_mini_cells(self, label: str, frame) -> set[MiniCell]:
        walls = frame.grid_walls.get(label, {}) or {}
        result: set[MiniCell] = set()
        last = self.divisions - 1

        if walls.get("bottom", False):  # image-top wall
            for mc in range(self.divisions):
                result.add((0, mc))
        if walls.get("top", False):  # image-bottom wall
            for mc in range(self.divisions):
                result.add((last, mc))
        if walls.get("left", False):
            for mr in range(self.divisions):
                result.add((mr, 0))
        if walls.get("right", False):
            for mr in range(self.divisions):
                result.add((mr, last))

        rc = self._cell_rc(label)
        if rc is None:
            return result
        row, col = rc
        n_rows = getattr(frame, "n_rows", 0)
        n_cols = getattr(frame, "n_cols", 0)

        def wall_present(r: int, c: int, side: str) -> bool:
            if not (0 <= r < n_rows and 0 <= c < n_cols):
                return False
            neighbour = self._rc_cell(r, c)
            if neighbour is None:
                return False
            return frame.grid_walls.get(neighbour, {}).get(side, False)

        if wall_present(row - 1, col, "left") or wall_present(row, col - 1, "bottom"):
            result.add((0, 0))
        if wall_present(row - 1, col, "right") or wall_present(row, col + 1, "bottom"):
            result.add((0, last))
        if wall_present(row + 1, col, "left") or wall_present(row, col - 1, "top"):
            result.add((last, 0))
        if wall_present(row + 1, col, "right") or wall_present(row, col + 1, "top"):
            result.add((last, last))

        return result

    # Multi-source BFS distance from each node to the nearest source, capped at max_distance.
    def _node_distance_to_set(
        self,
        sources: set[Node],
        allowed_cells: set[str],
        frame,
        max_distance: int,
    ) -> dict[Node, int]:
        distances: dict[Node, int] = {node: 0 for node in sources}
        queue: deque[Node] = deque(sources)
        while queue:
            node = queue.popleft()
            d = distances[node]
            if d >= max_distance:
                continue
            for neighbor in self._node_neighbors(node, allowed_cells, frame, blocked=set()):
                if neighbor in distances:
                    continue
                distances[neighbor] = d + 1
                queue.append(neighbor)
        return distances

    # A* across mini-cells of every parent cell in the corridor.
    def _shortest_node_path(
        self,
        start: Node,
        goal: Node,
        blocked: set[Node],
        obstacle_blocked: set[Node],
        wall_blocked: set[Node],
        allowed_cells: set[str],
        frame,
    ) -> list[Node] | None:
        if start in blocked or goal in blocked:
            return None

        # A* with euclidean cost plus soft repulsion away from forbidden cells.
        goal_global = self._global_mini_rc(*goal)

        def heuristic(node: Node) -> float:
            gr, gc = self._global_mini_rc(*node)
            return math.hypot(gr - goal_global[0], gc - goal_global[1])

        radius = self.REPULSION_RADIUS
        obstacle_distances = self._node_distance_to_set(
            obstacle_blocked, allowed_cells, frame, radius,
        )
        wall_distances = self._node_distance_to_set(
            wall_blocked, allowed_cells, frame, radius,
        )

        def repulsion(node: Node) -> float:
            d_o = obstacle_distances.get(node, radius + 1)
            d_w = wall_distances.get(node, radius + 1)
            return (
                self.OBSTACLE_REPULSION_WEIGHT * max(0, radius - d_o)
                + self.WALL_REPULSION_WEIGHT * max(0, radius - d_w)
            )

        queue: list[tuple[float, int, Node]] = [(heuristic(start), 0, start)]
        sequence = 1
        previous: dict[Node, Node | None] = {start: None}
        best_cost: dict[Node, float] = {start: 0.0}

        while queue:
            _, _, current = heapq.heappop(queue)
            if current == goal:
                break

            current_cost = best_cost[current]
            current_global = self._global_mini_rc(*current)
            for neighbor in self._node_neighbors(current, allowed_cells, frame, blocked):
                if neighbor in blocked:
                    continue
                neighbor_global = self._global_mini_rc(*neighbor)
                step = math.hypot(
                    neighbor_global[0] - current_global[0],
                    neighbor_global[1] - current_global[1],
                )
                next_cost = current_cost + step + repulsion(neighbor)
                if next_cost >= best_cost.get(neighbor, float("inf")):
                    continue
                best_cost[neighbor] = next_cost
                previous[neighbor] = current
                heapq.heappush(queue, (next_cost + heuristic(neighbor), sequence, neighbor))
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
        if not self._portal_step_is_allowed(
            parent_row,
            parent_col,
            next_parent_row,
            next_parent_col,
            row,
            col,
        ):
            return None
        if not self._parent_step_is_open(cell, next_cell, frame):
            return None
        return (next_cell, wrapped_row, wrapped_col)

    def _portal_step_is_allowed(
        self,
        parent_row: int,
        parent_col: int,
        next_parent_row: int,
        next_parent_col: int,
        row: int,
        col: int,
    ) -> bool:
        dr = next_parent_row - parent_row
        dc = next_parent_col - parent_col
        if abs(dr) + abs(dc) != 1:
            return False
        if dc != 0:
            return row in self.portal_indexes
        if dr != 0:
            return col in self.portal_indexes
        return False

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
