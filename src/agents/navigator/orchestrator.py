from __future__ import annotations

import asyncio
import logging
import math
import os
from typing import Awaitable, Callable, Optional

# ArUco retry settings — fresh photo + fresh detection up to N attempts
MAX_DETECT_ATTEMPTS = 3
RETRY_DELAY_S = 0.2

# Rotation recovery when the ArUco is missing after photo retries.
ARUCO_RECOVERY_ROTATIONS = 4
ARUCO_RECOVERY_ROTATE_DEG = 10.0
ARUCO_RECOVERY_SLEEP_S = 1.0

# Pause after a bypass move so we re-plan slowly.
BYPASS_RECHECK_S = 1.0

# Short wait when a stationary opponent leaves no route to target.
STATIONARY_OPP_WAIT_S = 1.0

from common.config import TARGET_ARUCO_ID

from agents.navigator.config import NavigatorConfig
from agents.navigator.debug import NavigatorDebug
from agents.navigator.enemy_detection import detect_enemies
from agents.navigator.localization import RobotLocalizationStep
from agents.navigator.opponent_predictor import (
    EMERGENCY_AVOIDANCE_DISTANCE_CELLS,
    find_bypass_cell,
    manhattan_cells,
    opponent_target_cell,
    predict_opponent_path,
)
from agents.navigator.planner import PathPlanner
from agents.navigator.result import NavigationOutcome, NavigationResult
from agents.navigator.vision_pipeline import (
    MazeVisionPipeline,
    VisionError,
)

from pathfinding.path_command_converter import PathCommandConverter
from vision.camera import Camera

from common.config import PAUSE_TIME

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
        navigator,
        executor,
        debug: NavigatorDebug | None = None,
        notify_logger: Callable[[str], Awaitable[None]] | None = None,
        boulder_picker: Callable[[dict[str, float]], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config
        self.photo_source = photo_source
        self.vision = vision
        self.localizer = localizer
        self.planner = planner
        self.converter = converter
        self.navigator_agent = navigator
        self.executor = executor
        self.debug = debug
        self.notify_logger = notify_logger
        self.boulder_picker = boulder_picker

        # Goal cell. Falls back to the configured value until the target ArUco
        # marker is detected in the first valid frame, then locked in.
        self.target_cell = config.target_cell
        self._target_detected = False

    async def run(self) -> NavigationResult:
        cfg = self.config
        bad_grid_count = 0
        last_cell: str | None = None
        latest_boulder_coordinates: list[tuple[int, int]] = []
        latest_boulder_positions_m: list[dict[str, float]] = []
        boulder_pick_requested = False
        # Cache of the maze structure (crop_bbox, walls, grid lines) from the
        # first successful frame; reused thereafter to skip the wall pipeline.
        cached_frame = None

        for step in range(cfg.max_steps):
            logger.info(f"\n========== STEP {step} ==========")
            if self.navigator_agent.paused:
                await asyncio.sleep(PAUSE_TIME)

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

            if not boulder_pick_requested and self.boulder_picker is not None:
                preflight_boulders = self.vision.detect_boulders_only(
                    img_bytes,
                    cached=cached_frame,
                )
                if not isinstance(preflight_boulders, VisionError):
                    preflight_positions_m = self._boulder_positions_m(
                        preflight_boulders,
                    )
                    if preflight_positions_m:
                        await self.boulder_picker(preflight_positions_m[0])
                        await asyncio.sleep(20)  
                        boulder_pick_requested = True
                        logger.info(
                            f"[BOULDERS] pick requested before obstacles/motion: "
                            f"{preflight_positions_m[0]}"
                        )

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
            latest_boulder_coordinates = frame.boulder_coordinates
            latest_boulder_positions_m = self._boulder_positions_m(
                latest_boulder_coordinates,
            )
            logger.info(f"[IMAGE] Shape: {frame.image.shape}")
            logger.info(f"[MAZE] crop_bbox: {frame.maze['crop_bbox']}")
            logger.info(f"[GRID] x_lines: {frame.x_lines}")
            logger.info(f"[GRID] y_lines: {frame.y_lines}")
            logger.info(f"[GRID] rows: {frame.n_rows}, cols: {frame.n_cols}")
            logger.info(f"[OBSTACLES] {frame.obstacles}")
            logger.info(f"[BOULDERS] coordinates={frame.boulder_coordinates}")
            logger.info(f"[BOULDERS] positions_m={latest_boulder_positions_m}")

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
                            boulder_coordinates=latest_boulder_coordinates,
                            boulder_positions_m=latest_boulder_positions_m,
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

            # Read the goal cell from the target ArUco marker on the first valid
            # frame. If the marker is not visible yet, retry on the next step.
            if not self._target_detected:
                detected = self.localizer.find_marker_cell(frame, TARGET_ARUCO_ID)
                if detected is not None:
                    self.target_cell = detected
                    self._target_detected = True
                    logger.info(
                        f"[TARGET] aruco {TARGET_ARUCO_ID} -> cell {detected}"
                    )
                else:
                    logger.warning(
                        f"[TARGET] aruco {TARGET_ARUCO_ID} not detected at step {step}, "
                        f"using fallback {self.target_cell}"
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
                latest_boulder_coordinates = frame.boulder_coordinates
                latest_boulder_positions_m = self._boulder_positions_m(
                    latest_boulder_coordinates,
                )
                robot = self.localizer.locate(frame)

            # Rotate slightly between photos to bring the ArUco back in view.
            if robot is None:
                logger.warning(
                    f"[ROBOT] aruco not detected after {MAX_DETECT_ATTEMPTS} "
                    f"photo attempts, entering rotation recovery"
                )
                for rot_attempt in range(1, ARUCO_RECOVERY_ROTATIONS + 1):
                    logger.info(
                        f"[ROBOT] recovery rotation {rot_attempt}/"
                        f"{ARUCO_RECOVERY_ROTATIONS}: "
                        f"+{ARUCO_RECOVERY_ROTATE_DEG:.0f} deg"
                    )
                    ok = await self.executor.rotate(ARUCO_RECOVERY_ROTATE_DEG)
                    if not ok:
                        logger.error(
                            "[ROBOT] rotation command failed during recovery"
                        )
                        break
                    await asyncio.sleep(ARUCO_RECOVERY_SLEEP_S)

                    recovery_bytes = await self.photo_source("navigator-recovery")
                    if recovery_bytes is None:
                        continue
                    if cached_frame is not None:
                        recovery_frame = self.vision.analyze_with_cached_maze(
                            recovery_bytes, cached_frame,
                        )
                    else:
                        recovery_frame = self.vision.analyze(recovery_bytes)
                    if isinstance(recovery_frame, VisionError):
                        continue
                    frame = recovery_frame
                    robot = self.localizer.locate(frame)
                    if robot is not None:
                        logger.info(
                            f"[ROBOT] aruco recovered after rotation {rot_attempt}"
                        )
                        break

            # Stop the run if rotation recovery also fails.
            if robot is None:
                logger.error(
                    f"[ROBOT] aruco still not detected after "
                    f"{ARUCO_RECOVERY_ROTATIONS} rotation recovery attempts, "
                    f"stopping navigator"
                )
                self._save_debug(
                    step, image=frame.image, frame=frame,
                    robot_pose=None, path=None,
                )
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_ROBOT,
                    last_cell=last_cell,
                    steps_taken=step,
                    message=(
                        f"aruco missing after {ARUCO_RECOVERY_ROTATIONS} "
                        f"rotation recovery attempts"
                    ),
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

            # Proximity check: count as reached if robot is within the configured
            # radius from the target cell center, even if still labelled in a neighbour cell.
            target_center = self._cell_center_local(self.target_cell, frame)
            robot_local_pos_check = self._robot_local_position(frame, robot)
            distance_to_target_mm = None
            if target_center is not None:
                distance_to_target_mm = math.hypot(
                    target_center[0] - robot_local_pos_check[0],
                    target_center[1] - robot_local_pos_check[1],
                ) * cfg.mm_per_pixel
                logger.info(
                    f"[TARGET] {self.target_cell} distance={distance_to_target_mm:.0f} mm "
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
                    boulder_coordinates=latest_boulder_coordinates,
                    boulder_positions_m=latest_boulder_positions_m,
                )

            if target_center is None:
                logger.error(f"[ERROR] Target cell {self.target_cell} has no center")
                self._save_debug(step, image=frame.image, frame=frame, robot_pose=robot, path=None)
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_PATH,
                    last_cell=current_cell,
                    steps_taken=step,
                    message=f"invalid target cell {self.target_cell}",
                    boulder_coordinates=latest_boulder_coordinates,
                    boulder_positions_m=latest_boulder_positions_m,
                )

            robot_local_pos = self._robot_local_position(frame, robot)

            # First detected enemy is treated as the opponent.
            enemies = detect_enemies(frame, self.vision.aruco)
            opponent = enemies[0] if enemies else None

            # Predict opponent path, or fall back to stationary one-cell.
            opponent_path: list[str] | None = None
            opp_target: str | None = None
            opp_has_target = False
            if opponent is not None:
                opp_target = opponent_target_cell(self.localizer, frame)
                if opp_target is not None:
                    opponent_path = predict_opponent_path(
                        frame, opponent.cell, opp_target,
                    )
                if opponent_path:
                    opp_has_target = True
                    logger.info(
                        f"[OPP] cell={opponent.cell} target={opp_target} "
                        f"path={opponent_path}"
                    )
                else:
                    # Stationary fallback when target ArUco is not visible.
                    opponent_path = [opponent.cell]
                    logger.info(
                        f"[OPP] no target ArUco, treating opponent at "
                        f"{opponent.cell} as a locked cell"
                    )

            # Hard-block opponent cell when stationary, plan honestly otherwise.
            stationary_block_cells: set[str] = set()
            if opponent is not None and not opp_has_target:
                stationary_block_cells = {opponent.cell}
            point_path = self.planner.plan_points(
                frame=frame,
                start_cell=current_cell,
                end_cell=self.target_cell,
                start_point=robot_local_pos,
                goal_point=target_center,
                extra_blocked_cells=stationary_block_cells,
            )

            # Emergency avoidance only fires for a moving opponent on our path.
            avoidance_path: list[str] | None = None
            in_avoidance = False
            opp_distance = (
                manhattan_cells(current_cell, opponent.cell)
                if opponent is not None else None
            )
            if (
                opp_has_target
                and point_path is not None
                and opponent is not None
                and opponent_path is not None
                and opp_distance is not None
                and opp_distance <= EMERGENCY_AVOIDANCE_DISTANCE_CELLS
                and opponent.cell in self._cells_in_point_path(point_path, frame)
            ):
                logger.warning(
                    f"[AVOID] opponent {opponent.cell} sits on our path "
                    f"(distance={opp_distance})"
                )
                # Pick the closest cell off the opponent path, reachable without going through them.
                bypass = find_bypass_cell(
                    frame, current_cell, opponent_path,
                    blocked_for_expansion={opponent.cell},
                )
                if bypass is not None and bypass != current_cell:
                    bypass_center = self._cell_center_local(bypass, frame)
                    if bypass_center is not None:
                        # Bypass plan also keeps the opponent cell as a wall.
                        bypass_pp = self.planner.plan_points(
                            frame=frame,
                            start_cell=current_cell,
                            end_cell=bypass,
                            start_point=robot_local_pos,
                            goal_point=bypass_center,
                            extra_blocked_cells={opponent.cell},
                        )
                        if bypass_pp and len(bypass_pp) >= 1:
                            point_path = bypass_pp
                            avoidance_path = self._cells_in_point_path(
                                bypass_pp, frame,
                            )
                            in_avoidance = True
                            logger.warning(
                                f"[AVOID] diverting to bypass cell "
                                f"{bypass} via {avoidance_path}"
                            )

            if point_path is None or len(point_path) < 1:
                # Short wait when a stationary opponent caused the failure.
                if opponent is not None and not opp_has_target:
                    wait_s = STATIONARY_OPP_WAIT_S
                else:
                    wait_s = cfg.path_blocked_wait_s
                logger.error(
                    "[NO PATH FOUND] PATH BLOCKED -- "
                    f"ROBOT STOPPED IN CELL {current_cell} -- "
                    f"WAITING {wait_s:.1f}s BEFORE RETRYING"
                )
                self._save_debug(
                    step,
                    image=frame.image,
                    frame=frame,
                    robot_pose=robot,
                    path=None,
                    enemies=enemies,
                    stopped_cell=current_cell,
                    opponent=opponent,
                    opponent_path=opponent_path,
                )
                if wait_s > 0:
                    await asyncio.sleep(wait_s)
                continue

            waypoint_info = self._next_point_waypoint(
                robot_local_pos,
                point_path,
                reached_px=cfg.mini_grid_waypoint_reached_px,
            )
            if waypoint_info is None:
                logger.info("[SUCCESS] Reached mini-grid target")
                self._save_debug(
                    step,
                    image=frame.image,
                    frame=frame,
                    robot_pose=robot,
                    path=None,
                    point_path=point_path,
                    enemies=enemies,
                    opponent=opponent,
                    opponent_path=opponent_path,
                    avoidance_path=avoidance_path,
                )
                return NavigationResult(
                    NavigationOutcome.REACHED,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="reached target",
                    boulder_coordinates=latest_boulder_coordinates,
                    boulder_positions_m=latest_boulder_positions_m,
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
                next_waypoint=waypoint,
                enemies=enemies,
                opponent=opponent,
                opponent_path=opponent_path,
                avoidance_path=avoidance_path,
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
                    boulder_coordinates=latest_boulder_coordinates,
                    boulder_positions_m=latest_boulder_positions_m,
                )

            # Pause after a bypass move before re-planning.
            if in_avoidance:
                logger.info(
                    f"[AVOID] sleeping {BYPASS_RECHECK_S:.1f}s before recheck"
                )
                await asyncio.sleep(BYPASS_RECHECK_S)

        logger.error("[FAIL] Max steps reached")
        return NavigationResult(
            NavigationOutcome.FAILED_MAX_STEPS,
            last_cell=last_cell,
            steps_taken=cfg.max_steps,
            message="max steps reached",
            boulder_coordinates=latest_boulder_coordinates,
            boulder_positions_m=latest_boulder_positions_m,
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
                # Settle now lives inside MotionClient so it applies to the
                # calibrator's direct motion calls too. No orchestrator-level
                # sleep needed.

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
            # Settle is handled inside MotionClient.command_rotation so the
            # calibrator's direct rotations get the same pause for free.

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

    def _boulder_positions_m(
        self,
        boulder_coordinates: list[tuple[int, int]],
    ) -> list[dict[str, float]]:
        meters_per_pixel = self.config.mm_per_pixel / 1000.0
        origin_x = self.config.arm_origin_px_x
        origin_y = self.config.arm_origin_px_y
        y_sign = -1.0 if self.config.arm_flip_y else 1.0

        return [
            {
                "x": round((x - origin_x) * meters_per_pixel, 6),
                "y": round((y - origin_y) * meters_per_pixel * y_sign, 6),
            }
            for x, y in boulder_coordinates
        ]

    @staticmethod
    def _robot_local_position(frame, robot) -> tuple[int, int]:
        x1, y1, _, _ = frame.maze["crop_bbox"]
        return (
            int(robot.center[0] - x1),
            int(robot.center[1] - y1),
        )

    # Aim at the current cell centre until reached, then advance to the next.
    @staticmethod
    def _next_point_waypoint(
        robot_local_pos: tuple[int, int],
        point_path: list[tuple[int, int]],
        reached_px: float = 2.0,
    ) -> tuple[tuple[int, int], tuple[int, int], float] | None:
        if not point_path:
            return None

        snapped_current_node = point_path[0]
        snapped_distance_px = math.dist(robot_local_pos, snapped_current_node)

        if snapped_distance_px > reached_px:
            return (point_path[0], snapped_current_node, snapped_distance_px)

        if len(point_path) >= 2:
            return (point_path[1], snapped_current_node, snapped_distance_px)

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

    def _cell_center_local(self, label: str | None, frame) -> tuple[int, int] | None:
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
        return ((x_left + x_right) // 2, (y_top + y_bottom) // 2)

    def _save_debug(
        self,
        step,
        image,
        frame,
        robot_pose,
        path,
        point_path=None,
        next_waypoint=None,
        enemies=None,
        stopped_cell=None,
        opponent=None,
        opponent_path=None,
        avoidance_path=None,
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
            enemies=enemies,
            next_waypoint=next_waypoint,
            stopped_cell=stopped_cell,
            opponent=opponent,
            opponent_path=opponent_path,
            avoidance_path=avoidance_path,
        )

    # Ordered unique cells visited by a pixel point_path.
    @staticmethod
    def _cells_in_point_path(point_path, frame) -> list[str]:
        if not point_path or frame is None:
            return []
        x_lines = frame.x_lines
        y_lines = frame.y_lines
        seen: set[str] = set()
        cells: list[str] = []
        for px, py in point_path:
            cell = NavigationOrchestrator._point_to_cell(px, py, x_lines, y_lines)
            if cell is not None and cell not in seen:
                seen.add(cell)
                cells.append(cell)
        return cells

    # Map a pixel coordinate to its cell label in the cropped frame.
    @staticmethod
    def _point_to_cell(
        px: float, py: float, x_lines: list[int], y_lines: list[int],
    ) -> str | None:
        import string
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
        if row is None or col is None or row >= len(string.ascii_uppercase):
            return None
        return f"{string.ascii_uppercase[row]}{col + 1}"
