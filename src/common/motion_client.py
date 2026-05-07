from __future__ import annotations

import asyncio
import logging

from spade.message import Message
from common.config import ROBOT_JID

logger = logging.getLogger(__name__)


# How long every motion command pauses on our side AFTER the robot's ack
# before returning, so the chassis has time to physically stop / settle
# before the caller takes the next photo or issues another command.
# Edit this constant to tune; a per-instance override is available via the
# `post_motion_settle_s` constructor argument.
POST_MOTION_SETTLE_S: float = 1.0


# Helper client that wraps the motion commands sent to the robot
class MotionClient:
    def __init__(
        self,
        behaviour,
        jid: str = ROBOT_JID,
        post_motion_settle_s: float | None = None,
    ):
        self.behaviour = behaviour
        self.jid = jid
        self.post_motion_settle_s = (
            post_motion_settle_s
            if post_motion_settle_s is not None
            else POST_MOTION_SETTLE_S
        )

    async def _post_motion_settle(self, label: str) -> None:
        if self.post_motion_settle_s <= 0:
            return
        logger.info(
            f"[MOTION] settle {self.post_motion_settle_s:.2f}s after {label}"
        )
        await asyncio.sleep(self.post_motion_settle_s)

    # Sending a rotation command to the robot
    async def command_rotation(self, signed_degrees: float, duration=None, pwm=None, ratio=None) -> bool:

        # Usage example: rotation 90
        # 90 angle in degrees

        # robot uses "0" as the null sentinel — convert any None field before formatting
        signed_degrees = 0 if signed_degrees is None else signed_degrees
        duration = 0 if duration is None else duration
        pwm = 0 if pwm is None else pwm
        ratio = 0 if ratio is None else ratio

        # Creates the message
        command = f"rotation {signed_degrees:g} {duration:g} {pwm:g} {ratio:g}"
        msg = Message(to=self.jid)
        msg.set_metadata("performative", "request")
        msg.body = command

        # Sends the message to the target agent
        await self.behaviour.send(msg)
        logger.info(f"sent '{command}' to {self.jid}")

        # Waits for the answer
        ack = await self.behaviour.receive(timeout=30)
        if ack is None:
            logger.error("no ack from robot after rotation command")
            return False
        logger.info(f"robot ack: {ack.body}")
        await self._post_motion_settle("rotation")
        return True

    async def command_move(self, distance: float, duration=None, pwm=None, ratio=None) -> bool:

        # robot uses "0" as the null sentinel — convert any None field before formatting
        distance = 0 if distance is None else distance
        duration = 0 if duration is None else duration
        pwm = 0 if pwm is None else pwm
        ratio = 0 if ratio is None else ratio

        # Usage example: move -200 0 20 1.04
        # -200 distance
        # 0 duration
        # 20 PWM
        # 1.04 ratio left/right
        command = f"move {distance:g} {duration:g} {pwm:g} {ratio:g}"
        msg = Message(to=self.jid)
        msg.set_metadata("performative", "request")
        msg.body = command

        # sends the command to the robot
        await self.behaviour.send(msg)
        logger.info(f"sent '{command}' to {self.jid}")

        # waits for an answer from the robot
        ack = await self.behaviour.receive(timeout=30)
        if ack is None:
            logger.error("no ack from robot after move command")
            return False
        logger.info(f"robot ack: {ack.body}")
        await self._post_motion_settle("move")
        return True

    # Sends a one-shot calibrate command to the robot.
    # Format: calibrate <key> <value1> [value2]
    # Doesn't move the motors — the robot just persists the values.
    async def command_calibrate(self, key: str, *values) -> bool:
        parts = " ".join(f"{v:g}" for v in values)
        command = f"calibrate {key} {parts}".rstrip()

        msg = Message(to=self.jid)
        msg.set_metadata("performative", "request")
        msg.body = command

        await self.behaviour.send(msg)
        logger.info(f"sent '{command}' to {self.jid}")

        ack = await self.behaviour.receive(timeout=10)
        if ack is None:
            logger.error(f"no ack from robot after calibrate {key}")
            return False
        logger.info(f"robot ack: {ack.body}")
        return True