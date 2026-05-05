"""
    Main entry point for the SpadeRunner agents.

    Selects which agent to run based on the MODE env variable,
    then delegates to the generic runner.

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

# DEBUG=1 in the env enables the chatty dashboard / aiohttp / spade logs
debug_mode = os.getenv("DEBUG") == "1"
root_level = logging.DEBUG if debug_mode else logging.INFO

# Set up logging to track program execution
logging.basicConfig(level=root_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Silence the noisy stuff unless debug mode is on
if not debug_mode:
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("TelemetryAgent").setLevel(logging.ERROR)
    logging.getLogger("spade").setLevel(logging.WARNING)
    logging.getLogger("slixmpp").setLevel(logging.WARNING)

from agents.calibrator.agent import CalibratorAgent
from agents.navigator.agent import NavigatorAgent
from agents.camera_receiver.agent import CameraReceiverAgent
from agents.telemetry.agent import TelemetryAgent
from common.runner import start_agent
from common.config import *

# Maps MODE value to the agent class
AGENTS = {
    CALIBRATOR_JID: CalibratorAgent,
    NAVIGATOR_JID: NavigatorAgent,
    RECEIVER_JID: CameraReceiverAgent,
    TELEMETRY_JID: TelemetryAgent,
}


async def main():
    logger.info(f"Running in Alphabot2 mode")

    active = []
    for jid, a in AGENTS.items():
        active.append(await start_agent(a, jid))

    logger.info("Agents started successfully")

    try:
        while all(a.is_alive() for a in active):
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except asyncio.CancelledError:
        logger.warning("Main loop cancelled")
    finally:
        for a in active:
            await a.stop()
        logger.info("... all agents are stopped")


if __name__ == "__main__":
    asyncio.run(main())
