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
PATH_LINE_THICK = 4
CONTOUR_PATH_COLOR = (255, 0, 255)
CONTOUR_POINT_RADIUS = 6
POSITION_DOT_COLOR = (0, 0, 255)
POSITION_DOT_RADIUS = 8
ARROW_COLOR = (128, 0, 128)
ARROW_LENGTH = 35
ARROW_THICK = 2
BLOCKED_CELL_COLOR = (80, 80, 255)
BLOCKED_CELL_ALPHA = 0.28
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
        contour_padding_px: int = 0,
        safe_cell_inset_px: int = 0,
        safe_cell_inset_start_factor: float = 0.45,
        camera: Camera | None = None,
    ) -> None:
        self.run_dir = run_dir
        self.grid_detector = grid_detector
        self.localizer = localizer
        self.obstacle_margin_px = obstacle_margin_px
        self.robot_margin_px = robot_margin_px
        self.contour_padding_px = contour_padding_px
        self.safe_cell_inset_px = safe_cell_inset_px
        self.safe_cell_inset_start_factor = safe_cell_inset_start_factor
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
        contour_path: list[tuple[int, int]] | None = None,
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

        path_img = self._build_path_panel(frame, robot_pose, path, contour_path)
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
        contour_path: list[tuple[int, int]] | None = None,
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
        self._draw_blocked_cells(canvas, frame)

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

        if contour_path and len(contour_path) >= 2:
            planned_waypoints = self._path_waypoints(
                path, local_center, frame,
            )
            for a, b in zip(planned_waypoints[:-1], planned_waypoints[1:]):
                cv2.line(canvas, a, b, PLANNED_PATH_FAINT_COLOR, 2)

            for a, b in zip(contour_path[:-1], contour_path[1:]):
                cv2.line(canvas, a, b, CONTOUR_PATH_COLOR, PATH_LINE_THICK)
            for point in contour_path:
                cv2.circle(canvas, point, CONTOUR_POINT_RADIUS, CONTOUR_PATH_COLOR, -1)

            cv2.putText(
                canvas,
                "contour",
                (contour_path[0][0] + 8, contour_path[0][1] - 8),
                LABEL_FONT,
                PATH_TEXT_SCALE,
                CONTOUR_PATH_COLOR,
                2,
                cv2.LINE_AA,
            )
        elif path and len(path) >= 2:
            waypoints = self._path_waypoints(
                path, local_center, frame,
            )

            for a, b in zip(waypoints[:-1], waypoints[1:]):
                cv2.line(canvas, a, b, PATH_LINE_COLOR, PATH_LINE_THICK)

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
            if path and len(path) >= 2:
                next_cell = path[1]
                next_center = self._safe_cell_center(next_cell, frame)
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
                        f"next:    {next_cell}",
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
            center = self._safe_cell_center(cell, frame)
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

    def _draw_blocked_cells(self, canvas: np.ndarray, frame) -> None:
        blocked_cells = obstacle_cells_from_frame(frame)
        if not blocked_cells:
            return

        overlay = canvas.copy()
        for cell in blocked_cells:
            bounds = self._cell_bounds(cell, frame.x_lines, frame.y_lines)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            cv2.rectangle(overlay, (x1, y1), (x2, y2), BLOCKED_CELL_COLOR, -1)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), BLOCKED_CELL_COLOR, 2)

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
                BLOCKED_CELL_COLOR,
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

    def _safe_cell_center(self, label: str, frame) -> tuple[int, int] | None:
        bounds = self._cell_bounds(label, frame.x_lines, frame.y_lines)
        if bounds is None:
            return None

        x_left, y_top, x_right, y_bottom = bounds
        cx = (x_left + x_right) // 2
        cy = (y_top + y_bottom) // 2

        inset = self._dynamic_safe_cell_inset(
            cx,
            cy,
            x_left,
            y_top,
            x_right,
            y_bottom,
            frame,
        )
        if inset == 0:
            return (cx, cy)

        walls = frame.grid_walls.get(label, {})
        if walls.get("left"):
            cx += inset
        if walls.get("right"):
            cx -= inset
        # MazeGridAnalyzer uses "bottom" for the image-top cell edge and
        # "top" for the image-bottom cell edge.
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
