"""
    Runner function from the  navigator agent that waits for a path request from a robot,
    fetches a picture from the camera agent
    computes a path
    returns it to the robot

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from navigator_agent import NavigatorAgent
from camera_receiver import ReceiverAgent

async def run_navigator():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting Navigator with JID: {xmpp_jid}")

    navigator = NavigatorAgent(xmpp_jid, xmpp_password)
    await navigator.start(auto_register=True)

    if not navigator.is_alive():
        logger.error("Navigator agent couldn't connect.")
        await navigator.stop()
        return None

    logger.info("Navigator agent started successfully.")
    return navigator

async def run_camera_receiver():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting CameraReceiver with JID: {xmpp_jid}")

    receiver = ReceiverAgent(xmpp_jid, xmpp_password)
    await receiver.start(auto_register=True)

    if not receiver.is_alive():
        logger.error("Camera receiver agent couldn't connect.")
        await receiver.stop()
        return None

    logger.info("Camera receiver agent started successfully.")
    return receiver

async def main():
    os.makedirs("received_photos", exist_ok=True)

    mode = os.getenv("MODE", "navigator")

    if mode == "camera_test":
        agent = await run_camera_receiver()
    else:
        agent = await run_navigator()

    if not agent:
        logger.error("Failed to start agent.")
        return

    try:
        logger.info(f"Agent running in {mode} mode.")
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()
        logger.info("Agent stopped.")

if __name__ == "__main__":
    asyncio.run(main())