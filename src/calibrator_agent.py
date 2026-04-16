import os
import base64
import logging
import datetime

from spade import agent, behaviour
from spade.message import Message

from qr_detector import detect_qr_angle, angle_diff
from photo_io import save_bytes
from calibration_log import log_row


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CAMERA_JID = os.getenv("CAMERA_JID", "camera_agent@isc-coordinator.lan")
ROBOT_JID = os.getenv("ROBOT_JID", "alphabot21-agent@isc-coordinator.lan")
ROTATION_DEGREES = float(os.getenv("ROTATION_DEGREES", "90"))
CALIBRATION_DIR = os.getenv("CALIBRATION_DIR", "calibration_photos")
CALIBRATION_CSV = os.getenv("CALIBRATION_CSV", os.path.join(CALIBRATION_DIR, "calibration.csv"))


class CalibratorAgent(agent.Agent):
    class CalibrateBehaviour(behaviour.OneShotBehaviour):
        async def request_photo(self, label: str):
            msg = Message(to=CAMERA_JID)
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"
            await self.send(msg)
            logger.info(f"[{label}] photo requested from {CAMERA_JID}")

            reply = await self.receive(timeout=15)
            if reply is None:
                logger.error(f"[{label}] no photo received")
                return None
            try:
                return base64.b64decode(reply.body)
            except Exception as e:
                logger.error(f"[{label}] failed to decode photo: {e}")
                return None

        async def measure_angle(self, label: str):
            img = await self.request_photo(label)
            if img is None:
                return None
            now = datetime.datetime.now()
            ts = now.strftime("%Y%m%d_%H%M%S")
            image_path = await save_bytes(img, f"calib_{label}_{ts}.jpg", CALIBRATION_DIR)

            angle = detect_qr_angle(img)
            if angle is None:
                logger.warning(f"[{label}] no QR code detected")
                return None
            logger.info(f"[{label}] QR angle = {angle:+.2f} deg")
            log_row(CALIBRATION_CSV, now.isoformat(timespec="seconds"), image_path, angle)
            return angle

        async def command_rotation(self) -> bool:
            command = f"rotation {ROTATION_DEGREES:g}"
            msg = Message(to=ROBOT_JID)
            msg.set_metadata("performative", "request")
            msg.body = command
            await self.send(msg)
            logger.info(f"sent rotation command '{command}' to {ROBOT_JID}")

            ack = await self.receive(timeout=30)
            if ack is None:
                logger.error("no ack from robot after rotation command")
                return False
            logger.info(f"robot ack: {ack.body}")
            return True

        async def run(self):
            theta_before = await self.measure_angle("before")
            if theta_before is None:
                return

            # if not await self.command_rotation():
            #     return
            #

            # theta_after = await self.measure_angle("after")

            # if theta_after is None:
            #     return

            # measured = angle_diff(theta_after, theta_before)
            logger.info(f"calibration cycle complete: commanded={ROTATION_DEGREES:+.1f} deg, measured={measured:+.2f} deg")

    async def setup(self):
        logger.info("calibrator agent ready")
        self.add_behaviour(self.CalibrateBehaviour())