import logging
import os

from spade import agent, behaviour
from spade.message import Message


# Configure logging for the navigation requester agent
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent responsible for sending navigation requests to the NavigatorAgent
class NavigationRequesterAgent(agent.Agent):
    ENV_PREFIX = "NAV_REQ"
    class SendNavigationRequestBehaviour(behaviour.OneShotBehaviour):

        async def run(self):
            # Read the navigator agent JID from environment variables
            navigator_jid = os.getenv("NAVIGATOR_JID")

            # Create a message addressed to the navigator
            msg = Message(to=navigator_jid)

            # Set performative type to indicate a request
            msg.set_metadata("performative", "request")

            # Body expected by the NavigatorAgent
            msg.body = "request path"

            # Send the navigation request
            await self.send(msg)

            # Log the request action
            logger.info(f"Sent navigation request to {navigator_jid}")

    async def setup(self):
        # Log that the agent is ready
        logger.info(f"{self.jid} is ready.")

        # Add behaviour to send a single navigation request
        self.add_behaviour(self.SendNavigationRequestBehaviour())