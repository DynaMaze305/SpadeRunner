"""
    Runner function from the camera agent that
    fetches a picture from the camera agent
    saves it to the disk

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

# Logger function to display info in the terminal during runtime
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.agents.camera_receiver.agent import CameraReceiverAgent

# Creates a camera receiver agent , and registers it to the coordinator
async def run_camera_receiver():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting Camera Receiver with JID: {xmpp_jid}")

    # Creation of the agent
    camera_receiver = CameraReceiverAgent(xmpp_jid, xmpp_password)

    # Registration
    await camera_receiver.start(auto_register=True)

    # Cleanup if failure
    if not camera_receiver.is_alive():
        logger.error("Camera_receiver agent couldn't connect.")
        await camera_receiver.stop()
        return None

    logger.info("Camera_receiver agent started successfully.")
    return camera_receiver


async def main():
    # Creates a directory for storing the calibration photos
    os.makedirs("Camera_reception", exist_ok=True)

    # Starts the agent setup
    agent = await run_camera_receiver()
    if not agent:
        logger.error("Failed to start camera_receiver.")
        return

    # Runtime info for running and shutdown
    try:
        logger.info("camera_receiver running.")
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()
        logger.info("camera_receiver stopped.")


if __name__ == "__main__":
    asyncio.run(main())
