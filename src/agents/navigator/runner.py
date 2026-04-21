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

# Set up logging to track program execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from agents.navigator.agent import NavigatorAgent

# Connects the navigator agent to the XMPP server
async def run_navigator():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting Navigator with JID: {xmpp_jid}")

    # creates an agent that listens for incoming path requests from the robot
    navigator = NavigatorAgent(xmpp_jid, xmpp_password)
    await navigator.start(auto_register=True)

    if not navigator.is_alive():
        logger.error("Navigator agent couldn't connect.")
        await navigator.stop()
        return None

    logger.info("Navigator agent started successfully.")
    return navigator

async def main():
    agent = await run_navigator()

    if not agent:
        logger.error("Failed to start agent.")
        return

    # main lop that keeps the agent running  and shutdowns in a clean way

    try:
        logger.info("Navigator running.")
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()
        logger.info("Agent stopped.")

if __name__ == "__main__":
    asyncio.run(main())