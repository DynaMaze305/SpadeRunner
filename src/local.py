import asyncio
import logging

# Set up logging to track program execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from agents.telemetry.agent import TelemetryAgent
from agents.keyboard_controller.agent import KeyBoardController
from common.runner import start_agent

# Maps MODE value to the agent class
AGENTS = {
    #"keyboard" : KeyBoardController,
    "telemetry" : TelemetryAgent
}


async def main():
    logger.info(f"Running in Alphabot2 mode")

    active = []
    for _, a in AGENTS.items():
        active.append(await start_agent(a))

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
    try:
      asyncio.run(main())
    except Exception as e:
        logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
