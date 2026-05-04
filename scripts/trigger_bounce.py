"""Send a 'start bounce' command to the BounceTestAgent over XMPP.

Usage:
    python scripts/trigger_bounce.py

Requires XMPP_PASSWORD (and XMPP_DOMAIN) to be set in the environment;
either source .env first or run inside a container that already loads it.
"""

import asyncio
import logging
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from spade import agent, behaviour
from spade.message import Message

from common.config import BOUNCE_TEST_JID, COORDINATOR_HOST


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# minimal one-shot agent: connects, sends 'start bounce', then stops
class TriggerAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.send_behaviour = self.Send()

    async def setup(self):
        self.add_behaviour(self.send_behaviour)

    class Send(behaviour.OneShotBehaviour):
        async def run(self):
            msg = Message(to=BOUNCE_TEST_JID)
            msg.set_metadata("performative", "request")
            msg.body = "start bounce"
            await self.send(msg)
            logger.info(f"sent 'start bounce' to {BOUNCE_TEST_JID}")


async def main():
    user = os.getenv("CALIBRATOR_REQUEST_USER", "calibrator_request")
    password = os.getenv("XMPP_PASSWORD")
    if not password:
        sys.exit("XMPP_PASSWORD not set — source .env first or run inside the docker container")

    jid = f"{user}@{COORDINATOR_HOST}"
    logger.info(f"connecting as {jid} to send 'start bounce'")

    trigger = TriggerAgent(jid, password)
    await trigger.start(auto_register=True)
    await trigger.send_behaviour.join()
    await trigger.stop()
    logger.info("done")


if __name__ == "__main__":
    asyncio.run(main())
