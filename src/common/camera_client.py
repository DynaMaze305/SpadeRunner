import os
import base64
import logging

from spade.message import Message

from common.photo_io import save_bytes
from common.config import CAMERA_JID

logger = logging.getLogger(__name__)


# Helper client that wraps the photo request exchange
class CameraClient:
    def __init__(self, behaviour, jid: str = CAMERA_JID):
        self.behaviour = behaviour
        self.jid = jid

    # Helper function that requests a photos and returns it
    async def request_photo(self, label: str):

        # Sends a message to request the photo
        async def send_request():
            msg = Message(to=self.jid)
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"
            await self.behaviour.send(msg)
            logger.info(f"[{label}] photo requested from {self.jid}")
        
        await send_request()
        # waits for the photo reception
        while True:
            reply = await self.behaviour.receive(timeout=45)
            if reply:
                if str(reply.sender.bare()) == self.jid:
                    break
                else:
                    await send_request()
            else:
                await send_request()

        if reply is None:
            logger.error(f"[{label}] no photo received")
            return None
        try:
            # Decodes the picture and returns raw data
            return base64.b64decode(reply.body)
        except Exception as e:
            logger.info(f"{msg}")
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
