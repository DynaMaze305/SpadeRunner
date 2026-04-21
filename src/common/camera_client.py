"""
    Helper client used by any agent that needs a photo from the
    ceiling camera. Wraps the XMPP request so the
    agent just calls: img = await camera.request_photo(label)
"""

import os
import base64
import logging

from spade.message import Message

from common.photo_io import save_bytes

logger = logging.getLogger(__name__)

CAMERA_JID = os.getenv("CAMERA_JID", "camera_agent@isc-coordinator.lan")


# Helper client that wraps the photo request exchange
class CameraClient:
    def __init__(self, behaviour, jid: str = CAMERA_JID):
        self.behaviour = behaviour
        self.jid = jid

    # Helper function that requests a photos and returns it
    async def request_photo(self, label: str):

        # Sends a message to request the photo
        msg = Message(to=self.jid)
        msg.set_metadata("performative", "request")
        msg.body = "Requesting photo"
        await self.behaviour.send(msg)
        logger.info(f"[{label}] photo requested from {self.jid}")

        # waits for the photo reception
        reply = await self.behaviour.receive(timeout=45)
        if reply is None:
            logger.error(f"[{label}] no photo received")
            return None
        try:
            # Decodes the picture and returns raw data
            return base64.b64decode(reply.body)
        except Exception as e:
            logger.error(f"[{label}] failed to decode photo: {e}")
            return None

    # Helper function that requests a photo and saves it to a given file path
    async def capture(self, label: str, path: str):
        img = await self.request_photo(label)
        if img is None:
            return None
        directory, name = os.path.split(path)
        saved_path = await save_bytes(img, name, directory)
        return img, saved_path
