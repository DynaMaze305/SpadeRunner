from __future__ import annotations

import logging
import math

Point = tuple[int, int]
Box = tuple[int, int, int, int]
logger = logging.getLogger(__name__)


class ObstacleAvoider:
    def __init__(
        self,
        margin: int = 15,
        robot_margin: int = 0,
        bypass_padding: int = 0,
    ):
        self.margin = margin
        self.robot_margin = robot_margin
        self.bypass_padding = bypass_padding

    def inflate_obstacles(self, obstacles: list[Box]) -> list[Box]:
        total_margin = self.margin + self.robot_margin
        return [
            (
                x1 - total_margin,
                y1 - total_margin,
                x2 + total_margin,
                y2 + total_margin,
            )
            for x1, y1, x2, y2 in obstacles
        ]

    def point_inside_box(self, point: Point, box: Box) -> bool:
        x, y = point
        x1, y1, x2, y2 = box
        return x1 <= x <= x2 and y1 <= y <= y2

    def segment_hits_box(self, start: Point, end: Point, box: Box) -> bool:
        steps = max(1, int(math.dist(start, end)))

        sx, sy = start
        ex, ey = end

        for i in range(steps + 1):
            t = i / steps
            x = int(sx + (ex - sx) * t)
            y = int(sy + (ey - sy) * t)

            if self.point_inside_box((x, y), box):
                return True

        return False

    def segment_hits_obstacle(
        self,
        start: Point,
        end: Point,
        obstacles: list[Box],
    ) -> Box | None:
        for obstacle in obstacles:
            if self.segment_hits_box(start, end, obstacle):
                return obstacle

        return None

    def choose_bypass_routes(
        self,
        start: Point,
        end: Point,
        obstacle: Box,
    ) -> list[list[Point]]:
        x1, y1, x2, y2 = obstacle
        base_margin = self.margin + self.robot_margin
        padding_steps = [self.bypass_padding]
        if self.bypass_padding > 0:
            padding_steps.extend([
                self.bypass_padding // 2,
                0,
            ])

        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])

        routes = []
        if dx >= dy:
            for padding in padding_steps:
                bypass_margin = base_margin + padding
                above_y = y1 - bypass_margin
                below_y = y2 + bypass_margin
                routes.extend([
                    [(start[0], above_y), (end[0], above_y)],
                    [(start[0], below_y), (end[0], below_y)],
                ])
            return routes

        for padding in padding_steps:
            bypass_margin = base_margin + padding
            left_x = x1 - bypass_margin
            right_x = x2 + bypass_margin
            routes.extend([
                [(left_x, start[1]), (left_x, end[1])],
                [(right_x, start[1]), (right_x, end[1])],
            ])

        return routes

    def route_is_clear(
        self,
        points: list[Point],
        obstacles: list[Box],
    ) -> bool:
        for a, b in zip(points[:-1], points[1:]):
            if self.segment_hits_obstacle(a, b, obstacles) is not None:
                return False

        return True

    def adjust_path(
        self,
        center_path: list[Point],
        obstacles: list[Box],
    ) -> list[Point] | None:
        if not center_path:
            return []

        inflated_obstacles = self.inflate_obstacles(obstacles)
        safe_path = [center_path[0]]

        for end in center_path[1:]:
            start = safe_path[-1]

            hit_obstacle = self.segment_hits_obstacle(
                start,
                end,
                inflated_obstacles,
            )

            if hit_obstacle is None:
                safe_path.append(end)
                continue

            bypass_routes = self.choose_bypass_routes(
                start,
                end,
                hit_obstacle,
            )

            logger.info(f"[AVOIDER] hit: {start} {end} {hit_obstacle}")
            logger.info(f"[AVOIDER] routes: {bypass_routes}")

            bypass_found = False

            for route in bypass_routes:
                test_points = [start] + route + [end]

                if self.route_is_clear(test_points, inflated_obstacles):
                    safe_path.extend(route)
                    safe_path.append(end)
                    bypass_found = True
                    break

            if not bypass_found:
                logger.warning(
                    f"[AVOIDER] obstacle hit but no bypass route found: {hit_obstacle}"
                )
                return None

        return safe_path
