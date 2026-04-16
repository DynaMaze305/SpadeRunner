"""
    Runner function from the calibrator agent that
    fetches a picture from the camera agent
    computes the rotation angle
    returns it to the robot

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

# Logger function to display info in the terminal during runtime
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from calibrator_agent import CalibratorAgent

# Creates a Calibrator agent , and registers it to the coordinator
async def run_calibrator():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting Calibrator with JID: {xmpp_jid}")

    # Creation of the agent
    calibrator = CalibratorAgent(xmpp_jid, xmpp_password)

    # Registration
    await calibrator.start(auto_register=True)

    # Cleanup if failure
    if not calibrator.is_alive():
        logger.error("Calibrator agent couldn't connect.")
        await calibrator.stop()
        return None

    logger.info("Calibrator agent started successfully.")
    return calibrator


async def main():
    # Creates a directory for storing the calibration photos
    os.makedirs("calibration_photos", exist_ok=True)

    # Starts the agent setup
    agent = await run_calibrator()
    if not agent:
        logger.error("Failed to start calibrator.")
        return

    # Runtime info for running and shutdown
    try:
        logger.info("Calibrator running.")
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()
        logger.info("Calibrator stopped.")


if __name__ == "__main__":
    asyncio.run(main())