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
from agents.navigator_request.agent import NavigationRequesterAgent
from agents.telemetry.agent import TelemetryAgent  # disabled: grafana/logger flow off
from common.runner import run_agent, start_agent

# Maps MODE value to the agent class
AGENTS = {
    "calibrator": CalibratorAgent,
    "navigator": NavigatorAgent,
    "camera_test": CameraReceiverAgent,
    "navigator_request": NavigationRequesterAgent,
    "telemetry": TelemetryAgent,  # disabled: grafana/logger flow off
}


async def main():
    # Reads the MODE env variable and looks up the agent class
    mode = os.getenv("MODE", "calibrator")
    if mode not in AGENTS:
        logger.error(f"Unknown MODE '{mode}', valid modes: {list(AGENTS.keys())}")
        return

    logger.info(f"Running in {mode.upper()} mode")

    active = []

    # starts the picked agent in the background (non-blocking)
    primary = await start_agent(AGENTS[mode])
    if primary:
        active.append(primary)

    # also starts the dashboard alongside (unless MODE was already telemetry)
    if AGENTS[mode] is not TelemetryAgent:
        dashboard = await start_agent(TelemetryAgent)
        if dashboard:
            active.append(dashboard)

    # always keep the calibrator on standby so the dashboard can trigger it
    if AGENTS[mode] is not CalibratorAgent:
        calibrator = await start_agent(CalibratorAgent)
        if calibrator:
            active.append(calibrator)

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
