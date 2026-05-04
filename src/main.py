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

from agents.bounce_test.agent import BounceTestAgent
from agents.calibrator.agent import CalibratorAgent
from agents.navigator.agent import NavigatorAgent
from agents.camera_receiver.agent import CameraReceiverAgent
from agents.navigator_request.agent import NavigationRequesterAgent
from agents.telemetry.agent import TelemetryAgent
from common.runner import run_agent, start_agent

# Production set: dashboard buttons + scripts trigger work on demand.
# bounce_test is here because it's a CyclicBehaviour that idles until
# 'start bounce' arrives (via scripts/trigger_bounce.py), same shape as calibrator.
PRODUCTION_AGENTS = (NavigatorAgent, TelemetryAgent, CalibratorAgent, BounceTestAgent)

# MODE selects a one-off test agent that bypasses the production set.
TEST_AGENTS = {
    "camera_test": CameraReceiverAgent,
    "navigator_request": NavigationRequesterAgent,
}


async def main():
    mode = os.getenv("MODE", "").strip()

    active = []

    if mode:
        if mode not in TEST_AGENTS:
            logger.error(f"Unknown MODE '{mode}', valid: {list(TEST_AGENTS.keys())} or empty")
            return
        logger.info(f"test mode: {mode}")
        test_agent = await start_agent(TEST_AGENTS[mode])
        if test_agent:
            active.append(test_agent)
    else:
        for AgentClass in PRODUCTION_AGENTS:
            started = await start_agent(AgentClass)
            if started:
                active.append(started)

    logger.info(f"agents started: {[a.jid for a in active]}")

    # keepalive: stops everything cleanly when any agent dies or on Ctrl+C
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
