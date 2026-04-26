"""
Navigator runner

Starts the NavigatorAgent and keeps it alive.
The agent now handles full closed-loop navigation internally.
"""

import os
import asyncio
import logging

from agents.navigator.agent import NavigatorAgent

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_navigator() -> NavigatorAgent | None:
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    if not xmpp_jid or not xmpp_password:
        logger.error("Missing XMPP credentials in environment variables.")
        return None

    logger.info(f"Starting Navigator with JID: {xmpp_jid}")

    agent = NavigatorAgent(xmpp_jid, xmpp_password)
    await agent.start(auto_register=True)

    if not agent.is_alive():
        logger.error("Navigator agent failed to start.")
        await agent.stop()
        return None

    logger.info("Navigator agent started successfully.")
    return agent


async def main():
    agent = await run_navigator()

    if agent is None:
        return

    try:
        logger.info("Navigator running (waiting for requests)...")

        while agent.is_alive():
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")

    finally:
        logger.info("Stopping navigator agent...")
        await agent.stop()
        logger.info("Navigator stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())