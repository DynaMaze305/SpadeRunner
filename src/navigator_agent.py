"""
    Listener agent that waits for a path request from a robot,
    fetches a picture from the camera agent
    computes a path
    returns it to the robot

    Based on the camera_receiver by Berk Buzcu
"""

import os
import asyncio
import logging
import base64
import aiofiles
import os
import datetime

from spade import agent, behaviour
from spade.message import Message
from pathfinding import compute_path

# Set up logging to track program execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NavigatorAgent(agent.Agent):
    class NavigateBehaviour(behaviour.CyclicBehaviour):
        async def run(self):

            # idle waiting for request
            logger.info("Waiting for any robot to request a path")
            request = await self.receive(timeout=9999)

            if request is None:
                return

            robot_jid = str(request.sender)
            if request.body == "request path":
                logger.info(f"Robot {robot_jid} requested path: {request}")
            else:
                logger.warning(f"Unknown incoming request: {request.body} from jid: {robot_jid}")
                return

            # asking for a photo to the coordinator
            msg = Message(to="camera_agent@isc-coordinator.lan")
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"

            await self.send(msg)
            logger.info("Requested a photo from the camera_agent at isc-coordinator.lan")
            photo_request = await self.receive(timeout=30)

            if not photo_request:
                logger.warning("No photo received from camera_agent")
                return

            logger.info("Received a photo from camera_agent")

            # saving the photo
            img_data = base64.b64decode(msg.body)

            photos_dir  = os.path.join(os.getcwd(), "received_photos")
            os.makedirs(photos_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}.jpg"
            filepath = os.path.join(photos_dir, filename)

            async with aiofiles.open(filepath, "wb") as img_file:
                await img_file.write(img_data)

            print(f"Photo saved as '{filepath}'.")

            # Should compute the path

            computed_path = compute_path(img_data)

            reply = Message(to=robot_jid)
            reply.set_metadata("performative", "response")
            reply.body = computed_path
            await self.send(reply)
            logger.info(f"Path returned to the robot, with length {len(reply.body)}")


    async def setup(self):
        logger.info(f"The navigator agent is ready to be used")
        self.add_behaviour(self.NavigateBehaviour())