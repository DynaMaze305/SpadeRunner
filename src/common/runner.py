"""
    Generic runner used by any SPADE agent. Handles:
    - reading XMPP credentials from env
    - starting the agent and registering it to the coordinator
    - keeping it alive until Ctrl+C
    - clean shutdown

    Based on the runner.py by Berk Buzcu
"""

import os
import asyncio
import logging

logger = logging.getLogger(__name__)


async def start_agent(AgentClass, **kwargs):
    """Starts an agent and returns it directly (no keepalive loop)"""
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting {AgentClass.__name__}...")

    agent = AgentClass(xmpp_jid, xmpp_password, **kwargs)
    await agent.start(auto_register=True)

    logger.info(f"... {AgentClass.__name__} has started")
    return agent


# Creates the given agent class and registers it to the coordinator
async def run_agent(AgentClass, **kwargs):
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")

    logger.info(f"Starting {AgentClass.__name__} with JID: {xmpp_jid}")

    # Creation of the agent
    agent = AgentClass(xmpp_jid, xmpp_password, **kwargs)

    # Registration
    await agent.start(auto_register=True)

    # Cleanup if failure
    if not agent.is_alive():
        logger.error(f"{AgentClass.__name__} couldn't connect.")
        await agent.stop()
        return

    logger.info(f"{AgentClass.__name__} started successfully.")

    # main loop that keeps the agent running and shuts it down cleanly
    try:
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()
        logger.info(f"{AgentClass.__name__} stopped.")
