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

from common.config import COORDINATOR_HOST

logger = logging.getLogger(__name__)


async def start_agent(AgentClass, custom_jid=None, **kwargs):
    """Starts an agent and returns it directly (no keepalive loop).

    Reads <ENV_PREFIX>_USER and XMPP_PASSWORD from the env so each
    agent can log in with its own XMPP account. Pass custom_jid to override
    the derived JID (used to make one agent log in as another).
    """
    prefix = AgentClass.ENV_PREFIX
    user = os.getenv(f"{prefix}_USER")
    agent_jid = custom_jid or f"{user}@{COORDINATOR_HOST}"
    agent_password = os.getenv(f"XMPP_PASSWORD")

    logger.info(f"Starting {AgentClass.__name__} as {agent_jid}...")

    agent = AgentClass(agent_jid, agent_password, **kwargs)
    await agent.start(auto_register=True)

    logger.info(f"... {AgentClass.__name__} has started")
    return agent


# Same as start_agent but keeps the agent alive in a loop until Ctrl+C
async def run_agent(AgentClass, custom_jid=None, **kwargs):
    prefix = AgentClass.ENV_PREFIX
    user = os.getenv(f"{prefix}_USER")
    agent_jid = custom_jid or f"{user}@{COORDINATOR_HOST}"
    agent_password = os.getenv(f"{prefix}_PASSWORD")

    logger.info(f"Starting {AgentClass.__name__} with JID: {agent_jid}")

    # Creation of the agent
    agent = AgentClass(agent_jid, agent_password, **kwargs)

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