import asyncio
import base64
import json
import time
import cv2
import logging
import re

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
from common.config import *
from common.path_motion_executor import PathMotionExecutor
from common.run_dir import new_run_dir

from pathfinding.path_command_converter import PathCommandConverter
from pathfinding.mini_grid_planner import MiniGridPlanner


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLOR_MAP = {
    "orange":   (255, 165, 0),
    "purple":   (128, 0, 128),
    "black" :   (0,   0,   0)
}

def parse_color_string(colors: str):
    match = re.findall(r"(?:start|end):([A-Za-z]+)", colors)
    if len(match) != 2:
        logging.warning(f"Invalide color format {colors}")
        return "black" "black"
    return match[0].lower(), match[1].lower()

def color_to_rgb(name: str):
    if name not in COLOR_MAP:
        logging.warning(f"Unknown color: {name}")
        return (0,0,0)
    return COLOR_MAP[name]

class NavigatorAgent(agent.Agent):
    ENV_PREFIX = "NAVIGATOR"

    def __init__(self, jid, password, verify_security = False):
        super().__init__(jid, password, verify_security)
        self.current_navigator = None
        self.current_requester = None
        self.racing = False
        self.racing_ready = False
        self.paired = False

    class NavigatorListenner(behaviour.CyclicBehaviour):
        async def run(self):
            cfg: NavigatorConfig = self.agent.cfg

            logger.info("[WAIT] Waiting for navigation start...")
            request = await self.receive(timeout=cfg.request_timeout_s)
            if request is None:
                return

            logger.info(f"[REQUEST] From: {request.sender} | Body: {request.body}")
            logger.info(f"[ROBOT JID] {ROBOT_JID}")

            if request.body == "penality":
                self.agent.paused = True
                await self.inform_penality()
                return

            if request.body == "request path" and self.agent.current_navigator is None:
                self.agent.current_navigator = self.agent.NavigateBehaviour()
                self.agent.current_requester = str(request.sender.bare())
                self.agent.add_behaviour(self.agent.current_navigator)
                return
            
            if request.body == "init_race" and not self.agent.racing and not self.agent.racing_ready:
                self.agent.racing = True
                await self.init_race()
                return
            
            if request.body.startswith("paired ") and self.agent.racing and not self.agent.racing_ready:
                self.agent.paired = True
                await self.update_leds(request.body.split(' ', 1)[1])
                await self.confirm_telemetry()
                return
            
            # if request.body.lower().startswith("executed command:") and self.agent.racing and self.agent.paired:
            if request.body == "ready_to_race" and self.agent.racing and self.agent.paired:
                self.agent.racing_ready = True
                await self.update_leds("start:black end:black")
                await self.ready_to_race()
                return
            
            if request.body == "Go!!" and self.agent.racing_ready and self.agent.current_navigator is not None:
                self.agent.current_navigator = self.agent.NavigateBehaviour()
                self.agent.current_requester = str(request.sender.bare())
                self.agent.add_behaviour(self.agent.current_navigator)
                return

            if request.body.startswith("Total race time: "):
                if self.agent.current_navigator is not None:
                    self.agent.current_navigator = None
                # Total race time: 106.057s
                await self.send_total_time(request.body.split(': ',1)[1])
                return
            
            if request.body.startswith("The race is finished! Your race time is: "):
                if self.agent.current_navigator is not None:
                    self.agent.current_navigator = None
                self.agent.racing = False
                self.agent.racing_ready = False
                self.agent.paired = False
                # The race is finished! Your race time is: 24.908s
                await self.send_race_time(request.body.split(': ',1)[1])
                return

            if request.body.startswith("Pairing failed:"):
                if self.agent.current_navigator is not None:
                    self.agent.current_navigator = None
                self.agent.racing = False
                self.agent.racing_ready = False
                self.agent.paired = False
                # The race is finished! Your race time is: 24.908s
                await self.confirm_telemetry()
                return

            return

        async def inform_penality(self):
            logger.info("Inform penality!")
            msg = Message(to= ROBOT_JID)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("emergency","penality")
            msg.body = "obstacles penality"
            await self.send(msg)
            self.agent.add_behaviour(self.agent.PenaltityTimer())

        async def init_race(self):
            logger.info("Init race!")
            msg = Message(to=TIMEKEEPER_JID)
            msg.set_metadata("performative", "request")
            msg.body = "Hello TimeKeeper ! Please initialise a race."
            await self.send(msg)

        async def update_leds(self, colors: str):
            logger.info(f"Update LEDs; {colors}")
            start_color, end_color = parse_color_string(colors)

            r1, g1, b1 = color_to_rgb(start_color)
            r2, g2, b2 = color_to_rgb(end_color)

            msg = Message(to=PICAMERA_JID)
            msg.set_metadata("performative", "request")
            msg.body = f"leds 1 {r1} {g1} {b1} 2 {r2} {g2} {b2}"
            await self.send(msg)

        async def confirm_telemetry(self):
            logger.info("Confirm telemetry")
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = "race step done"
            await self.send(msg)

        async def ready_to_race(self):
            logger.info("Ready race!")
            msg = Message(to=TIMEKEEPER_JID)
            msg.set_metadata("performative", "request")
            msg.body = "I'm ready to race !"
            await self.send(msg)

        async def send_total_time(self, time: str):
            logger.info(f"Total time: {time}")
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps({
                "type": "total_time",
                "bot":  ROBOT_FILTRE,
                "ts":   0,
                "data": {"total_time": time}
            })
            await self.send(msg)

        async def send_race_time(self, time: str):
            logger.info(f"Total time: {time}")
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps({
                "type": "race_time",
                "bot":  ROBOT_FILTRE,
                "ts":   0,
                "data": {"race_time": time}
            })
            await self.send(msg)
            self.confirm_telemetry()

    class NavigateBehaviour(behaviour.OneShotBehaviour):
        async def on_start(self):
            logger.info("Launch navigation.")

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

            cfg: NavigatorConfig = self.agent.cfg
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
                navigator=self.agent,
                debug=debug,
                notify_logger=self.notify_logger,
            )

            result = await orch.run()
            logger.info(
                f"[RESULT] outcome={result.outcome.name} "
                f"steps={result.steps_taken} last_cell={result.last_cell}"
            )

            reply = Message(to=self.agent.current_requester)
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


    class PenaltityTimer(behaviour.OneShotBehaviour):
        async def run(self):
            await asyncio.sleep(PAUSE_TIME)
            logger.info("Penality navigator")
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = "penality done"
            await self.send(msg)

    async def setup(self):
        self.cfg = NavigatorConfig.from_env()
        self.paused = False
        logger.info(
            f"[INIT] Navigator ready: target={self.cfg.target_cell}, "
            f"max_steps={self.cfg.max_steps}, "
            f"grid={self.cfg.expected_rows}x{self.cfg.expected_cols}"
        )
        logger.info("TEST################")
        self.add_behaviour(self.NavigatorListenner())

        logger.info("TEST################")
