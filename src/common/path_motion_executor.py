import logging
from typing import Optional

from common.motion_client import MotionClient


# Logger used to display motion execution progress and errors
logger = logging.getLogger(__name__)


# Executes path commands by sending movement instructions to the robot
class PathMotionExecutor:

    def __init__(
        self,
        behaviour,
        robot_jid: str,
        move_distance: float,
        move_pwm: int,
        rotation_pwm: int,
        ratio: float = 1.05,
    ):
        # Motion client used to communicate with the robot agent
        self.motion = MotionClient(behaviour, jid=robot_jid)

        # Distance used for each forward movement command
        self.move_distance = move_distance

        # PWM value used when moving forward
        self.move_pwm = move_pwm

        # PWM value used when rotating
        self.rotation_pwm = rotation_pwm

        # Calibration ratio used to fine-tune movement distance
        self.ratio = ratio

    async def rotate(self, angle_deg: float) -> bool:
        # Ignore extremely small rotations
        if abs(angle_deg) < 0.001:
            return True

        # Log the rotation command
        logger.info(f"Rotating {angle_deg:g} degrees")

        # Send signed rotation command to the robot
        return await self.motion.command_rotation(
            signed_degrees=angle_deg,
            pwm=self.rotation_pwm,
        )

    async def move_forward(
        self,
        from_cell: Optional[str] = None,
        to_cell: Optional[str] = None,
    ) -> bool:
        # Log cell-to-cell movement if path information is available
        if from_cell and to_cell:
            logger.info(f"Moving from {from_cell} to {to_cell}")

        # Otherwise log a generic forward movement
        else:
            logger.info("Moving forward")

        # Send forward movement command to the robot
        return await self.motion.command_move(
            distance=self.move_distance,
            duration=0,
            pwm=self.move_pwm,
            ratio=self.ratio,
        )

    async def execute_command(self, command: dict) -> bool:
        # Read the command action type
        action = command.get("action")

        # Execute rotation command
        if action == "rotate":
            angle_deg = command.get("angle_deg")

            # Rotation commands must include an angle
            if angle_deg is None:
                logger.error(f"Missing angle_deg in command: {command}")
                return False

            return await self.rotate(float(angle_deg))

        # Execute forward movement command
        if action == "move":
            return await self.move_forward(
                from_cell=command.get("from"),
                to_cell=command.get("to"),
            )

        # Reject unknown command types
        logger.warning(f"Unknown motion command: {command}")
        return False

    async def execute_commands(self, commands: list[dict]) -> bool:
        # Stop if there are no commands to execute
        if not commands:
            logger.warning("No motion commands to execute.")
            return False

        # Log how many commands will be executed
        logger.info(f"Executing {len(commands)} motion commands")

        # Execute commands one by one in order
        for index, command in enumerate(commands, start=1):
            logger.info(f"Command {index}/{len(commands)}: {command}")

            # Execute current command
            ok = await self.execute_command(command)

            # Stop immediately if a command fails
            if not ok:
                logger.error(f"Motion command failed at {index}: {command}")
                return False

        # All commands completed successfully
        logger.info("All motion commands executed successfully.")
        return True