"""
    Agent that obtains a one-shot photo from the ceiling camera
    and saves it to disk.

    Inspired by the camera_receiver.py from Berk Buzcu
"""

import os
import datetime
import logging

from spade import agent, behaviour

from common.camera_client import CameraClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PHOTOS_DIR = "received_photos"

class CameraReceiverAgent(agent.Agent):
    ENV_PREFIX = "CAMERA_RECEIVER"
    class CameraReceiveBehaviour(behaviour.OneShotBehaviour):
        async def run(self):
            camera = CameraClient(self)

            # creates the filename with a timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(PHOTOS_DIR, f"photo_{timestamp}.jpg")

            # requests a photo and saves it to disk
            capture = await camera.capture("receiver", path)
            if capture is None:
                return
            img, filepath = capture

            logger.info(f"Photo saved as '{filepath}'.")

    async def setup(self):
        logger.info(f"{self.jid} is ready.")
        self.add_behaviour(self.CameraReceiveBehaviour())