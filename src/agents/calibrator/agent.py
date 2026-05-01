"""calibrator agent: runs sweeps + regressions, or repeats moves to score the calibration
Inspired by the runner.py from Berk Buzcu
"""

import asyncio
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

# detection retry: tries N times then aborts after K consecutive misses
MAX_DETECT_ATTEMPTS = 3
RETRY_DELAY_S = 0.2
MAX_CONSECUTIVE_FAILURES = 2


class CalibratorAgent(agent.Agent):
    ENV_PREFIX = "CALIBRATOR"

    class CalibrateBehaviour(behaviour.OneShotBehaviour):

        # retries fresh capture + aruco detection a few times
        async def _capture_and_detect(self):
            step_label = f"step {self.step_id}"
            target_path = os.path.join(self.run_dir, f"{self.step_id}.jpg")
            image_path = None

            # blur is the usual cause, so retrying with a new photo helps
            for attempt in range(MAX_DETECT_ATTEMPTS):

                # asks the camera agent for a fresh photo
                capture = await self.camera.capture(step_label, target_path)
                if capture is None:
                    logger.warning(
                        f"[step {self.step_id}] capture failed "
                        f"(attempt {attempt + 1}/{MAX_DETECT_ATTEMPTS})"
                    )
                else:
                    _, image_path = capture

                    # runs aruco detection on the photo
                    aruco = ArucoDetector()
                    pose = aruco.detect_qr_angle_pose(image_path, ARUCO_ID)
                    if pose is not None:
                        return pose, image_path
                    logger.warning(
                        f"[step {self.step_id}] no marker "
                        f"(attempt {attempt + 1}/{MAX_DETECT_ATTEMPTS})"
                    )

                # small delay before the next try
                if attempt < MAX_DETECT_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_S)

            return None, image_path

        # captures a frame, logs the row, aborts if too many misses in a row
        async def calibrate_rot_pos(self, target_angle: float = 0.0, pwm: int = 0,
                                    target_distance: float = 0.0, duration: int = 0,
                                    ratio: float = 0.0):
            pose, image_path = await self._capture_and_detect()

            now = datetime.datetime.now()
            timestamp = now.isoformat(timespec="seconds")

            # fail: log NaN so the csv stays lined up with the moves the bot did
            if pose is None:
                logger.error(
                    f"[step {self.step_id}] detection failed after "
                    f"{MAX_DETECT_ATTEMPTS} attempts — NaN"
                )
                measured_angle = float("nan")
                x = float("nan")
                y = float("nan")
                pose = {"angle_deg": measured_angle, "x": x, "y": y}
                self.consecutive_failures += 1

            # success: log the real values
            else:
                measured_angle = pose["angle_deg"]
                x = pose["x"]
                y = pose["y"]
                logger.info(
                    f"[step {self.step_id}] target={target_angle:+.1f} pwm={pwm} "
                    f"duration={duration} ratio={ratio} "
                    f"measured={measured_angle:+.2f} x={x:+.1f} y={y:+.1f}"
                )
                self.consecutive_failures = 0

            # writes the row to the csv
            log_row(
                self.run_csv,
                timestamp,
                image_path or "",
                target_angle,
                pwm,
                measured_angle,
                target_distance,
                duration,
                ratio,
                x, y,
            )
            self.step_id += 1

            # K misses in a row -> camera/marker broken, abort
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    f"aborting: {self.consecutive_failures} consecutive "
                    f"detection failures (camera/marker likely broken)"
                )
                return None
            return pose

        # test different ratio value and evaluate teh best one
        async def run_ratio_calibration(self):
            logger.info(
                f"mode: ratio — distance={RATIO_DISTANCE_MM}mm, "
                f"ratios={RATIOS}, pwm={RATIO_PWM}"
            )
            # loops through ratios in the ratio list
            for ratio in RATIOS:
                for direction in (1, -1):
                    distance = RATIO_DISTANCE_MM * direction

                    # sending movement to robot
                    if not await self.motion.command_move(distance, None, RATIO_PWM, ratio):
                        return
                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        target_angle=0.0, pwm=RATIO_PWM,
                        target_distance=distance, ratio=ratio,
                    ) is None:
                        return

            # does linear regression on the ratio data
            fwd_ratio, bwd_ratio = analyse_ratio(self.run_dir)

            # sends to the controller agent the calculated ratios
            if fwd_ratio is not None:
                await self.motion.command_calibrate("ratio_forward", fwd_ratio)
            if bwd_ratio is not None:
                await self.motion.command_calibrate("ratio_backward", bwd_ratio)

        # tests different rotations to obtain a dataset duration / angle
        async def run_rotation_calibration(self):
            logger.info(
                f"mode: rotation — durations={ROTATION_DURATIONS}, "
                f"pwm={ROTATION_PWM}, ratio={ROTATION_RATIO}"
            )

            # loops through durations in the list
            for duration in ROTATION_DURATIONS:
                for direction in (1, -1):
                    signed_duration = duration * direction

                    # sending movement to robot
                    if not await self.motion.command_rotation(
                        None, signed_duration, ROTATION_PWM, ROTATION_RATIO
                    ):
                        return

                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        duration=signed_duration, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    ) is None:
                        return

            # does linear regression on the rotation data
            pos_slope, pos_intercept, neg_slope, neg_intercept = analyse_rotation(
                self.run_dir
            )

            # sends to the controller agent the calculated ratios
            await self.motion.command_calibrate("positive", pos_slope, pos_intercept)
            await self.motion.command_calibrate("negative", neg_slope, neg_intercept)

        # tests different durations to obtain a dataset duration / distance
        async def run_distance_calibration(self):
            logger.info(
                f"mode: distance — durations={DISTANCE_DURATIONS}, "
                f"pwm={DISTANCE_PWM}, ratio={DISTANCE_RATIO}"
            )

            # loops through durations in the list
            for duration in DISTANCE_DURATIONS:
                for direction in (1, -1):
                    signed_duration = duration * direction

                    # sending movement to robot
                    if not await self.motion.command_move(
                        None, signed_duration, DISTANCE_PWM, DISTANCE_RATIO
                    ):
                        return

                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        duration=signed_duration, pwm=DISTANCE_PWM, ratio=DISTANCE_RATIO,
                    ) is None:
                        return

            # does linear regression on the distance data
            fwd_slope, fwd_intercept, bwd_slope, bwd_intercept = analyse_distance(
                self.run_dir
            )

            # sends to the controller agent the calculated ratios
            await self.motion.command_calibrate("forward", fwd_slope, fwd_intercept)
            await self.motion.command_calibrate("backward", bwd_slope, bwd_intercept)

        # repeats forward/backward moves to verify the calibrated ratio
        async def run_ratio_verification(self):
            logger.info(
                f"mode: verify_ratio — {VERIFY_RATIO_TRIALS} cycles of "
                f"forward+backward {RATIO_DISTANCE_MM}mm"
            )

            # loops through the verification trials
            for trial in range(VERIFY_RATIO_TRIALS):
                for direction in (1, -1):
                    distance = RATIO_DISTANCE_MM * direction

                    # sending movement to robot
                    # ratio=None → bot uses its calibrated ratio_forward / ratio_backward
                    if not await self.motion.command_move(distance, None, RATIO_PWM, None):
                        return

                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        target_angle=0.0, pwm=RATIO_PWM,
                        target_distance=distance, ratio=0.0,
                    ) is None:
                        return

            # computes L2 score on the verification data
            score = analyse_ratio_verify(self.run_dir)

            # saves the score in a txt file
            self._save_score(score)

        # repeats +/-90 rotations to verify the calibrated rotation model
        async def run_rotation_verification(self):
            logger.info(
                f"mode: verify_rotation — {VERIFY_ROTATION_CYCLES} cycles of "
                f"+{VERIFY_ROTATION_ANGLE} then -{VERIFY_ROTATION_ANGLE}"
            )

            # loops through the verification cycles
            for cycle in range(VERIFY_ROTATION_CYCLES):
                for direction in (1, -1):
                    signed_angle = VERIFY_ROTATION_ANGLE * direction

                    # sending movement to robot
                    # duration=0 → bot derives duration from its calibrated rotation model
                    if not await self.motion.command_rotation(
                        signed_angle, 0, ROTATION_PWM, ROTATION_RATIO
                    ):
                        return

                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        target_angle=signed_angle, pwm=ROTATION_PWM, ratio=ROTATION_RATIO,
                    ) is None:
                        return

            # computes L2 score on the verification data
            score = analyse_rotation_verify(self.run_dir)

            # saves the score in a txt file
            self._save_score(score)

        # repeats forward/backward moves to verify the calibrated distance model
        async def run_distance_verification(self):
            logger.info(
                f"mode: verify_distance — {VERIFY_DISTANCE_TRIALS} cycles of "
                f"forward+backward {VERIFY_DISTANCE_MM}mm"
            )

            # loops through the verification trials
            for trial in range(VERIFY_DISTANCE_TRIALS):
                for direction in (1, -1):
                    distance = VERIFY_DISTANCE_MM * direction

                    # sending movement to robot
                    # duration=None and ratio=None → bot uses its calibrated values
                    if not await self.motion.command_move(distance, None, DISTANCE_PWM, None):
                        return

                    # takes a picture and get rot pos
                    if await self.calibrate_rot_pos(
                        target_distance=distance, pwm=DISTANCE_PWM,
                    ) is None:
                        return

            # computes L2 score on the verification data
            score = analyse_distance_verify(self.run_dir)

            # saves the score in a txt file
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
            self.consecutive_failures = 0

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
