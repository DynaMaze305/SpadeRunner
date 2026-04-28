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
from common.config import ROBOT_JID
from common.path_motion_executor import PathMotionExecutor
from common.photo_io import save_bytes

from pathfinding.path_command_converter import PathCommandConverter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NavigatorAgent(agent.Agent):
    ENV_PREFIX = "NAVIGATOR"

    class NavigateBehaviour(behaviour.CyclicBehaviour):

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
            )
            debug = NavigatorDebug(
                photos_dir=cfg.photos_dir,
                grid_detector=vision.grid,
                localizer=localizer.localizer,
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
                photo_saver=save_bytes,
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
        logger.info(
            f"[INIT] Navigator ready: target={self.cfg.target_cell}, "
            f"max_steps={self.cfg.max_steps}, "
            f"grid={self.cfg.expected_rows}x{self.cfg.expected_cols}"
        )
        self.add_behaviour(self.NavigateBehaviour())
