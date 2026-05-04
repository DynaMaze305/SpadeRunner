"""bounce test agent: drives forward in chunks, recovers like the navigator
when the bot trips emergency. listens for 'start bounce' and runs the loop.
used to validate soft-bounce + hard-emergency without the full nav pipeline.
"""

import json
import logging

from spade import agent, behaviour
from spade.message import Message

from common.config import ROBOT_JID, TELEMETRY_JID
from common.motion_client import MotionClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# how far each forward chunk goes before re-issuing
FORWARD_CHUNK_MM = 20000
FORWARD_PWM = 15
FORWARD_RATIO = 0.9

# emergency recovery (must match the navigator's constants)
EMERGENCY_RECOVERY_MM = -30
EMERGENCY_RECOVERY_PWM = 10
MAX_CONSECUTIVE_EMERGENCIES = 2

# rotation maneuver fired when the bot sends 'emergency_stop <side>'
EMERGENCY_TURN_DEG = 90
EMERGENCY_TURN_PWM = 15
EMERGENCY_TURN_RATIO = 1.05

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
            await self._notify_status("busy", task="bounce")
            consecutive_emergencies = 0

            try:
                for i in range(MAX_CHUNKS):
                    # one chunk forward
                    await self.motion.command_move(
                        distance=FORWARD_CHUNK_MM,
                        pwm=FORWARD_PWM,
                        ratio=FORWARD_RATIO,
                    )

                    # bot may send 'emergency_stop <0|1>' between chunks: 0 -> turn left, 1 -> turn right
                    if await self._handle_emergency_maneuvers():
                        consecutive_emergencies += 1
                        if consecutive_emergencies > MAX_CONSECUTIVE_EMERGENCIES:
                            logger.error("stuck after rotation maneuvers, ending test")
                            return
                        # rotation cleared the wall, drop the latch flag for next chunk
                        self.motion.last_emergency = False
                        continue

                    consecutive_emergencies = 0

                logger.info(f"completed {MAX_CHUNKS} chunks")
            finally:
                await self._notify_status("ready")

        # Drain the mailbox of bot-sent 'emergency_stop <0|1>' messages and
        # fire a 90 deg rotation in the indicated direction. 0 -> left, 1 -> right.
        # Returns True if a maneuver was performed (caller should continue the loop).
        async def _handle_emergency_maneuvers(self) -> bool:
            side = None
            while True:
                msg = await self.receive(timeout=0.05)
                if msg is None:
                    break
                body = (msg.body or "").strip()
                # only the most recent emergency_stop side wins
                if body.startswith("emergency_stop "):
                    side = body.split()[1]
                # 'emergency_maneuver right/left' is a duplicate signal, drop silently
                elif body.startswith("emergency_maneuver"):
                    continue
                else:
                    logger.warning(f"unknown command from {msg.sender}: '{body}'")

            if side is None:
                return False

            if side == "0":
                signed = -EMERGENCY_TURN_DEG  # turn left
            elif side == "1":
                signed = EMERGENCY_TURN_DEG   # turn right
            else:
                logger.warning(f"unknown emergency_stop side '{side}', skipping maneuver")
                return False

            logger.warning(f"[EMERGENCY] received emergency_stop {side}, rotating {signed:+.0f} deg")
            await self.motion.command_rotation(
                signed_degrees=signed,
                pwm=EMERGENCY_TURN_PWM,
                ratio=EMERGENCY_TURN_RATIO,
            )
            return True

        # Tells the dashboard (via telemetry) we just started or finished a job
        async def _notify_status(self, status: str, task: str = "") -> None:
            msg = Message(to=TELEMETRY_JID)
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps({"type": status, "task": task})
            await self.send(msg)
            logger.info(f"sent status='{status}' task='{task}' to telemetry")

    async def setup(self):
        logger.info("[INIT] BounceTestAgent ready")
        self.add_behaviour(self.BounceBehaviour())
