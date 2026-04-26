import logging
import os

from spade.message import Message

logger = logging.getLogger(__name__)
ROBOT_JID = os.getenv("ROBOT_JID", "alphabot21-agent@isc-coordinator2.lan")

# Helper client that wraps the motion commands sent to the robot
class MotionClient:
    def __init__(self, behaviour, jid: str = ROBOT_JID):
        self.behaviour = behaviour
        self.jid = jid

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
        return True