"""
    Simple driver agent that runs a fixed motion sequence:
    rotation, forward, rotation, forward.
    Used as an end-to-end smoke test of the motion pipeline.
"""

import logging

from spade import agent, behaviour

from common.motion_client import MotionClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROTATION_ANGLE = 180
ROTATION_PWM = 15

MOVE_DISTANCE = 200
MOVE_DURATION = None
MOVE_PWM = 20
MOVE_RATIO = 1.0


class DriverAgent(agent.Agent):
    ENV_PREFIX = "DRIVER"

    class DriveBehaviour(behaviour.OneShotBehaviour):
        # fixed test sequence: rotate, move forward, rotate, move forward
        async def run(self):
            self.motion = MotionClient(self)

            logger.info("driver: rotation 1")
            if not await self.motion.command_rotation(ROTATION_ANGLE, ROTATION_PWM):
                return

            logger.info("driver: forward 1")
            if not await self.motion.command_move(MOVE_DISTANCE, MOVE_DURATION, MOVE_PWM, MOVE_RATIO):
                return

            logger.info("driver: rotation 2")
            if not await self.motion.command_rotation(ROTATION_ANGLE, ROTATION_PWM):
                return

            logger.info("driver: forward 2")
            if not await self.motion.command_move(MOVE_DISTANCE, MOVE_DURATION, MOVE_PWM, MOVE_RATIO):
                return

    async def setup(self):
        logger.info("driver agent ready")
        self.add_behaviour(self.DriveBehaviour())