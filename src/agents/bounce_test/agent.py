"""bounce test agent: drives forward in chunks, recovers like the navigator
when the bot trips emergency. listens for 'start bounce' and runs the loop.
used to validate soft-bounce + hard-emergency without the full nav pipeline.
"""

import logging

from spade import agent, behaviour

from common.config import ROBOT_JID
from common.motion_client import MotionClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# how far each forward chunk goes before re-issuing
FORWARD_CHUNK_MM = 200
FORWARD_PWM = 15
FORWARD_RATIO = 0.9

# emergency recovery (must match the navigator's constants)
EMERGENCY_RECOVERY_MM = -30
EMERGENCY_RECOVERY_PWM = 10
MAX_CONSECUTIVE_EMERGENCIES = 2

# safety cap so an idle 'start bounce' doesn't run literally forever
MAX_CHUNKS = 100


class BounceTestAgent(agent.Agent):
    ENV_PREFIX = "BOUNCE_TEST"

    class BounceBehaviour(behaviour.CyclicBehaviour):

        async def on_start(self):
            self.motion = MotionClient(self, jid=ROBOT_JID)
            # toss any offline messages Prosody queued while we were down
            drained = 0
            while True:
                stale = await self.receive(timeout=0.1)
                if stale is None:
                    break
                drained += 1
            if drained:
                logger.info(f"discarded {drained} stale message(s) from offline queue")
            logger.info("bounce test ready, waiting for 'start bounce' command")

        async def run(self):
            request = await self.receive(timeout=10)
            if request is None:
                return

            body = (request.body or "").strip()
            if body != "start bounce":
                logger.warning(f"unknown command from {request.sender}: '{body}'")
                return

            logger.info(f"starting forward loop (up to {MAX_CHUNKS} chunks)")
            consecutive_emergencies = 0

            for i in range(MAX_CHUNKS):
                # one chunk forward
                await self.motion.command_move(
                    distance=FORWARD_CHUNK_MM,
                    pwm=FORWARD_PWM,
                    ratio=FORWARD_RATIO,
                )

                # emergency tripped -> back up, count, bail if stuck
                if self.motion.last_emergency:
                    consecutive_emergencies += 1
                    logger.warning(
                        f"[EMERGENCY] tripped, consecutive={consecutive_emergencies}, "
                        f"recovering with {EMERGENCY_RECOVERY_MM}mm backward override"
                    )
                    if consecutive_emergencies > MAX_CONSECUTIVE_EMERGENCIES:
                        logger.error("stuck after recoveries, ending test")
                        return
                    await self.motion.command_move(
                        distance=EMERGENCY_RECOVERY_MM,
                        pwm=EMERGENCY_RECOVERY_PWM,
                        ratio=FORWARD_RATIO,
                        override=True,
                    )
                    self.motion.last_emergency = False
                else:
                    consecutive_emergencies = 0

            logger.info(f"completed {MAX_CHUNKS} chunks")

    async def setup(self):
        logger.info("[INIT] BounceTestAgent ready")
        self.add_behaviour(self.BounceBehaviour())
