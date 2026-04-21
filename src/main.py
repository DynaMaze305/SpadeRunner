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
from common.runner import run_agent

# Maps MODE value to the agent class
AGENTS = {
    "calibrator": CalibratorAgent,
    "navigator": NavigatorAgent,
    "camera_test": CameraReceiverAgent,
}


async def main():
    # Reads the MODE env variable and looks up the agent class
    mode = os.getenv("MODE", "calibrator")
    if mode not in AGENTS:
        logger.error(f"Unknown MODE '{mode}', valid modes: {list(AGENTS.keys())}")
        return

    logger.info(f"Running in {mode.upper()} mode")
    await run_agent(AGENTS[mode])


if __name__ == "__main__":
    asyncio.run(main())
