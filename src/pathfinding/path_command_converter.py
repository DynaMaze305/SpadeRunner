import math


class PathCommandConverter:
    DIRECTIONS = {
        (0, 1): 0,
        (1, 1): 45,
        (1, 0): 90,
        (1, -1): 135,
        (0, -1): 180,
        (-1, -1): -135,
        (-1, 0): -90,
        (-1, 1): -45,
    }

    def path_to_commands(
        self,
        path: list[str],
        start_angle: float = 0,
    ) -> list[dict]:
        commands = []
        current_angle = start_angle

        for current, next_cell in zip(path, path[1:]):
            r1, c1 = self.label_to_rc(current)
            r2, c2 = self.label_to_rc(next_cell)

            dr = r2 - r1
            dc = c2 - c1

            target_angle = self.DIRECTIONS[(dr, dc)]
            rotation = self.angle_diff(target_angle, current_angle)

            if abs(rotation) > 15:
                commands.append({
                    "action": "rotate",
                    "angle_deg": rotation,
                })

            commands.append({
                "action": "move",
                "from": current,
                "to": next_cell,
            })

            current_angle = target_angle

        return commands

    def points_to_commands(
        self,
        path: list[tuple[int, int]],
        start_angle: float = 0,
        pixels_per_move_unit: float = 1.0,
    ) -> list[dict]:
        commands = []
        current_angle = start_angle

        for current, next_point in zip(path, path[1:]):
            x1, y1 = current
            x2, y2 = next_point

            dx = x2 - x1
            dy = y2 - y1

            distance_px = math.hypot(dx, dy)

            if distance_px < 1:
                continue

            # Image coordinates:
            # +x = right
            # +y = down
            target_angle = math.degrees(math.atan2(-dy, dx))

            rotation = self.angle_diff(target_angle, current_angle)

            if abs(rotation) > 15:
                commands.append({
                    "action": "rotate",
                    "angle_deg": rotation,
                })

            commands.append({
                "action": "move",
                "from": current,
                "to": next_point,
                "distance_px": distance_px,
                "distance": distance_px / pixels_per_move_unit,
            })

            current_angle = target_angle

        return commands

    def label_to_rc(self, label: str) -> tuple[int, int]:
        row_letter = label[0].upper()
        col = int(label[1:]) - 1

        row_map = {
            "C": 0,
            "B": 1,
            "A": 2,
        }

        return row_map[row_letter], col

    def angle_diff(self, new: float, old: float) -> float:
        return (new - old + 180.0) % 360.0 - 180.0
