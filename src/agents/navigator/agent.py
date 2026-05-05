import asyncio
import base64
import json
import time
import cv2
import logging
import os

from spade import agent, behaviour
from spade.message import Message

from agents.navigator.config import NavigatorConfig
from agents.navigator.debug import NavigatorDebug
from agents.navigator.localization import RobotLocalizationStep
from agents.navigator.orchestrator import NavigationOrchestrator
from agents.navigator.planner import PathPlanner
from agents.navigator.result import NavigationOutcome
from agents.navigator.vision_pipeline import MazeVisionPipeline

from common.camera_client import CameraClient
from common.config import TELEMETRY_JID, ROBOT_JID, PAUSE_TIME
from common.path_motion_executor import PathMotionExecutor
from common.run_dir import new_run_dir

from pathfinding.path_command_converter import PathCommandConverter
from pathfinding.mini_grid_planner import MiniGridPlanner


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NavigatorAgent(agent.Agent):
    ENV_PREFIX = "NAVIGATOR"

    def __init__(self, jid, password, verify_security = False):
        super().__init__(jid, password, verify_security)
        self.current_navigator = None

    class NavigatorListenner(behaviour.CyclicBehaviour):
        async def runt(self):
            cfg: NavigatorConfig = self.agent.cfg

            logger.info("[WAIT] Waiting for navigation start...")
            request = await self.receive(timeout=cfg.request_timeout_s)
            if request is None:
                return

            logger.info(f"[REQUEST] From: {request.sender} | Body: {request.body}")
            logger.info(f"[ROBOT JID] {ROBOT_JID}")

            if request.body == "penality":
                self.agent.paused = True
                self.inform_penality()
                return

            if request.body == "request path" and self.agent.current_navigator is None:
                self.agent.current_navigator = self.agent.NavigateBehaviour()
                self.agent.add_behaviour(self.agent.current_navigator)

        async def inform_penality(self):
            msg = Message(to= ROBOT_JID)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("emergency","penality")
            msg.body = "penality"
            await self.send(msg)

    class NavigateBehaviour(behaviour.OneShotBehaviour):

        # Pushes the path of the latest per-step path image to the logger agent
        # via XMPP. The logger reads the file from the shared filesystem.
        async def notify_logger(self, image_path: str) -> None:
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            # Load image
            img = cv2.imread(image_path)
            _, buf = cv2.imencode(".jpg", img)
            b64 = base64.b64encode(buf).decode("utf-8")

            data = {
                "type": "image_path",
                "bot": str(self.agent.jid),
                "ts": time.time(),
                "data": b64
            }

            msg.body = json.dumps(data)
            await self.send(msg)
            logger.info(f"[NAV] notified {TELEMETRY_JID}: image {image_path}")

        async def run(self):
            if self.agent.paused:
                await asyncio.sleep(PAUSE_TIME)
                self.agent.paused = False

            logger.info("[START] Navigation requested")
            logger.info(
                f"[CONFIG] target_cell={cfg.target_cell}, max_steps={cfg.max_steps}"
            )

            run_dir, run_id = new_run_dir(
                cfg.photos_dir, "navigation", with_timestamp=False,
            )
            logger.info(f"[RUN] Created run dir: {run_dir} (run_id={run_id})")

            camera = CameraClient(self)
            vision = MazeVisionPipeline(
                threshold_ratio=cfg.grid_threshold_ratio,
                min_gap=cfg.grid_min_gap,
                expected_rows=cfg.expected_rows,
                expected_cols=cfg.expected_cols,
                hardcoded_grid_enabled=cfg.hardcoded_grid_enabled,
                hardcoded_grid_x_fractions=cfg.hardcoded_grid_x_fractions,
                hardcoded_grid_y_fractions=cfg.hardcoded_grid_y_fractions,
                obstacle_hardcoded_grid_enabled=cfg.obstacle_hardcoded_grid_enabled,
                obstacle_hardcoded_grid_x_fractions=(
                    cfg.obstacle_hardcoded_grid_x_fractions
                ),
                obstacle_hardcoded_grid_y_fractions=(
                    cfg.obstacle_hardcoded_grid_y_fractions
                ),
            )
            localizer = RobotLocalizationStep(angle_offset_deg=cfg.angle_offset_deg)
            planner = PathPlanner(
                mini_grid_planner=MiniGridPlanner(
                    divisions=cfg.obstacle_mini_grid_divisions,
                    obstacle_margin_px=cfg.obstacle_avoidance_margin_px,
                    robot_margin_px=cfg.robot_clearance_margin_px,
                ),
            )
            converter = PathCommandConverter()
            executor = PathMotionExecutor(
                behaviour=self,
                robot_jid=ROBOT_JID,
                move_distance=cfg.move_distance,
                move_pwm=cfg.move_pwm,
                rotation_pwm=cfg.rotation_pwm,
                ratio=cfg.ratio,
                rotation_ratio=cfg.rotation_ratio,
            )
            debug = NavigatorDebug(
                run_dir=run_dir,
                grid_detector=vision.grid,
                localizer=localizer.localizer,
                obstacle_margin_px=cfg.obstacle_avoidance_margin_px,
                robot_margin_px=cfg.robot_clearance_margin_px,
                mini_grid_divisions=cfg.obstacle_mini_grid_divisions,
            )

            orch = NavigationOrchestrator(
                config=cfg,
                photo_source=camera.request_photo,
                vision=vision,
                localizer=localizer,
                planner=planner,
                converter=converter,
                executor=executor,
                debug=debug,
                notify_logger=self.notify_logger,
            )

            result = await orch.run()
            logger.info(
                f"[RESULT] outcome={result.outcome.name} "
                f"steps={result.steps_taken} last_cell={result.last_cell}"
            )

            reply = Message(to=ROBOT_JID)
            reply.set_metadata("performative", "response")
            reply.set_metadata("outcome", result.outcome.name)
            reply.body = (
                "navigation done"
                if result.outcome is NavigationOutcome.REACHED
                else "navigation failed"
            )
            await self.send(reply)
        
        async def on_end(self):
            self.agent.current_navigator = None

    async def setup(self):
        self.cfg = NavigatorConfig.from_env()
        logger.info(
            f"[INIT] Navigator ready: target={self.cfg.target_cell}, "
            f"max_steps={self.cfg.max_steps}, "
            f"grid={self.cfg.expected_rows}x{self.cfg.expected_cols}"
        )
        self.add_behaviour(self.NavigateBehaviour())
