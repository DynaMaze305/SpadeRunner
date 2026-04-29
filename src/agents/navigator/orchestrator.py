from __future__ import annotations

import logging
import math
import os
from typing import Awaitable, Callable, Optional

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

            robot = self.localizer.locate(frame)

            if robot is None:
                logger.error("[ERROR] Robot detection failed: no ArUco pose")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=None, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_ROBOT,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="no robot detected",
                )

            current_cell = robot.cell
            current_angle = robot.angle_deg
            last_cell = current_cell

            logger.info(
                f"[ROBOT] cell={current_cell}, "
                f"angle={current_angle:.2f}, "
                f"raw_angle={robot.raw_angle_deg:.2f}, "
                f"center={robot.center}"
            )

            if current_cell == cfg.target_cell:
                logger.info("[SUCCESS] Reached destination")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.REACHED,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="reached target",
                )

            path = self.planner.plan(frame, current_cell, cfg.target_cell)
            if path is None or len(path) < 2:
                logger.error("[ERROR] No valid path")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_PATH,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="no valid path",
                )

            logger.info(f"[PATH] full: {path}")
            logger.info(f"[PATH] length: {len(path)}")

            next_step_cells = path[: cfg.lookahead]
            logger.info(f"[STEP] next_step: {next_step_cells}")

            commands = self.converter.path_to_commands(
                path=next_step_cells,
                start_angle=current_angle,
            )
            logger.info(f"[COMMANDS] {commands}")

            # Annotate move commands with the actual mm distance derived from the
            # current camera frame, so the executor sends a per-step distance
            # instead of always using cfg.move_distance.
            self._inject_move_distances(commands, frame, robot)

            # Save the composite BEFORE motion executes so the card reflects
            # what the navigator decided, not what the robot ended up doing.
            self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=path)

            # Push the just-saved per-step path image to the logger.
            if self.notify_logger is not None and self.debug is not None:
                path_image = os.path.join(
                    self.debug.run_dir, "individuals", f"step_{step}", "path.jpg",
                )
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

    # Mutates each "move" command in `commands` to add `distance_mm`. The first
    # move is measured from the robot's actual pixel position; subsequent moves
    # chain through cell centres.
    def _inject_move_distances(
        self,
        commands: list[dict],
        frame,
        robot,
    ) -> None:
        if not commands:
            return

        x1, y1, _, _ = frame.maze["crop_bbox"]
        current_pos = (
            int(robot.center[0] - x1),
            int(robot.center[1] - y1),
        )
        mm_per_pixel = self.config.mm_per_pixel

        for cmd in commands:
            if cmd.get("action") != "move":
                continue
            target_pos = self._cell_center_local(
                cmd.get("to"), frame.x_lines, frame.y_lines,
            )
            if target_pos is None:
                continue
            distance_px = math.hypot(
                target_pos[0] - current_pos[0],
                target_pos[1] - current_pos[1],
            )
            cmd["distance_mm"] = distance_px * mm_per_pixel
            current_pos = target_pos

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

    def _save_debug(self, step, image, frame, robot_pose, path) -> None:
        if self.debug is None:
            return
        self.debug.save_step_composite(
            step=step,
            image=image,
            frame=frame,
            robot_pose=robot_pose,
            path=path,
        )
