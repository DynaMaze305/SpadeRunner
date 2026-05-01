"""Send a 'calibrate <mode>' command to the CalibratorAgent over XMPP.

Usage:
    python scripts/trigger_calibration.py rotation
    python scripts/trigger_calibration.py ratio
    python scripts/trigger_calibration.py distance

Requires XMPP_PASSWORD (and XMPP_DOMAIN) to be set in the environment;
either source .env first or run inside a container that already loads it.
"""

import argparse
import asyncio
import logging
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from spade import agent, behaviour
from spade.message import Message

from common.config import CALIBRATOR_JID, COORDINATOR_HOST


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


VALID_MODES = ("ratio", "rotation", "distance")


# parse the calibration mode from the cli
parser = argparse.ArgumentParser(description="trigger a calibration on the CalibratorAgent")
parser.add_argument("mode", choices=VALID_MODES, help="which calibration to start")
args = parser.parse_args()


# minimal one-shot agent that connects, sends one xmpp message, then stops
class TriggerAgent(agent.Agent):
    def __init__(self, jid, password, mode):
        super().__init__(jid, password)
        self.mode = mode
        self.send_behaviour = self.Send()

    async def setup(self):
        self.add_behaviour(self.send_behaviour)

    class Send(behaviour.OneShotBehaviour):
        async def run(self):
            mode = self.agent.mode
            msg = Message(to=CALIBRATOR_JID)
            msg.set_metadata("performative", "request")
            msg.body = f"calibrate {mode}"
            await self.send(msg)
            logger.info(f"sent 'calibrate {mode}' to {CALIBRATOR_JID}")


async def main():

    # xmpp credentials: reuses the same password as the rest of the agents
    user = os.getenv("CALIBRATOR_REQUEST_USER", "calibrator_request")
    password = os.getenv("XMPP_PASSWORD")
    if not password:
        sys.exit("XMPP_PASSWORD not set — source .env first or run inside the docker container")

    jid = f"{user}@{COORDINATOR_HOST}"
    logger.info(f"connecting as {jid} to send 'calibrate {args.mode}'")

    # start the agent, wait for the one-shot to finish, stop and exit
    trigger = TriggerAgent(jid, password, args.mode)
    await trigger.start(auto_register=True)
    await trigger.send_behaviour.join()
    await trigger.stop()
    logger.info("done")


if __name__ == "__main__":
    asyncio.run(main())
