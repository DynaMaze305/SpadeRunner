"""
    PWM calibration:
    1) request a photo from the ceiling camera (initial reference)
    2) for each (target_angle, pwm) pair:
       - command robot: rotation <signed_target_angle> <pwm>
         (robot derives duration internally from its target deg/sec)
       - request a new photo
       - measure marker angle, compute delta vs previous, log row

    Inspired by the runner.py from Berk Buzcu
"""

import os
import logging
import datetime

from spade import agent, behaviour

from vision.qr_detector import detect_qr_angle_pose
from agents.calibrator.log import log_row
from common.camera_client import CameraClient
from common.config import ARUCO_ID
from common.motion_client import MotionClient
from common.run_dir import new_run_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# selected at launch via env var (rotation | ratio | speed | curve)
CALIBRATION_MODE = os.getenv("CALIBRATION_MODE", "ratio")
LOCKED_RATIO = float(os.getenv("RATIO", "1.0"))

CALIBRATION_DIR = "calibration_photos"

# toggle to run every calibration loop forward + backward, or forward only
BI_DIRECTION = True
DIRECTIONS = (1, -1) if BI_DIRECTION else (1,)

# rotation mode
# TARGET_ANGLES = [30, 60, 90, 120, 180, -30, -60, -90, -120, -180]
# PWM_VALUES = [10, 15, 20, 25, 30]

ROTATION_DURATIONS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
ROTATION_PWM = 15
ROTATION_RATIO = 1.05

# rotation verification mode
# VERIFICATION_ANGLES = [90, 90, 90, 90, 90]
# VERIFICATION_ANGLES = [180, 180, 180, 180, 180]
VERIFICATION_ANGLES = [30] * 2

# ratio mode
FIXED_DISTANCE = 200
DURATION = None
RATIOS = [0.99, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05]
FIXED_PWM = 20

# speed mode
SPEED_DURATION = 2
SPEED_PWM = 20

# curve mode
CURVE_PWM = 15
CURVE_DURATIONS = [1.0]
CURVE_RATIO = 1.02

# distance mode
DISTANCES = [200, 150, 200]
DISTANCES_RATIO = 1.01
DISTANCES_PWM = 15


# repeats the whole calibration loop N times to gather more samples
MULTIPLY = 1

class CalibratorAgent(agent.Agent):
    ENV_PREFIX = "CALIBRATOR"

    class CalibrateBehaviour(behaviour.OneShotBehaviour):

        # Requests a photo, measures the rotation + position, logs the row
        async def calibrate_rot_pos(self, target_angle: float = 0.0, pwm: int = 0,
                                    target_distance: float = 0.0, duration: int = 0,
                                    ratio: float = 0.0):

            # Requests a phot through the helper function
            step_label = f"step {self.step_id}"
            target_path = os.path.join(self.run_dir, f"{self.step_id}.jpg")
            capture = await self.camera.capture(step_label, target_path)

            if capture is None:
                logger.error(f"NO image for step {self.step_id}")
                return None
            _, image_path = capture

            now = datetime.datetime.now()
            timestamp = now.isoformat(timespec="seconds")

            # Get the robot rotation + position using the vision lib
            pose = detect_qr_angle_pose(image_path, ARUCO_ID)
            if pose is None:
                logger.warning(f"[step {self.step_id}] no marker detected — NaN")
                measured_angle = float("nan")
                x = float("nan")
                y = float("nan")
                pose = {"angle_deg": measured_angle, "x": x, "y": y}
            else:
                measured_angle = pose["angle_deg"]
                x = pose["x"]
                y = pose["y"]
                logger.info(
                    f"[step {self.step_id}] target={target_angle:+.1f} pwm={pwm} "
                    f"duration={duration} ratio={ratio} "
                    f"measured={measured_angle:+.2f} x={x:+.1f} y={y:+.1f}"
                )

            log_row(
                self.run_csv,
                timestamp,
                image_path,
                target_angle,
                pwm,
                measured_angle,
                target_distance,
                duration,
                ratio,
                x, y,
            )
            self.step_id += 1
            return pose

        # moves back and forth a fixed distance to test the left/right ratio
        async def run_ratio_calibration(self):
            # overriding example
            # RATIOS = [x / 100 for x in range(100, 105)]

            logger.info(f"mode: ratio — distance={FIXED_DISTANCE}, ratios={RATIOS}, duration={DURATION}, pwm={FIXED_PWM}")

            for ratio in RATIOS:
                # forward then backward so the robot returns to the starting point
                for direction in DIRECTIONS:
                    distance = FIXED_DISTANCE * direction
                    if not await self.motion.command_move(distance, DURATION, FIXED_PWM, ratio):
                        return
                    if await self.calibrate_rot_pos(
                        target_angle=0.0, pwm=FIXED_PWM,
                        target_distance=distance, duration=DURATION, ratio=ratio,
                    ) is None:
                        return

        # single move with fixed ratio + duration, measure marker position to calculate the speed approximately
        async def run_speed_calibration(self):
            logger.info(f"mode: speed — ratio={LOCKED_RATIO}, duration={SPEED_DURATION}, pwm={SPEED_PWM}")
            for direction in DIRECTIONS:
                duration = SPEED_DURATION * direction
                if not await self.motion.command_move(None, duration, SPEED_PWM, LOCKED_RATIO):
                    return
                if await self.calibrate_rot_pos(
                    duration=duration, pwm=SPEED_PWM, ratio=LOCKED_RATIO,
                ) is None:
                    return

        # tries a range of duration to build a duration/distance curve with a fixed ratio
        async def run_curve_calibration(self):
            logger.info(f"mode: curve — ratio={CURVE_RATIO}, durations={CURVE_DURATIONS}, pwm={CURVE_PWM}")
            for _ in range(MULTIPLY):
                for duration in CURVE_DURATIONS:
                    for direction in DIRECTIONS:
                        signed_duration = duration * direction
                        if not await self.motion.command_move(None, signed_duration, CURVE_PWM, CURVE_RATIO):
                            return
                        if await self.calibrate_rot_pos(
                            duration=signed_duration, pwm=CURVE_PWM, ratio=CURVE_RATIO,
                        ) is None:
                            return

        # tries a range of distances forward then backward with a fixed ratio
        async def run_distance_calibration(self):
            logger.info(f"mode: distance — distances={DISTANCES}, pwm={DISTANCES_PWM}, ratio={DISTANCES_RATIO}")
            for _ in range(MULTIPLY):
                for distance in DISTANCES:
                    for direction in DIRECTIONS:
                        signed_distance = distance * direction
                        if not await self.motion.command_move(signed_distance, None, DISTANCES_PWM, DISTANCES_RATIO):
                            return
                        if await self.calibrate_rot_pos(
                            target_distance=signed_distance, pwm=DISTANCES_PWM, duration=None, ratio=DISTANCES_RATIO,
                        ) is None:
                            return

        # tries a range of durations at fixed pwm/ratio to build a duration/angle curve for the rotation
        async def run_rotation_calibration(self):
            logger.info(f"mode: rotation — durations={ROTATION_DURATIONS}, pwm={ROTATION_PWM}, ratio={ROTATION_RATIO}")
            for duration in ROTATION_DURATIONS:
                for direction in DIRECTIONS:
                    signed_duration = duration * direction
                    if not await self.motion.command_rotation(None, signed_duration, ROTATION_PWM, ROTATION_RATIO):
                        return
                    if await self.calibrate_rot_pos(
                        duration=signed_duration, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    ) is None:
                        return

        # replays a fixed list of target angles to check that the calibrated rotation model holds
        async def run_rotation_verification(self):
            logger.info(f"mode: rotation verification — angles={VERIFICATION_ANGLES}, pwm={ROTATION_PWM}, ratio={ROTATION_RATIO}")
            for angle in VERIFICATION_ANGLES:
                for direction in DIRECTIONS:
                    signed_angle = angle * direction
                    if not await self.motion.command_rotation(signed_angle, 0, ROTATION_PWM, ROTATION_RATIO):
                        return
                    pose = await self.calibrate_rot_pos(
                        target_angle=signed_angle, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    )
                    if pose is None:
                        return
                    logger.info(f"predicted: {signed_angle:+.1f} measured: {pose['angle_deg']:+.2f}")

        async def run(self):

            self.camera = CameraClient(self)
            self.motion = MotionClient(self)

            # Setting up the directories
            self.run_dir, run_id = new_run_dir(CALIBRATION_DIR, "calibration")
            self.run_csv = os.path.join(self.run_dir, f"{CALIBRATION_MODE}.csv")
            logger.info(f"calibration run {run_id} ({CALIBRATION_MODE}) writing to {self.run_dir}")

            # Increment if for naming
            self.step_id = 0

            # initial reference
            if await self.calibrate_rot_pos(target_angle=0.0, pwm=0) is None:
                return

            submodes = {
                "rotation": self.run_rotation_calibration,
                "rotation_verification": self.run_rotation_verification,
                "ratio": self.run_ratio_calibration,
                "speed": self.run_speed_calibration,
                "curve": self.run_curve_calibration,
                "distance": self.run_distance_calibration,
            }
            runner = submodes.get(CALIBRATION_MODE)
            if runner is None:
                logger.error(f"unknown CALIBRATION_MODE '{CALIBRATION_MODE}', valid: {list(submodes)}")
                return
            await runner()

        async def setup(self):
            pass

    async def setup(self):
        logger.info("calibrator agent ready")
        self.add_behaviour(self.CalibrateBehaviour())
