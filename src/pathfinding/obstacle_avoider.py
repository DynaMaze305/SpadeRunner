from __future__ import annotations

import math

Point = tuple[int, int]
Box = tuple[int, int, int, int]


class ObstacleAvoider:
    def __init__(self, margin: int = 15):
        self.margin = margin

    def inflate_obstacles(self, obstacles: list[Box]) -> list[Box]:
        return [
            (
                x1 - self.margin,
                y1 - self.margin,
                x2 + self.margin,
                y2 + self.margin,
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

        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])

        if dx >= dy:
            above_y = y1 - self.margin
            below_y = y2 + self.margin

            return [
                [(start[0], above_y), (end[0], above_y)],
                [(start[0], below_y), (end[0], below_y)],
            ]

        left_x = x1 - self.margin
        right_x = x2 + self.margin

        return [
            [(left_x, start[1]), (left_x, end[1])],
            [(right_x, start[1]), (right_x, end[1])],
        ]

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
    ) -> list[Point]:
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

            print("[AVOIDER] hit:", start, end, hit_obstacle)
            print("[AVOIDER] routes:", bypass_routes)

            bypass_found = False

            for route in bypass_routes:
                test_points = [start] + route + [end]

                if self.route_is_clear(test_points, inflated_obstacles):
                    safe_path.extend(route)
                    safe_path.append(end)
                    bypass_found = True
                    break

            if not bypass_found:
                print("[AVOIDER] obstacle hit but no bypass route found:", hit_obstacle)
                safe_path.append(end)

        return safe_path