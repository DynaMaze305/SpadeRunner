from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vision.robot_grid_localizer import RobotGridLocalizer


# Typed view of the robot localization result, decoupled from the underlying
# RobotGridLocalizer dict shape.
@dataclass
class RobotPose:
    cell: str | None
    angle_deg: float
    raw_angle_deg: float
    center: tuple[int, int]
    pose: dict
    corners: Any
    ids: Any


# Wraps RobotGridLocalizer so the orchestrator consumes a VisionFrame instead
# of having to feed the raw image + crop_bbox + grid lines.
class RobotLocalizationStep:

    def __init__(self, angle_offset_deg: float = 0.0) -> None:
        self.localizer = RobotGridLocalizer(angle_offset_deg=angle_offset_deg)

    def locate(self, frame) -> RobotPose | None:
        result = self.localizer.detect_robot_cell(
            image=frame.image,
            crop_bbox=frame.maze["crop_bbox"],
            x_lines=frame.x_lines,
            y_lines=frame.y_lines,
        )
        if result is None:
            return None

        return RobotPose(
            cell=result["cell"],
            angle_deg=result["angle_deg"],
            raw_angle_deg=result["raw_angle_deg"],
            center=result["center"],
            pose=result["pose"],
            corners=result["corners"],
            ids=result["ids"],
        )
