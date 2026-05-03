import logging

from spade.message import Message
from common.config import ROBOT_JID

logger = logging.getLogger(__name__)

# Helper client that wraps the motion commands sent to the robot
class MotionClient:
    def __init__(self, behaviour, jid: str = ROBOT_JID):
        self.behaviour = behaviour
        self.jid = jid
        # set by command_move when the bot's reply says emergency tripped
        self.last_emergency = False

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
        return True

    async def command_move(self, distance: float, duration=None, pwm=None, ratio=None, override: bool = False) -> bool:

        # robot uses "0" as the null sentinel — convert any None field before formatting
        distance = 0 if distance is None else distance
        duration = 0 if duration is None else duration
        pwm = 0 if pwm is None else pwm
        ratio = 0 if ratio is None else ratio
        # 6th token: 1 = bypass the bot's emergency latch (recovery move only)
        override_token = 1 if override else 0

        # Usage example: move -200 0 20 1.04 0
        # -200 distance
        # 0 duration
        # 20 PWM
        # 1.04 ratio left/right
        # 0 = normal, 1 = override
        command = f"move {distance:g} {duration:g} {pwm:g} {ratio:g} {override_token}"
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
        body = ack.body or ""
        # bot reply contains "Error: MotionManager emergency stop active" when latched
        self.last_emergency = "emergency stop active" in body.lower()
        logger.info(f"robot ack: {body}")
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