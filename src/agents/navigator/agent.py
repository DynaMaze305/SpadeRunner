import logging

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
from common.config import TELEMETRY_JID, ROBOT_JID
from common.path_motion_executor import PathMotionExecutor
from common.run_dir import new_run_dir

from pathfinding.path_command_converter import PathCommandConverter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NavigatorAgent(agent.Agent):
    ENV_PREFIX = "NAVIGATOR"

    class NavigateBehaviour(behaviour.CyclicBehaviour):

        # Pushes the path of the latest per-step path image to the logger agent
        # via XMPP. The logger reads the file from the shared filesystem.
        async def notify_logger(self, image_path: str) -> None:
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = f"image {image_path}"
            await self.send(msg)
            logger.info(f"[NAV] notified {TELEMETRY_JID}: image {image_path}")

        async def run(self):
            cfg: NavigatorConfig = self.agent.cfg

            logger.info("[WAIT] Waiting for navigation start...")
            request = await self.receive(timeout=cfg.request_timeout_s)
            if request is None:
                return

            logger.info(f"[REQUEST] From: {request.sender} | Body: {request.body}")
            logger.info(f"[ROBOT JID] {ROBOT_JID}")

            if request.body != "request path":
                logger.warning(f"[WARN] Unknown request: {request.body}")
                return

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
            )
            localizer = RobotLocalizationStep(angle_offset_deg=cfg.angle_offset_deg)
            planner = PathPlanner()
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
                contour_padding_px=cfg.contour_demo_padding_px,
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

    async def setup(self):
        self.cfg = NavigatorConfig.from_env()
        if not self.cfg.target_cell:
            logger.error("[INIT] Navigator target cell is empty")
        logger.info(
            f"[INIT] Navigator ready: target={self.cfg.target_cell}, "
            f"max_steps={self.cfg.max_steps}, "
            f"grid={self.cfg.expected_rows}x{self.cfg.expected_cols}"
        )
        self.add_behaviour(self.NavigateBehaviour())
