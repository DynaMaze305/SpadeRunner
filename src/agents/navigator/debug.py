from __future__ import annotations

import logging
import math
import os
import string

import cv2
import numpy as np

from pathfinding.pathfinding import obstacle_cells_from_frame
from vision.camera import Camera
from vision.robot_grid_localizer import RobotGridLocalizer


logger = logging.getLogger(__name__)


# Layout: 2 rows x 4 cols of panels, each panel sized PANEL_W x PANEL_H.
# Sized to fit the native 800x448 camera frame at 1:1 so panels are not downscaled.
# Final composite: 4 * PANEL_W wide x 2 * PANEL_H tall.
PANEL_W = 800
PANEL_H = 500
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.9
LABEL_THICK = 2
LABEL_COLOR = (0, 255, 0)

# Cell-label text drawn at the centre of each detected grid cell on the grid panel.
CELL_LABEL_COLOR = (0, 255, 255)
CELL_LABEL_SCALE = 0.5
CELL_LABEL_THICK = 1

# Path-panel colours (BGR).
PATH_PANEL_BG = (255, 255, 255)
PATH_GRID_VERTICAL = (255, 0, 0)
PATH_GRID_HORIZONTAL = (0, 255, 0)
PATH_LINE_COLOR = (0, 165, 255)
PLANNED_PATH_FAINT_COLOR = (180, 210, 255)
BYPASS_PATH_COLOR = (255, 128, 0)
BYPASS_POINT_RADIUS = 4
# Mini-grid line colour used for cells that are discretised but neither
# blocked nor adjacent to any traversed blocked cell. Purple = anomaly.
MINI_GRID_COLOR = (200, 0, 200)
# Pink — cell is a corridor entry/exit (free, but grid-adjacent to a
# traversed blocked cell so the planner pulled it into the mini-grid corridor).
ENTRY_CORRIDOR_GRID_COLOR = (180, 105, 255)
PATH_LINE_THICK = 4
POSITION_DOT_COLOR = (0, 0, 255)
POSITION_DOT_RADIUS = 8
ARROW_COLOR = (128, 0, 128)
ARROW_LENGTH = 35
ARROW_THICK = 2
BLOCKED_CELL_COLOR = (80, 80, 255)
TRAVERSED_BLOCKED_CELL_COLOR = (0, 165, 255)
BLOCKED_CELL_ALPHA = 0.28
# Dark red fill for individual mini-cells whose bounds intersect any inflated
# obstacle (i.e. mini-cells the planner cannot step on). Drawn inside cells
# that received a mini-grid overlay so the unreachable areas are obvious.
BLOCKED_MINI_CELL_COLOR = (40, 40, 140)
# Lighter red for mini-cells that touch a wall side of the parent cell.
WALL_ADJACENT_MINI_CELL_COLOR = (80, 80, 220)
RAW_OBSTACLE_COLOR = (0, 0, 255)
INFLATED_OBSTACLE_COLOR = (255, 0, 255)
ROBOT_EXCLUSION_COLOR = (255, 255, 0)

# Target-direction arrow + path info text overlay (BGR).
TARGET_ARROW_COLOR = (0, 180, 0)
PATH_TEXT_COLOR = (40, 40, 40)
PATH_TEXT_SCALE = 0.55
PATH_TEXT_LINE_HEIGHT = 22


# Builds and saves one composite "debug card" per step.
# All panels are letterboxed into the same size so cv2.hconcat works.
class NavigatorDebug:

    def __init__(
        self,
        run_dir: str,
        grid_detector,
        localizer,
        obstacle_margin_px: int = 0,
        robot_margin_px: int = 0,
        mini_grid_divisions: int = 5,
        camera: Camera | None = None,
    ) -> None:
        self.run_dir = run_dir
        self.grid_detector = grid_detector
        self.localizer = localizer
        self.obstacle_margin_px = obstacle_margin_px
        self.robot_margin_px = robot_margin_px
        self.mini_grid_divisions = mini_grid_divisions
        self.camera = camera or Camera()
        os.makedirs(run_dir, exist_ok=True)

    @staticmethod
    def fmt(v) -> str:
        return f"{v:.2f}" if isinstance(v, (int, float)) else "None"

    def save_step_composite(
        self,
        step: int,
        image=None,
        frame=None,
        robot_pose=None,
        path: list[str] | None = None,
        point_path: list[tuple[int, int]] | None = None,
    ) -> None:
        image_with_axes = self.camera.draw_axes(image) if image is not None else None

        crop_img = frame.maze["cropped"] if frame is not None else None
        wall_img = frame.wall_clean if frame is not None else None

        if frame is not None:
            grid_overlay = self.grid_detector.draw_grid_lines(
                wall_clean=frame.wall_clean,
                x_lines=frame.x_lines,
                y_lines=frame.y_lines,
            )
            grid_img = cv2.cvtColor(grid_overlay, cv2.COLOR_RGB2BGR)
            self._draw_cell_labels(grid_img, frame.x_lines, frame.y_lines)
        else:
            grid_img = None

        aruco_img = None
        robot_img = None
        if image_with_axes is not None and self.localizer is not None:
            aruco_img = self.localizer.draw_aruco_debug(image_with_axes)
            if robot_pose is not None and frame is not None:
                robot_result = {
                    "cell": robot_pose.cell,
                    "angle_deg": robot_pose.angle_deg,
                    "raw_angle_deg": robot_pose.raw_angle_deg,
                    "center": robot_pose.center,
                }
                robot_img = self.localizer.draw_robot_grid_debug(
                    image=image_with_axes,
                    robot_result=robot_result,
                    crop_bbox=frame.maze["crop_bbox"],
                    x_lines=frame.x_lines,
                    y_lines=frame.y_lines,
                    grid_walls=frame.grid_walls,
                )

        path_img = self._build_path_panel(frame, robot_pose, path, point_path)
        obstacles_img = self._build_obstacles_panel(frame)

        # Save individual full-resolution images into individuals/step_N/
        self._save_individuals(
            step,
            {
                "raw": image_with_axes,
                "crop": crop_img,
                "wall_mask": wall_img,
                "grid": grid_img,
                "aruco": aruco_img,
                "robot": robot_img,
                "obstacles": obstacles_img,
                "path": path_img,
            },
        )

        # Build the composite by letterboxing each source into a uniform panel.
        raw_panel = self._panel(image_with_axes, "raw")
        crop_panel = self._panel(crop_img, "crop")
        wall_panel = self._panel(wall_img, "wall_mask")
        grid_panel = self._panel(grid_img, "grid")
        aruco_panel = self._panel(aruco_img, "aruco")
        robot_panel = self._panel(robot_img, "robot")
        obstacle_panel = self._panel(obstacles_img, "obstacles")
        path_panel = self._panel(path_img, "path")

        row1 = cv2.hconcat([raw_panel, crop_panel, wall_panel, grid_panel])
        row2 = cv2.hconcat([aruco_panel, robot_panel, obstacle_panel, path_panel])
        composite = cv2.vconcat([row1, row2])

        out_path = os.path.join(self.run_dir, f"step_{step}.jpg")
        cv2.imwrite(out_path, composite)
        logger.info(f"[DEBUG] Saved composite step {step} -> {out_path}")

    # Draws the A1, A2, ... cell labels at the centre of each detected cell.
    # Uses the same row-letter / column-number convention as MazeGridAnalyzer
    # so the labels match the keys in grid_walls and the path logic.
    @staticmethod
    def _draw_cell_labels(
        image: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
    ) -> None:
        n_rows = len(y_lines) - 1
        n_cols = len(x_lines) - 1
        if n_rows <= 0 or n_cols <= 0:
            return

        for r in range(min(n_rows, len(string.ascii_uppercase))):
            for c in range(n_cols):
                cx = (x_lines[c] + x_lines[c + 1]) // 2
                cy = (y_lines[r] + y_lines[r + 1]) // 2
                label = f"{string.ascii_uppercase[r]}{c + 1}"
                (tw, th), _ = cv2.getTextSize(
                    label, LABEL_FONT, CELL_LABEL_SCALE, CELL_LABEL_THICK,
                )
                cv2.putText(
                    image,
                    label,
                    (cx - tw // 2, cy + th // 2),
                    LABEL_FONT,
                    CELL_LABEL_SCALE,
                    CELL_LABEL_COLOR,
                    CELL_LABEL_THICK,
                    cv2.LINE_AA,
                )

    # Builds a white-background panel that mirrors the robot panel (grid + walls
    # + direction arrow) but adds the planned path in orange and the current
    # cell as a red dot. Returns None when there's no frame to draw on.
    def _build_path_panel(
        self,
        frame,
        robot_pose,
        path: list[str] | None,
        point_path: list[tuple[int, int]] | None = None,
    ) -> np.ndarray | None:
        if frame is None:
            return None

        cropped = frame.maze["cropped"]
        h, w = cropped.shape[:2]
        canvas = np.full((h, w, 3), PATH_PANEL_BG, dtype=np.uint8)

        for x in frame.x_lines:
            cv2.line(canvas, (x, 0), (x, h - 1), PATH_GRID_VERTICAL, 1)
        for y in frame.y_lines:
            cv2.line(canvas, (0, y), (w - 1, y), PATH_GRID_HORIZONTAL, 1)

        if frame.grid_walls:
            RobotGridLocalizer._draw_walls(
                canvas, frame.grid_walls, frame.x_lines, frame.y_lines,
            )

        self._draw_obstacle_boxes(canvas, frame.obstacles)
        self._draw_blocked_cells(canvas, frame, point_path)

        # Build the visual path. The first segment starts at the robot's actual
        # pixel position (red dot) rather than the centre of path[0], so the
        # drawn path matches where the robot really is. Subsequent segments are
        # cell-centre to cell-centre as before.
        local_center: tuple[int, int] | None = None
        if robot_pose is not None:
            bx1, by1, _, _ = frame.maze["crop_bbox"]
            local_center = (
                int(robot_pose.center[0] - bx1),
                int(robot_pose.center[1] - by1),
            )

        if path and len(path) >= 2:
            waypoints = self._path_waypoints(
                path, local_center, frame,
            )

            for a, b in zip(waypoints[:-1], waypoints[1:]):
                color = PLANNED_PATH_FAINT_COLOR if point_path else PATH_LINE_COLOR
                thickness = 2 if point_path else PATH_LINE_THICK
                cv2.line(canvas, a, b, color, thickness)

        if point_path and len(point_path) >= 1:
            self._draw_mini_grid_for_points(canvas, frame, point_path)

            bypass_waypoints = []
            if local_center is not None:
                bypass_waypoints.append(local_center)
            bypass_waypoints.extend(point_path)

            for a, b in zip(bypass_waypoints[:-1], bypass_waypoints[1:]):
                cv2.line(canvas, a, b, BYPASS_PATH_COLOR, PATH_LINE_THICK)
            for point in point_path:
                cv2.circle(canvas, point, BYPASS_POINT_RADIUS, BYPASS_PATH_COLOR, -1)

        info_lines: list[str] = []

        if robot_pose is not None and local_center is not None:
            cv2.circle(canvas, local_center, POSITION_DOT_RADIUS,
                       POSITION_DOT_COLOR, -1)

            # Current heading arrow (purple).
            angle_rad = math.radians(robot_pose.angle_deg)
            end = (
                int(local_center[0] + ARROW_LENGTH * math.cos(angle_rad)),
                int(local_center[1] - ARROW_LENGTH * math.sin(angle_rad)),
            )
            cv2.arrowedLine(canvas, local_center, end, ARROW_COLOR, ARROW_THICK)

            # Target heading arrow (green) toward the next cell in the path,
            # plus info text covering current/target/rotation/distance.
            if point_path:
                next_center = point_path[0]
                next_label = "mini"
            elif path and len(path) >= 2:
                next_cell = path[1]
                next_center = self._cell_center(next_cell, frame)
                next_label = next_cell
            else:
                next_center = None

            if next_center is not None:
                dx = next_center[0] - local_center[0]
                dy = next_center[1] - local_center[1]
                distance_px = math.hypot(dx, dy)
                # math-convention angle (image y inverted, consistent with the
                # rest of the codebase's angle handling).
                target_angle = math.degrees(math.atan2(-dy, dx))
                rotation = (
                    target_angle - robot_pose.angle_deg + 180.0
                ) % 360.0 - 180.0

                target_rad = math.radians(target_angle)
                target_end = (
                    int(local_center[0] + ARROW_LENGTH * math.cos(target_rad)),
                    int(local_center[1] - ARROW_LENGTH * math.sin(target_rad)),
                )
                cv2.arrowedLine(
                    canvas, local_center, target_end,
                    TARGET_ARROW_COLOR, ARROW_THICK,
                )

                info_lines = [
                    f"current: {robot_pose.angle_deg:+.1f}",
                    f"target:  {target_angle:+.1f}",
                    f"rotate:  {rotation:+.1f}",
                    f"next:    {next_label}",
                    f"dist:    {distance_px:.0f} px",
                ]

        if info_lines:
            y_text = 22
            for line in info_lines:
                cv2.putText(
                    canvas, line, (8, y_text), LABEL_FONT,
                    PATH_TEXT_SCALE, PATH_TEXT_COLOR, 1, cv2.LINE_AA,
                )
                y_text += PATH_TEXT_LINE_HEIGHT

        return canvas

    def _draw_mini_grid_for_points(
        self,
        canvas: np.ndarray,
        frame,
        point_path: list[tuple[int, int]],
    ) -> None:
        points_by_bounds: dict[tuple[int, int, int, int], list[tuple[int, int]]] = {}
        bounds_to_rc: dict[tuple[int, int, int, int], tuple[int, int]] = {}
        for point in point_path:
            cell_bounds = self._cell_bounds_for_point(point, frame.x_lines, frame.y_lines)
            if cell_bounds is None:
                continue
            points_by_bounds.setdefault(cell_bounds, []).append(point)
            if cell_bounds not in bounds_to_rc:
                rc = self._bounds_to_rc(cell_bounds, frame.x_lines, frame.y_lines)
                if rc is not None:
                    bounds_to_rc[cell_bounds] = rc

        # Diagnostic: log every cell that ended up with >=2 waypoints, with
        # the exact waypoint coordinates that landed there. Lets us see
        # whether the planner emitted the points to the right cell.
        for bounds, pts in sorted(
            points_by_bounds.items(),
            key=lambda kv: bounds_to_rc.get(kv[0], (-1, -1)),
        ):
            if len(pts) < 2:
                continue
            rc = bounds_to_rc.get(bounds)
            label = (
                chr(ord("A") + rc[0]) + str(rc[1] + 1) if rc is not None else "?"
            )
            logger.info(f"[MINI-DEBUG] cell {label} bounds={bounds} pts={pts}")

        counts = {b: len(p) for b, p in points_by_bounds.items()}

        blocked_bounds: dict[tuple[int, int, int, int], tuple[int, int]] = {}
        for cell in obstacle_cells_from_frame(frame):
            bounds = self._cell_bounds(cell, frame.x_lines, frame.y_lines)
            if bounds is None:
                continue
            rc = self._bounds_to_rc(bounds, frame.x_lines, frame.y_lines)
            if rc is not None:
                blocked_bounds[bounds] = rc

        traversed_blocked_rcs = {
            rc for bounds, rc in blocked_bounds.items() if bounds in counts
        }

        for cell_bounds, count in counts.items():
            if count < 2:
                continue
            if cell_bounds in blocked_bounds:
                color = TRAVERSED_BLOCKED_CELL_COLOR
            else:
                rc = bounds_to_rc.get(cell_bounds)
                if rc is not None and any(
                    abs(rc[0] - br) + abs(rc[1] - bc) == 1
                    for br, bc in traversed_blocked_rcs
                ):
                    color = ENTRY_CORRIDOR_GRID_COLOR
                else:
                    color = MINI_GRID_COLOR
            rc = bounds_to_rc.get(cell_bounds)
            cell_label = (
                chr(ord("A") + rc[0]) + str(rc[1] + 1) if rc is not None else None
            )
            self._draw_mini_grid_cell(
                canvas, cell_bounds, color,
                obstacles=frame.obstacles,
                frame=frame, cell_label=cell_label,
            )

    def _draw_mini_grid_cell(
        self,
        canvas: np.ndarray,
        cell_bounds: tuple[int, int, int, int],
        color: tuple[int, int, int] = MINI_GRID_COLOR,
        obstacles: list[tuple[int, int, int, int]] | None = None,
        frame=None,
        cell_label: str | None = None,
    ) -> None:
        x1, y1, x2, y2 = cell_bounds
        divisions = max(1, self.mini_grid_divisions)

        if frame is not None and cell_label and getattr(frame, "grid_walls", None):
            wall_minis = self._wall_adjacent_minis(frame, cell_label, divisions)
            for mr, mc in wall_minis:
                mx1 = int(round(x1 + (x2 - x1) * mc / divisions))
                my1 = int(round(y1 + (y2 - y1) * mr / divisions))
                mx2 = int(round(x1 + (x2 - x1) * (mc + 1) / divisions))
                my2 = int(round(y1 + (y2 - y1) * (mr + 1) / divisions))
                cv2.rectangle(
                    canvas, (mx1, my1), (mx2, my2),
                    WALL_ADJACENT_MINI_CELL_COLOR, -1,
                )

        if obstacles:
            margin = self.obstacle_margin_px + self.robot_margin_px
            inflated = [
                (ox1 - margin, oy1 - margin, ox2 + margin, oy2 + margin)
                for ox1, oy1, ox2, oy2 in obstacles
            ]
            for mr in range(divisions):
                for mc in range(divisions):
                    mx1 = int(round(x1 + (x2 - x1) * mc / divisions))
                    my1 = int(round(y1 + (y2 - y1) * mr / divisions))
                    mx2 = int(round(x1 + (x2 - x1) * (mc + 1) / divisions))
                    my2 = int(round(y1 + (y2 - y1) * (mr + 1) / divisions))
                    if any(
                        mx1 <= ix2 and mx2 >= ix1 and my1 <= iy2 and my2 >= iy1
                        for ix1, iy1, ix2, iy2 in inflated
                    ):
                        cv2.rectangle(
                            canvas, (mx1, my1), (mx2, my2),
                            BLOCKED_MINI_CELL_COLOR, -1,
                        )

        for i in range(1, divisions):
            x = int(round(x1 + (x2 - x1) * i / divisions))
            y = int(round(y1 + (y2 - y1) * i / divisions))
            cv2.line(canvas, (x, y1), (x, y2), color, 1)
            cv2.line(canvas, (x1, y), (x2, y), color, 1)

        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

    @staticmethod
    def _bounds_to_rc(
        bounds: tuple[int, int, int, int],
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int] | None:
        x1, y1, _, _ = bounds
        try:
            col = x_lines.index(x1)
            row = y_lines.index(y1)
        except ValueError:
            return None
        return (row, col)

    # Returns the set of (mini_row, mini_col) positions that should be marked
    # as wall-adjacent for the parent cell `label`. Includes:
    #  - the row/column along any side of the parent that has a wall, AND
    #  - corner mini-cells when a wall of a neighbouring cell ends at that
    #    corner (e.g. the wall between B5 and B6 makes C5's top-right
    #    mini-cell wall-adjacent even though no side of C5 itself has a wall).
    @staticmethod
    def _wall_adjacent_minis(
        frame, label: str, divisions: int,
    ) -> set[tuple[int, int]]:
        walls = frame.grid_walls.get(label, {}) or {}
        result: set[tuple[int, int]] = set()

        if walls.get("top", False):
            for mc in range(divisions):
                result.add((0, mc))
        if walls.get("bottom", False):
            for mc in range(divisions):
                result.add((divisions - 1, mc))
        if walls.get("left", False):
            for mr in range(divisions):
                result.add((mr, 0))
        if walls.get("right", False):
            for mr in range(divisions):
                result.add((mr, divisions - 1))

        try:
            row = ord(label[0].upper()) - ord("A")
            col = int(label[1:]) - 1
        except (ValueError, IndexError):
            return result

        n_rows = frame.n_rows
        n_cols = frame.n_cols

        def wall_present(r: int, c: int, side: str) -> bool:
            if not (0 <= r < n_rows and 0 <= c < n_cols):
                return False
            neighbour_label = chr(ord("A") + r) + str(c + 1)
            return frame.grid_walls.get(neighbour_label, {}).get(side, False)

        # top-left corner: above's left wall, or left's top wall
        if wall_present(row - 1, col, "left") or wall_present(row, col - 1, "top"):
            result.add((0, 0))
        # top-right corner: above's right wall, or right's top wall
        if wall_present(row - 1, col, "right") or wall_present(row, col + 1, "top"):
            result.add((0, divisions - 1))
        # bottom-left corner: below's left wall, or left's bottom wall
        if wall_present(row + 1, col, "left") or wall_present(row, col - 1, "bottom"):
            result.add((divisions - 1, 0))
        # bottom-right corner: below's right wall, or right's bottom wall
        if wall_present(row + 1, col, "right") or wall_present(row, col + 1, "bottom"):
            result.add((divisions - 1, divisions - 1))

        return result

    @staticmethod
    def _cell_bounds_for_point(
        point: tuple[int, int],
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int, int, int] | None:
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

        return (x_lines[col], y_lines[row], x_lines[col + 1], y_lines[row + 1])

    def _path_waypoints(
        self,
        path: list[str] | None,
        local_center: tuple[int, int] | None,
        frame,
    ) -> list[tuple[int, int]]:
        if not path:
            return []

        waypoints: list[tuple[int, int]] = []
        if local_center is not None:
            waypoints.append(local_center)
            cells_to_visit = path[1:]
        else:
            cells_to_visit = path

        for cell in cells_to_visit:
            center = self._cell_center(cell, frame)
            if center is not None:
                waypoints.append(center)

        return waypoints

    def _build_obstacles_panel(self, frame):
        if frame is None:
            return None

        canvas = cv2.cvtColor(frame.obstacle_mask, cv2.COLOR_GRAY2BGR)

        for x1, y1, x2, y2 in frame.obstacles:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), RAW_OBSTACLE_COLOR, 2)

        for x1, y1, x2, y2 in getattr(frame, "obstacle_robot_exclusions", []):
            cv2.rectangle(canvas, (x1, y1), (x2, y2), ROBOT_EXCLUSION_COLOR, 2)
            cv2.putText(
                canvas,
                "robot ignored",
                (x1, max(12, y1 - 6)),
                LABEL_FONT,
                0.45,
                ROBOT_EXCLUSION_COLOR,
                1,
                cv2.LINE_AA,
            )

        self._draw_obstacle_boxes(canvas, frame.obstacles)
        cv2.putText(
            canvas,
            f"raw=red inflated=magenta aruco-ignore=cyan obstacle={self.obstacle_margin_px}px robot={self.robot_margin_px}px",
            (8, 22),
            LABEL_FONT,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        return canvas

    def _draw_obstacle_boxes(
        self,
        canvas: np.ndarray,
        obstacles: list[tuple[int, int, int, int]] | None = None,
    ) -> None:
        if obstacles is None:
            return

        h, w = canvas.shape[:2]
        margin = self.obstacle_margin_px + self.robot_margin_px

        for x1, y1, x2, y2 in obstacles:
            ix1 = max(0, x1 - margin)
            iy1 = max(0, y1 - margin)
            ix2 = min(w - 1, x2 + margin)
            iy2 = min(h - 1, y2 + margin)

            cv2.rectangle(canvas, (ix1, iy1), (ix2, iy2), INFLATED_OBSTACLE_COLOR, 1)

    def _draw_blocked_cells(
        self,
        canvas: np.ndarray,
        frame,
        point_path: list[tuple[int, int]] | None = None,
    ) -> None:
        blocked_cells = obstacle_cells_from_frame(frame)
        if not blocked_cells:
            return

        traversed_bounds: set[tuple[int, int, int, int]] = set()
        if point_path:
            for point in point_path:
                bounds = self._cell_bounds_for_point(
                    point, frame.x_lines, frame.y_lines,
                )
                if bounds is not None:
                    traversed_bounds.add(bounds)

        overlay = canvas.copy()
        for cell in blocked_cells:
            bounds = self._cell_bounds(cell, frame.x_lines, frame.y_lines)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            color = (
                TRAVERSED_BLOCKED_CELL_COLOR
                if bounds in traversed_bounds
                else BLOCKED_CELL_COLOR
            )
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

            (tw, th), _ = cv2.getTextSize(
                "blocked", LABEL_FONT, CELL_LABEL_SCALE, CELL_LABEL_THICK,
            )
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            cv2.putText(
                canvas,
                "blocked",
                (cx - tw // 2, cy + th // 2),
                LABEL_FONT,
                CELL_LABEL_SCALE,
                color,
                CELL_LABEL_THICK,
                cv2.LINE_AA,
            )

        cv2.addWeighted(
            overlay,
            BLOCKED_CELL_ALPHA,
            canvas,
            1.0 - BLOCKED_CELL_ALPHA,
            0,
            canvas,
        )

    # Converts a cell label like "B5" to its centre pixel in crop-image coords.
    # Returns None if the label is malformed or out of bounds for the detected grid.
    @staticmethod
    def _cell_center(
        label: str,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int] | None:
        if not label or len(label) < 2:
            return None
        row_letter = label[0].upper()
        try:
            col = int(label[1:]) - 1
        except ValueError:
            return None
        r = ord(row_letter) - ord("A")
        if r < 0 or r >= len(y_lines) - 1:
            return None
        if col < 0 or col >= len(x_lines) - 1:
            return None
        cx = (x_lines[col] + x_lines[col + 1]) // 2
        cy = (y_lines[r] + y_lines[r + 1]) // 2
        return (cx, cy)

    def _cell_center(self, label: str, frame) -> tuple[int, int] | None:
        bounds = self._cell_bounds(label, frame.x_lines, frame.y_lines)
        if bounds is None:
            return None

        x_left, y_top, x_right, y_bottom = bounds
        return ((x_left + x_right) // 2, (y_top + y_bottom) // 2)

    @staticmethod
    def _label_rc(label: str | None) -> tuple[int, int] | None:
        if not label or len(label) < 2:
            return None
        try:
            col = int(label[1:]) - 1
        except ValueError:
            return None
        row = ord(label[0].upper()) - ord("A")
        if row < 0 or col < 0:
            return None
        return (row, col)

    @staticmethod
    def _cell_bounds(
        label: str,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int, int, int] | None:
        if not label or len(label) < 2:
            return None
        row_letter = label[0].upper()
        try:
            col = int(label[1:]) - 1
        except ValueError:
            return None
        r = ord(row_letter) - ord("A")
        if r < 0 or r >= len(y_lines) - 1:
            return None
        if col < 0 or col >= len(x_lines) - 1:
            return None
        return (x_lines[col], y_lines[r], x_lines[col + 1], y_lines[r + 1])

    def _save_individuals(self, step: int, named_images: dict) -> None:
        # Create the per-step subfolder lazily, only if there's something to save.
        available = {n: img for n, img in named_images.items() if img is not None}
        if not available:
            return

        step_dir = os.path.join(self.run_dir, "individuals", f"step_{step}")
        os.makedirs(step_dir, exist_ok=True)

        for name, img in available.items():
            cv2.imwrite(os.path.join(step_dir, f"{name}.jpg"), img)

    def _panel(
        self,
        img,
        label: str,
        w: int = PANEL_W,
        h: int = PANEL_H,
    ) -> np.ndarray:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

        if img is None:
            cv2.putText(
                canvas,
                "n/a",
                (w // 2 - 30, h // 2),
                LABEL_FONT,
                0.8,
                (80, 80, 80),
                2,
            )
        else:
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            ih, iw = img.shape[:2]
            scale = min(w / iw, h / ih)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            resized = cv2.resize(img, (nw, nh))
            y0 = (h - nh) // 2
            x0 = (w - nw) // 2
            canvas[y0:y0 + nh, x0:x0 + nw] = resized

        if label:
            cv2.putText(
                canvas,
                label,
                (12, 36),
                LABEL_FONT,
                LABEL_SCALE,
                LABEL_COLOR,
                LABEL_THICK,
            )
        return canvas
