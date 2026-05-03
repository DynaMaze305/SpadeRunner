"""bounce test agent: drives forward forever, recovers like the navigator
when the bot trips emergency. used to validate the soft-bounce + hard-emergency
behaviour without the full navigation pipeline.
"""

import asyncio
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


class BounceTestAgent(agent.Agent):
    ENV_PREFIX = "BOUNCE_TEST"

    class DriveBehaviour(behaviour.CyclicBehaviour):

        async def on_start(self):
            self.motion = MotionClient(self, jid=ROBOT_JID)
            self.consecutive_emergencies = 0
            logger.info("[BOUNCE] starting forward loop")

        async def run(self):
            # one chunk forward
            await self.motion.command_move(
                distance=FORWARD_CHUNK_MM,
                pwm=FORWARD_PWM,
                ratio=FORWARD_RATIO,
            )

            # emergency tripped -> back up, count, bail if stuck
            if self.motion.last_emergency:
                self.consecutive_emergencies += 1
                logger.warning(
                    f"[EMERGENCY] tripped, consecutive={self.consecutive_emergencies}, "
                    f"recovering with {EMERGENCY_RECOVERY_MM}mm backward override"
                )
                if self.consecutive_emergencies > MAX_CONSECUTIVE_EMERGENCIES:
                    logger.error("[BOUNCE] stuck after recoveries, stopping the test")
                    self.kill(exit_code="stuck")
                    return
                await self.motion.command_move(
                    distance=EMERGENCY_RECOVERY_MM,
                    pwm=EMERGENCY_RECOVERY_PWM,
                    ratio=FORWARD_RATIO,
                    override=True,
                )
                self.motion.last_emergency = False
                return

            self.consecutive_emergencies = 0

    async def setup(self):
        logger.info("[INIT] BounceTestAgent ready")
        self.add_behaviour(self.DriveBehaviour())
