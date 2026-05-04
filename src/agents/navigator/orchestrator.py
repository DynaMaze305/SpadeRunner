from __future__ import annotations

import asyncio
import logging
import math
import os
from typing import Awaitable, Callable, Optional

# ArUco retry settings — fresh photo + fresh detection up to N attempts
MAX_DETECT_ATTEMPTS = 3
RETRY_DELAY_S = 0.2

from agents.navigator.config import NavigatorConfig
from agents.navigator.debug import NavigatorDebug
from agents.navigator.localization import RobotLocalizationStep
from agents.navigator.planner import PathPlanner
from agents.navigator.result import NavigationOutcome, NavigationResult
from agents.navigator.vision_pipeline import (
    MazeVisionPipeline,
    VisionError,
)

from pathfinding.path_command_converter import PathCommandConverter
from vision.camera import Camera


logger = logging.getLogger(__name__)


# Navigation session loop, with no SPADE imports.
# All collaborators are injected so tests can pass fakes without an XMPP server.
class NavigationOrchestrator:

    def __init__(
        self,
        config: NavigatorConfig,
        photo_source: Callable[[str], Awaitable[Optional[bytes]]],
        vision: MazeVisionPipeline,
        localizer: RobotLocalizationStep,
        planner: PathPlanner,
        converter: PathCommandConverter,
        executor,
        debug: NavigatorDebug | None = None,
        notify_logger: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config
        self.photo_source = photo_source
        self.vision = vision
        self.localizer = localizer
        self.planner = planner
        self.converter = converter
        self.executor = executor
        self.debug = debug
        self.notify_logger = notify_logger

    async def run(self) -> NavigationResult:
        cfg = self.config
        bad_grid_count = 0
        last_cell: str | None = None
        # Cache of the maze structure (crop_bbox, walls, grid lines) from the
        # first successful frame; reused thereafter to skip the wall pipeline.
        cached_frame = None

        for step in range(cfg.max_steps):
            logger.info(f"\n========== STEP {step} ==========")

            img_bytes = await self.photo_source("navigator")
            if img_bytes is None:
                logger.error("[ERROR] No image received")
                self._save_debug(step, image=None, frame=None, robot_pose=None, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_IMAGE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="no image received",
                )

            logger.info(f"[IMAGE] Received {len(img_bytes)} bytes")

            if cached_frame is not None:
                frame_or_err = self.vision.analyze_with_cached_maze(
                    img_bytes, cached_frame,
                )
            else:
                frame_or_err = self.vision.analyze(img_bytes)

            if frame_or_err is VisionError.NO_IMAGE:
                logger.error("[ERROR] Image decode failed")
                self._save_debug(step, image=None, frame=None, robot_pose=None, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_IMAGE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="image decode failed",
                )

            if frame_or_err is VisionError.NO_MAZE:
                logger.error("[ERROR] Maze detection failed")
                # Decode the raw image so the composite still shows what the camera saw.
                try:
                    raw = Camera.decode_image(img_bytes)
                except Exception:
                    raw = None
                self._save_debug(step, image=raw, frame=None, robot_pose=None, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_MAZE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="no maze detected",
                )

            frame = frame_or_err
            logger.info(f"[IMAGE] Shape: {frame.image.shape}")
            logger.info(f"[MAZE] crop_bbox: {frame.maze['crop_bbox']}")
            logger.info(f"[GRID] x_lines: {frame.x_lines}")
            logger.info(f"[GRID] y_lines: {frame.y_lines}")
            logger.info(f"[GRID] rows: {frame.n_rows}, cols: {frame.n_cols}")
            logger.info(f"[OBSTACLES] {frame.obstacles}")

            # Grid validation only runs while we don't have a cached maze: once
            # we've locked one in, the structure is reused and trusted.
            if cached_frame is None:
                if frame.n_rows != cfg.expected_rows or frame.n_cols != cfg.expected_cols:
                    bad_grid_count += 1
                    logger.warning(
                        f"[ERROR] Invalid grid size. Expected "
                        f"{cfg.expected_rows}x{cfg.expected_cols}, "
                        f"got {frame.n_rows}x{frame.n_cols}"
                    )
                    self._save_debug(step, image=frame.image, frame=frame, robot_pose=None, path=None)
                    if bad_grid_count >= cfg.max_bad_grid_retries:
                        logger.error("[ERROR] Too many invalid grid detections")
                        return NavigationResult(
                            NavigationOutcome.FAILED_BAD_GRID,
                            last_cell=last_cell,
                            steps_taken=step,
                            message="too many bad grid detections",
                        )
                    continue

                # Grid is valid — cache the maze structure for subsequent steps.
                cached_frame = frame
                logger.info(
                    f"[CACHE] locked maze structure: {frame.n_rows}x{frame.n_cols}, "
                    f"crop={frame.maze['crop_bbox']}"
                )
                logger.info(
                    f"[CACHE] locked obstacle map: {len(frame.obstacles)} obstacles"
                )

            robot = self.localizer.locate(frame)

            # If aruco was not detected, retry with fresh photos (up to MAX_DETECT_ATTEMPTS total)
            for attempt in range(1, MAX_DETECT_ATTEMPTS):
                if robot is not None:
                    break
                logger.warning(f"[ROBOT] aruco missing, retry {attempt}/{MAX_DETECT_ATTEMPTS - 1}")
                await asyncio.sleep(RETRY_DELAY_S)

                # Fresh photo and fresh vision pass
                retry_bytes = await self.photo_source("navigator-retry")
                if retry_bytes is None:
                    continue
                if cached_frame is not None:
                    retry_frame_or_err = self.vision.analyze_with_cached_maze(
                        retry_bytes, cached_frame,
                    )
                else:
                    retry_frame_or_err = self.vision.analyze(retry_bytes)
                if isinstance(retry_frame_or_err, VisionError):
                    continue
                # Fresh detection on the new frame
                frame = retry_frame_or_err
                robot = self.localizer.locate(frame)

            # All retries exhausted, skip this step instead of killing the run
            if robot is None:
                logger.warning(
                    f"[ROBOT] aruco not detected after {MAX_DETECT_ATTEMPTS} attempts, "
                    f"skipping step {step}"
                )
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=None, path=None)
                continue

            current_cell = robot.cell
            current_angle = robot.angle_deg
            last_cell = current_cell

            logger.info(
                f"[ROBOT] cell={current_cell}, "
                f"angle={current_angle:.2f}, "
                f"raw_angle={robot.raw_angle_deg:.2f}, "
                f"center={robot.center}"
            )

            # Proximity check: count as reached if robot is within the configured
            # radius from the target cell center, even if still labelled in a neighbour cell.
            target_center = self._safe_cell_center_local(cfg.target_cell, frame)
            robot_local_pos_check = self._robot_local_position(frame, robot)
            distance_to_target_mm = None
            if target_center is not None:
                distance_to_target_mm = math.hypot(
                    target_center[0] - robot_local_pos_check[0],
                    target_center[1] - robot_local_pos_check[1],
                ) * cfg.mm_per_pixel
                logger.info(
                    f"[TARGET] {cfg.target_cell} distance={distance_to_target_mm:.0f} mm "
                    f"(radius={cfg.cell_reached_radius_mm:.0f} mm)"
                )

            within_radius = (
                distance_to_target_mm is not None
                and distance_to_target_mm <= cfg.cell_reached_radius_mm
            )

            if within_radius:
                logger.info("[SUCCESS] Reached destination")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.REACHED,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="reached target",
                )

            if target_center is None:
                logger.error(f"[ERROR] Target cell {cfg.target_cell} has no center")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_PATH,
                    last_cell=current_cell,
                    steps_taken=step,
                    message=f"invalid target cell {cfg.target_cell}",
                )

            robot_local_pos = self._robot_local_position(frame, robot)
            point_path = self.planner.plan_points(
                frame=frame,
                start_cell=current_cell,
                end_cell=cfg.target_cell,
                start_point=robot_local_pos,
                goal_point=target_center,
            )
            if point_path is None or len(point_path) < 1:
                logger.error("[ERROR] No valid mini-grid path")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_PATH,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="no valid mini-grid path",
                )

            waypoint_info = self._next_point_waypoint(robot_local_pos, point_path)
            if waypoint_info is None:
                logger.info("[SUCCESS] Reached mini-grid target")
                self._save_debug(
                    step,
                    image=frame.image,
                    frame=frame,
                    robot_pose=robot,
                    path=None,
                    point_path=point_path,
                )
                return NavigationResult(
                    NavigationOutcome.REACHED,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="reached target",
                )

            waypoint, snapped_current_node, snapped_distance_px = waypoint_info
            logger.info(
                f"[NAV] robot_center_full={robot.center} "
                f"robot_center_local={robot_local_pos} "
                f"snapped_current_node={snapped_current_node} "
                f"snapped_distance_px={snapped_distance_px:.1f} "
                f"selected_next_waypoint={waypoint}"
            )
            logger.info(f"[PATH] mini-grid length: {len(point_path)}")
            logger.info(f"[STEP] next mini waypoint: {waypoint}")
            commands = self.converter.points_to_commands(
                path=[robot_local_pos, waypoint],
                start_angle=current_angle,
            )
            self._inject_point_move_distances(commands)
            self._log_move_command(commands)

            logger.info(f"[COMMANDS] {commands}")

            # Save the composite BEFORE motion executes so the card reflects
            # what the navigator decided, not what the robot ended up doing.
            self._save_debug(
                step,
                image=frame.image,
                frame=frame,
                robot_pose=robot,
                path=None,
                point_path=point_path,
            )

            # Push the just-saved per-step path image to the logger.
            if self.notify_logger is not None and self.debug is not None:
                path_image = os.path.join(
                    self.debug.run_dir, "individuals", f"step_{step}", "path.jpg",
                )

                if os.path.exists(path_image):
                    await self.notify_logger(path_image)

            success = await self._execute_with_rotation_correction(
                commands, current_angle,
            )
            logger.info(f"[EXECUTION] success={success}")

            if not success:
                logger.error("[ERROR] Execution failed")
                return NavigationResult(
                    NavigationOutcome.FAILED_EXECUTION,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="motion execution failed",
                )

        logger.error("[FAIL] Max steps reached")
        return NavigationResult(
            NavigationOutcome.FAILED_MAX_STEPS,
            last_cell=last_cell,
            steps_taken=cfg.max_steps,
            message="max steps reached",
        )

    # Runs the path's commands, but each rotation goes through a measure-and-correct
    # loop: rotate, capture a fresh photo, check if the actual heading is within
    # cfg.rotation_tolerance_deg of the expected target, and if not, rotate by the
    # remaining error. Up to cfg.max_rotation_attempts rotations per command.
    async def _execute_with_rotation_correction(
        self,
        commands: list[dict],
        current_angle: float,
    ) -> bool:
        if not commands:
            logger.warning("No motion commands to execute.")
            return False

        # Tracks the heading the robot is supposed to have at this point in the
        # sequence. Starts from the robot's currently-detected angle and is
        # updated by each rotate command's intended delta.
        target_angle = current_angle

        for command in commands:
            action = command.get("action")

            if action == "rotate":
                delta = command.get("angle_deg")
                if delta is None:
                    logger.error(f"Missing angle_deg in command: {command}")
                    return False
                target_angle = (target_angle + float(delta) + 180.0) % 360.0 - 180.0
                ok = await self._rotate_with_correction(target_angle, float(delta))
                if not ok:
                    return False

            elif action == "move":
                ok = await self.executor.execute_command(command)
                if not ok:
                    return False

            else:
                logger.warning(f"Unknown motion command: {command}")
                return False

        return True

    async def _rotate_with_correction(
        self,
        target_angle: float,
        initial_delta: float,
    ) -> bool:
        cfg = self.config
        delta = initial_delta

        for attempt in range(cfg.max_rotation_attempts):
            logger.info(
                f"[ROT] attempt {attempt}: rotate {delta:+.1f} (target={target_angle:+.1f})"
            )
            ok = await self.executor.rotate(delta)
            if not ok:
                return False

            # Last allowed attempt -> commit, no point re-measuring.
            if attempt + 1 >= cfg.max_rotation_attempts:
                logger.info("[ROT] max attempts reached, proceeding to next command")
                return True

            actual = await self._measure_angle(label=f"rot-check-{attempt}")
            if actual is None:
                logger.warning(
                    "[ROT] could not measure heading; skipping further corrections"
                )
                return True

            error = (target_angle - actual + 180.0) % 360.0 - 180.0
            logger.info(
                f"[ROT] attempt {attempt}: actual={actual:+.1f}, error={error:+.1f}"
            )

            if abs(error) <= cfg.rotation_tolerance_deg:
                logger.info(f"[ROT] within tolerance ({cfg.rotation_tolerance_deg} deg)")
                return True

            # Rotate again by the residual error on the next iteration.
            delta = error

        return True

    # Captures one photo, runs the vision + localizer pipeline, and returns the
    # robot's currently-detected angle (or None if anything in the chain failed).
    async def _measure_angle(self, label: str) -> float | None:
        img_bytes = await self.photo_source(label)
        if img_bytes is None:
            return None
        frame_or_err = self.vision.analyze(img_bytes)
        if isinstance(frame_or_err, VisionError):
            return None
        robot = self.localizer.locate(frame_or_err)
        if robot is None:
            return None
        return robot.angle_deg

    def _inject_point_move_distances(self, commands: list[dict]) -> None:
        for cmd in commands:
            if cmd.get("action") != "move":
                continue
            distance_px = cmd.get("distance_px")
            if distance_px is None:
                continue
            # Scale by the fraction so the loop can re-localize between partial moves
            cmd["distance_mm"] = float(distance_px) * self.config.mm_per_pixel * self.config.move_distance_fraction

    @staticmethod
    def _robot_local_position(frame, robot) -> tuple[int, int]:
        x1, y1, _, _ = frame.maze["crop_bbox"]
        return (
            int(robot.center[0] - x1),
            int(robot.center[1] - y1),
        )

    @staticmethod
    def _next_point_waypoint(
        robot_local_pos: tuple[int, int],
        point_path: list[tuple[int, int]],
        reached_px: float = 5.0,
    ) -> tuple[tuple[int, int], tuple[int, int], float] | None:
        if not point_path:
            return None

        # The point path is rebuilt from the detected robot center on every
        # frame, so its first point is the current snapped mini-grid node. Using
        # the closest point anywhere in the path can skip ahead when the robot is
        # inside a blocked cell and physically near a later mini-route segment.
        snapped_current_node = point_path[0]
        snapped_distance_px = math.dist(robot_local_pos, snapped_current_node)

        for next_index in range(1, len(point_path)):
            waypoint = point_path[next_index]
            if math.dist(robot_local_pos, waypoint) > reached_px:
                return (waypoint, snapped_current_node, snapped_distance_px)

        if snapped_distance_px > reached_px:
            return (snapped_current_node, snapped_current_node, snapped_distance_px)

        return None

    @staticmethod
    def _log_move_command(commands: list[dict]) -> None:
        for cmd in commands:
            if cmd.get("action") == "move":
                logger.info(
                    f"[NAV] final_move_command from={cmd.get('from')} "
                    f"to={cmd.get('to')} distance_px={cmd.get('distance_px')} "
                    f"distance_mm={cmd.get('distance_mm')}"
                )
                return

    @staticmethod
    def _cell_rc(label: str | None) -> tuple[int, int] | None:
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
    def _cell_center_local(
        label: str | None,
        x_lines: list[int],
        y_lines: list[int],
    ) -> tuple[int, int] | None:
        if not label or len(label) < 2:
            return None
        try:
            col = int(label[1:]) - 1
        except ValueError:
            return None
        r = ord(label[0].upper()) - ord("A")
        if r < 0 or r >= len(y_lines) - 1:
            return None
        if col < 0 or col >= len(x_lines) - 1:
            return None
        cx = (x_lines[col] + x_lines[col + 1]) // 2
        cy = (y_lines[r] + y_lines[r + 1]) // 2
        return (cx, cy)

    def _safe_cell_center_local(self, label: str | None, frame) -> tuple[int, int] | None:
        rc = self._cell_rc(label)
        if rc is None:
            return None

        row, col = rc
        if row >= len(frame.y_lines) - 1 or col >= len(frame.x_lines) - 1:
            return None

        x_left = frame.x_lines[col]
        x_right = frame.x_lines[col + 1]
        y_top = frame.y_lines[row]
        y_bottom = frame.y_lines[row + 1]
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
        walls = frame.grid_walls.get(label, {})
        if (
            (col == 0 and walls.get("left"))
            or (col == len(frame.x_lines) - 2 and walls.get("right"))
            or (row == 0 and walls.get("bottom"))
            or (row == len(frame.y_lines) - 2 and walls.get("top"))
        ):
            cell_limit = max(0, min(x_right - x_left, y_bottom - y_top) // 3)
            inset = min(max(inset, self.config.safe_cell_inset_px), cell_limit)

        if inset == 0:
            return (cx, cy)

        if walls.get("left"):
            cx += inset
        if walls.get("right"):
            cx -= inset
        # MazeGridAnalyzer names these from the project angle convention:
        # "bottom" is the image-top edge, "top" is the image-bottom edge.
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
        max_inset = max(0, self.config.safe_cell_inset_px)
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
        start = min(max(self.config.safe_cell_inset_start_factor, 0.0), 0.99)
        if edge_factor <= start:
            return 0

        ramp = (edge_factor - start) / (1.0 - start)
        cell_limit = max(0, min(x_right - x_left, y_bottom - y_top) // 3)
        return min(int(round(max_inset * ramp)), cell_limit)

    def _save_debug(
        self,
        step,
        image,
        frame,
        robot_pose,
        path,
        point_path=None,
    ) -> None:
        if self.debug is None:
            return
        self.debug.save_step_composite(
            step=step,
            image=image,
            frame=frame,
            robot_pose=robot_pose,
            path=path,
            point_path=point_path,
        )
