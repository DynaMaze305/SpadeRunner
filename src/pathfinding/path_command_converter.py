# Converts a maze path into robot movement commands
class PathCommandConverter:

    # Maps movement direction to the robot angle needed for that movement
    DIRECTIONS = {
        (0, 1): 0,       # Move right
        (1, 0): 90,      # Move down
        (0, -1): 180,    # Move left
        (-1, 0): -90,    # Move up
    }

    def path_to_commands(
        self,
        path: list[str],
        start_angle: float = 0,
    ) -> list[dict]:
        # Stores the final sequence of robot commands
        commands = []

        # Current robot orientation before starting the path
        current_angle = start_angle

        # Loop over each pair of consecutive cells in the path
        for current, next_cell in zip(path, path[1:]):
            # Convert cell labels like "A1" into row/column coordinates
            r1, c1 = self.label_to_rc(current)
            r2, c2 = self.label_to_rc(next_cell)

            # Compute movement direction between the two cells
            dr = r2 - r1
            dc = c2 - c1

            # Convert movement direction into the angle the robot should face
            target_angle = self.DIRECTIONS[(dr, dc)]

            # Compute the smallest rotation needed to face the target angle
            rotation = self.angle_diff(target_angle, current_angle)

            # Only rotate if the angle difference is significant
            if abs(rotation) > 15:
                commands.append({
                    "action": "rotate",
                    "angle_deg": rotation,
                })

            # Move forward from the current cell to the next cell
            commands.append({
                "action": "move",
                "from": current,
                "to": next_cell,
            })

            # Update robot orientation after the move
            current_angle = target_angle

        return commands

    def label_to_rc(self, label: str) -> tuple[int, int]:
        # Extract row letter and column number from a cell label like "B2"
        row_letter = label[0].upper()
        col = int(label[1:]) - 1

        # Convert maze row labels into row indexes
        # This mapping is specific to a 3-row maze orientation
        row_map = {
            "C": 0,
            "B": 1,
            "A": 2,
        }

        return row_map[row_letter], col

    def angle_diff(self, new: float, old: float) -> float:
        # Compute the shortest signed difference between two angles
        # Result is normalized to the range [-180, 180]
        return (new - old + 180.0) % 360.0 - 180.0