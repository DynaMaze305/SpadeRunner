"""
    Similar to navigator agent
    1) requests a photo form the ceiling camera
    2) Commands the robot via SPADE to do movement
    2) using opencv measures the angle after rotation
    3) Logs it to the CSV file
    4) repeat for all commands in the list
"""

import os
import base64
import logging
import datetime

from spade import agent, behaviour
from spade.message import Message

from qr_detector import detect_qr_angle
from photo_io import save_bytes
from calibration_log import log_row

# Logger function to display info in the terminal during runtime
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# fetching all environment variables , defaulting to fallback if missing
CAMERA_JID = os.getenv("CAMERA_JID", "camera_agent@isc-coordinator.lan")
ROBOT_JID = os.getenv("ROBOT_JID", "alphabot21-agent@isc-coordinator.lan")
ROTATION_DEGREES = [float(x) for x in os.getenv("ROTATION_DEGREES", "90, 180, -90, -180, 270, -270").split(",") if x.strip()]
CALIBRATION_DIR = os.getenv("CALIBRATION_DIR", "calibration_photos")
CALIBRATION_CSV = os.getenv("CALIBRATION_CSV", os.path.join(CALIBRATION_DIR, "calibration.csv"))

# Calibrator agent with three ineternal functions
# - Get a photo
# - Computes the angle and log it in the CSV
# - Send a movment command to the robot
class CalibratorAgent(agent.Agent):
    class CalibrateBehaviour(behaviour.OneShotBehaviour):
        async def request_photo(self, label: str):
            # Message request for fetching a photo
            msg = Message(to=CAMERA_JID)
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"
            await self.send(msg)
            logger.info(f"[{label}] photo requested from {CAMERA_JID}")

            # Waiting for a reply
            reply = await self.receive(timeout=45)
            if reply is None:
                logger.error(f"[{label}] no photo received")
                return None
            try:
                # If successful decodes the photo from b64 to raw
                return base64.b64decode(reply.body)
            except Exception as e:
                logger.error(f"[{label}] failed to decode photo: {e}")
                return None

        # Wrapper function that requests , computes , logs
        async def capture_and_log(self, step_id: int, commanded_angle: float):
            # Requesting a photo
            img = await self.request_photo(f"step {step_id}")
            if img is None:
                logger.info(f"NO image for step {step_id}")
                return None
            now = datetime.datetime.now()

            # Saves the photo locally
            image_path = await save_bytes(img, f"{step_id}.jpg", CALIBRATION_DIR)

            # Measuring angle with OpenCV
            measured_angle = detect_qr_angle(image_path)

            if measured_angle is None:
                logger.warning(f"[step {step_id}] no marker detected — logging NaN and continuing")
                measured_angle = float("nan")
            else:
                logger.info(f"[step {step_id}] commanded={commanded_angle:+.2f} measured={measured_angle:+.2f} deg")

            # Logs the data in the CSV file (NaN if marker missing)
            log_row(CALIBRATION_CSV, now.isoformat(timespec="seconds"), image_path, commanded_angle, measured_angle)
            return measured_angle

        # Send a Rotation command to the robot, angle as parameter in degree
        # Follows the trigonometric rotation sign
        async def command_rotation(self, degrees: float) -> bool:
            # Ssnds message to robot
            command = f"rotation {degrees:g}"
            msg = Message(to=ROBOT_JID)
            msg.set_metadata("performative", "request")
            msg.body = command
            await self.send(msg)
            logger.info(f"sent rotation command '{command}' to {ROBOT_JID}")

            # Waits for a successful ACK of the command
            ack = await self.receive(timeout=30)
            if ack is None:
                logger.error("no ack from robot after rotation command")
                return False
            logger.info(f"robot ack: {ack.body}")
            return True


        # Entry function of the agent
        async def run(self):
            os.makedirs(CALIBRATION_DIR, exist_ok=True)

            # find the next free step id by scanning existing .jpg files
            existing = []
            for name in os.listdir(CALIBRATION_DIR):
                stem = os.path.splitext(name)[0]
                if stem.isdigit():
                    existing.append(int(stem))
            step_id = max(existing, default=-1) + 1

            # Starts with taking a first picture and measuring it
            if await self.capture_and_log(step_id, commanded_angle=0.0) is None:
                return
            step_id += 1

            # Then loops through the commands to
            # - 1) Execute the command
            # - 2) take a picture and log data to CSV
            for degrees in ROTATION_DEGREES:
                if not await self.command_rotation(degrees):
                    return
                if await self.capture_and_log(step_id, commanded_angle=degrees) is None:
                    return
                step_id += 1

    # Registers the agent behaviour to the pool
    async def setup(self):
        logger.info("calibrator agent ready")
        self.add_behaviour(self.CalibrateBehaviour())