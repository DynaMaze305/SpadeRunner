"""
    PWM calibration:
    Three calibration modes (ratio, rotation, distance) compute params from a
    sweep + linear regression and push them to the MotionAgent via the calibrate
    XMPP endpoint.
    Three verification modes (verify_ratio, verify_rotation, verify_distance)
    repeat the calibrated motion and report an L2 score.

    Inspired by the runner.py from Berk Buzcu
"""

import datetime
import logging
import os

from spade import agent, behaviour

from agents.calibrator.distance_analysis import (
    analyse_distance,
    analyse_distance_verify,
)
from agents.calibrator.log import log_row
from agents.calibrator.ratio_analysis import analyse_ratio, analyse_ratio_verify
from agents.calibrator.rotation_analysis import (
    analyse_rotation,
    analyse_rotation_verify,
)

from common.camera_client import CameraClient
from common.config import ARUCO_ID
from common.motion_client import MotionClient
from common.run_dir import new_run_dir

from vision.aruco_detector import ArucoDetector


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# selected at launch via env var
# valid: ratio | rotation | distance | verify_ratio | verify_rotation | verify_distance
CALIBRATION_MODE = os.getenv("CALIBRATION_MODE", "ratio")

CALIBRATION_DIR = "calibration_photos"


# ratio calibration: sweep ratios at a fixed short distance
RATIOS = [0.99, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05]
RATIO_DISTANCE_MM = 100
RATIO_PWM = 20

# rotation calibration: sweep durations at fixed pwm + ratio
ROTATION_DURATIONS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
ROTATION_PWM = 15
ROTATION_RATIO = 1.05

# distance calibration: sweep durations at fixed pwm + ratio
DISTANCE_DURATIONS = [0.5, 1.0, 1.5, 2.0]
DISTANCE_PWM = 15
DISTANCE_RATIO = 0.0

# verifications
VERIFY_RATIO_TRIALS = 5
VERIFY_DISTANCE_TRIALS = 5
VERIFY_DISTANCE_MM = 200
VERIFY_ROTATION_CYCLES = 4   # each cycle = +90 then -90, so 8 moves total
VERIFY_ROTATION_ANGLE = 90


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
            aruco = ArucoDetector()
            pose = aruco.detect_qr_angle_pose(image_path, ARUCO_ID)
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

        # sweep ratios at fixed short distance, fit alpha vs ratio,
        # send the zero-crossing as the calibrated forward / backward ratio
        async def run_ratio_calibration(self):
            logger.info(
                f"mode: ratio — distance={RATIO_DISTANCE_MM}mm, "
                f"ratios={RATIOS}, pwm={RATIO_PWM}"
            )

            for ratio in RATIOS:
                for direction in (1, -1):
                    distance = RATIO_DISTANCE_MM * direction
                    if not await self.motion.command_move(distance, None, RATIO_PWM, ratio):
                        return
                    if await self.calibrate_rot_pos(
                        target_angle=0.0, pwm=RATIO_PWM,
                        target_distance=distance, ratio=ratio,
                    ) is None:
                        return

            fwd_ratio, bwd_ratio = analyse_ratio(self.run_dir)

            if fwd_ratio is not None:
                await self.motion.command_calibrate("ratio_forward", fwd_ratio)
            if bwd_ratio is not None:
                await self.motion.command_calibrate("ratio_backward", bwd_ratio)

        # sweep durations CW + CCW, fit angle vs duration,
        # send (slope, intercept) for the positive / negative rotation models
        async def run_rotation_calibration(self):
            logger.info(
                f"mode: rotation — durations={ROTATION_DURATIONS}, "
                f"pwm={ROTATION_PWM}, ratio={ROTATION_RATIO}"
            )

            for duration in ROTATION_DURATIONS:
                for direction in (1, -1):
                    signed_duration = duration * direction
                    if not await self.motion.command_rotation(
                        None, signed_duration, ROTATION_PWM, ROTATION_RATIO
                    ):
                        return
                    if await self.calibrate_rot_pos(
                        duration=signed_duration, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    ) is None:
                        return

            pos_slope, pos_intercept, neg_slope, neg_intercept = analyse_rotation(
                self.run_dir
            )

            await self.motion.command_calibrate("positive", pos_slope, pos_intercept)
            await self.motion.command_calibrate("negative", neg_slope, neg_intercept)

        # sweep durations forward + backward, fit distance(mm) vs duration,
        # send (slope, intercept) for the forward / backward distance models
        async def run_distance_calibration(self):
            logger.info(
                f"mode: distance — durations={DISTANCE_DURATIONS}, "
                f"pwm={DISTANCE_PWM}, ratio={DISTANCE_RATIO}"
            )

            for duration in DISTANCE_DURATIONS:
                for direction in (1, -1):
                    signed_duration = duration * direction
                    if not await self.motion.command_move(
                        None, signed_duration, DISTANCE_PWM, DISTANCE_RATIO
                    ):
                        return
                    if await self.calibrate_rot_pos(
                        duration=signed_duration, pwm=DISTANCE_PWM, ratio=DISTANCE_RATIO,
                    ) is None:
                        return

            fwd_slope, fwd_intercept, bwd_slope, bwd_intercept = analyse_distance(
                self.run_dir
            )

            await self.motion.command_calibrate("forward", fwd_slope, fwd_intercept)
            await self.motion.command_calibrate("backward", bwd_slope, bwd_intercept)

        # repeat 100 mm forward / backward N times, score = L2 of alpha angles
        async def run_ratio_verification(self):
            logger.info(
                f"mode: verify_ratio — {VERIFY_RATIO_TRIALS} cycles of "
                f"forward+backward {RATIO_DISTANCE_MM}mm"
            )

            for trial in range(VERIFY_RATIO_TRIALS):
                for direction in (1, -1):
                    distance = RATIO_DISTANCE_MM * direction
                    # ratio=None → bot uses its calibrated ratio_forward / ratio_backward
                    if not await self.motion.command_move(distance, None, RATIO_PWM, None):
                        return
                    if await self.calibrate_rot_pos(
                        target_angle=0.0, pwm=RATIO_PWM,
                        target_distance=distance, ratio=0.0,
                    ) is None:
                        return

            score = analyse_ratio_verify(self.run_dir)
            self._save_score(score)

        # alternate +90, -90 N cycles, score = L2 of (target - measured) angle errors
        async def run_rotation_verification(self):
            logger.info(
                f"mode: verify_rotation — {VERIFY_ROTATION_CYCLES} cycles of "
                f"+{VERIFY_ROTATION_ANGLE} then -{VERIFY_ROTATION_ANGLE}"
            )

            for cycle in range(VERIFY_ROTATION_CYCLES):
                for direction in (1, -1):
                    signed_angle = VERIFY_ROTATION_ANGLE * direction
                    # duration=0 → bot derives duration from its calibrated rotation model
                    if not await self.motion.command_rotation(
                        signed_angle, 0, ROTATION_PWM, ROTATION_RATIO
                    ):
                        return
                    if await self.calibrate_rot_pos(
                        target_angle=signed_angle, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    ) is None:
                        return

            score = analyse_rotation_verify(self.run_dir)
            self._save_score(score)

        # repeat 200 mm forward / backward N times, score = L2 of distance errors (mm)
        async def run_distance_verification(self):
            logger.info(
                f"mode: verify_distance — {VERIFY_DISTANCE_TRIALS} cycles of "
                f"forward+backward {VERIFY_DISTANCE_MM}mm"
            )

            for trial in range(VERIFY_DISTANCE_TRIALS):
                for direction in (1, -1):
                    distance = VERIFY_DISTANCE_MM * direction
                    # duration=None and ratio=None → bot uses its calibrated values
                    if not await self.motion.command_move(distance, None, DISTANCE_PWM, None):
                        return
                    if await self.calibrate_rot_pos(
                        target_distance=distance, pwm=DISTANCE_PWM,
                    ) is None:
                        return

            score = analyse_distance_verify(self.run_dir)
            self._save_score(score)

        # helper function to save the score into a txt file
        def _save_score(self, score):
            score_path = os.path.join(self.run_dir, "score.txt")
            with open(score_path, "w") as f:
                f.write(f"{score:.4f}\n")
            logger.info(f"saved score to {score_path}")

        # main entry point
        async def run(self):
            self.camera = CameraClient(self)
            self.motion = MotionClient(self)

            # Setting up the directories
            self.run_dir, run_id = new_run_dir(CALIBRATION_DIR, "calibration")
            self.run_csv = os.path.join(self.run_dir, f"{CALIBRATION_MODE}.csv")
            logger.info(f"calibration run {run_id} ({CALIBRATION_MODE}) writing to {self.run_dir}")

            # Increment for naming
            self.step_id = 0

            # initial reference frame
            if await self.calibrate_rot_pos(target_angle=0.0, pwm=0) is None:
                return

            submodes = {
                "ratio": self.run_ratio_calibration,
                "rotation": self.run_rotation_calibration,
                "distance": self.run_distance_calibration,
                "verify_ratio": self.run_ratio_verification,
                "verify_rotation": self.run_rotation_verification,
                "verify_distance": self.run_distance_verification,
            }
            runner = submodes.get(CALIBRATION_MODE)
            if runner is None:
                logger.error(
                    f"unknown CALIBRATION_MODE '{CALIBRATION_MODE}', valid: {list(submodes)}"
                )
                return
            await runner()

        async def setup(self):
            pass

    async def setup(self):
        logger.info("calibrator agent ready")
        self.add_behaviour(self.CalibrateBehaviour())
