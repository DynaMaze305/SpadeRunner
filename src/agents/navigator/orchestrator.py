from __future__ import annotations

import datetime
import logging
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

from common.photo_io import save_bytes
from pathfinding.path_command_converter import PathCommandConverter


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
        photo_saver: Callable[..., Awaitable[str]] = save_bytes,
    ) -> None:
        self.config = config
        self.photo_source = photo_source
        self.vision = vision
        self.localizer = localizer
        self.planner = planner
        self.converter = converter
        self.executor = executor
        self.debug = debug
        self.photo_saver = photo_saver

    async def run(self) -> NavigationResult:
        cfg = self.config
        bad_grid_count = 0
        last_cell: str | None = None

        for step in range(cfg.max_steps):
            logger.info(f"\n========== STEP {step} ==========")

            img_bytes = await self.photo_source("navigator")
            if img_bytes is None:
                logger.error("[ERROR] No image received")
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_IMAGE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="no image received",
                )

            logger.info(f"[IMAGE] Received {len(img_bytes)} bytes")

            timestamp = datetime.datetime.now().strftime("%H%M%S")
            await self.photo_saver(
                img_bytes,
                f"step_{step}_{timestamp}.jpg",
                cfg.photos_dir,
            )

            frame = self.vision.analyze(img_bytes)

            if frame is VisionError.NO_IMAGE:
                logger.error("[ERROR] Image decode failed")
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_IMAGE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="image decode failed",
                )
            if frame is VisionError.NO_MAZE:
                logger.error("[ERROR] Maze detection failed")
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_MAZE,
                    last_cell=last_cell,
                    steps_taken=step,
                    message="no maze detected",
                )

            logger.info(f"[IMAGE] Shape: {frame.image.shape}")
            logger.info(f"[MAZE] crop_bbox: {frame.maze['crop_bbox']}")
            logger.info(f"[GRID] x_lines: {frame.x_lines}")
            logger.info(f"[GRID] y_lines: {frame.y_lines}")
            logger.info(f"[GRID] rows: {frame.n_rows}, cols: {frame.n_cols}")

            if frame.n_rows != cfg.expected_rows or frame.n_cols != cfg.expected_cols:
                bad_grid_count += 1
                logger.warning(
                    f"[ERROR] Invalid grid size. Expected "
                    f"{cfg.expected_rows}x{cfg.expected_cols}, "
                    f"got {frame.n_rows}x{frame.n_cols}"
                )
                if bad_grid_count >= cfg.max_bad_grid_retries:
                    logger.error("[ERROR] Too many invalid grid detections")
                    return NavigationResult(
                        NavigationOutcome.FAILED_BAD_GRID,
                        last_cell=last_cell,
                        steps_taken=step,
                        message="too many bad grid detections",
                    )
                continue

            robot = self.localizer.locate(frame)

            if self.debug is not None:
                self.debug.save_for_step(step=step, frame=frame, robot_pose=robot)

            if robot is None:
                logger.error("[ERROR] Robot detection failed: no ArUco pose")
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
                return NavigationResult(
                    NavigationOutcome.REACHED,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="reached target",
                )

            path = self.planner.plan(frame, current_cell, cfg.target_cell)
            if path is None or len(path) < 2:
                logger.error("[ERROR] No valid path")
                return NavigationResult(
                    NavigationOutcome.FAILED_NO_PATH,
                    last_cell=current_cell,
                    steps_taken=step,
                    message="no valid path",
                )

            logger.info(f"[PATH] full: {path}")
            logger.info(f"[PATH] length: {len(path)}")

            next_step = path[: cfg.lookahead]
            logger.info(f"[STEP] next_step: {next_step}")

            commands = self.converter.path_to_commands(
                path=next_step,
                start_angle=current_angle,
            )
            logger.info(f"[COMMANDS] {commands}")

            success = await self.executor.execute_commands(commands)
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
