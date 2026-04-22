"""
    Main entry point for the SpadeRunner agents.

    Selects which agent to run based on the MODE env variable,
    then delegates to the generic runner.

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

# Set up logging to track program execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from agents.calibrator.agent import CalibratorAgent
from agents.navigator.agent import NavigatorAgent
from agents.camera_receiver.agent import CameraReceiverAgent
from agents.keyboard_controller.agent import KeyBoardController
from common.runner import start_agent

# Maps MODE value to the agent class
AGENTS = {
    "calibrator": CalibratorAgent,
    "navigator": NavigatorAgent,
    "camera_test": CameraReceiverAgent,
}


async def main():
    mode = os.getenv("MODE", "camera_test")
    if mode not in AGENTS:
        logger.error(f"Unknown MODE '{mode}', valid modes: {list(AGENTS.keys())}")
        return

    logger.info(f"Running in {mode.upper()} mode")

    active = []
    
    # Pour avoir le KeybBoardController qui tourne en arrière-plan
    kb = await start_agent(KeyBoardController)
    if kb:
        active.append(kb)

    agent = await start_agent(AGENTS[mode])
    if agent:
        active.append(agent)

    try:
        while all(a.is_alive() for a in active):
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        for a in active:
            await a.stop()
        logger.info("... all agents are stopped")


if __name__ == "__main__":
    asyncio.run(main())
