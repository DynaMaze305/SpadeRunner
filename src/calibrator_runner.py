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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from calibrator_agent import CalibratorAgent


async def run_calibrator():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting Calibrator with JID: {xmpp_jid}")

    calibrator = CalibratorAgent(xmpp_jid, xmpp_password)
    await calibrator.start(auto_register=True)

    if not calibrator.is_alive():
        logger.error("Calibrator agent couldn't connect.")
        await calibrator.stop()
        return None

    logger.info("Calibrator agent started successfully.")
    return calibrator


async def main():
    os.makedirs("calibration_photos", exist_ok=True)

    agent = await run_calibrator()
    if not agent:
        logger.error("Failed to start calibrator.")
        return

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