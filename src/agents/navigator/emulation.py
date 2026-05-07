from __future__ import annotations

import logging
import math
from typing import Awaitable, Callable, Optional

import cv2
import numpy as np

from agents.navigator.localization import RobotLocalizationStep, RobotPose

logger = logging.getLogger(__name__)


def seeded_photo_source(
    seed_path: str,
    real_source: Callable[[str], Awaitable[Optional[bytes]]],
) -> Callable[[str], Awaitable[Optional[bytes]]]:
    served = False

    async def source(label: str) -> Optional[bytes]:
        nonlocal served
        if not served:
            with open(seed_path, "rb") as f:
                raw = f.read()
            # Saved per-step raw.jpg files are post-rotation (right-side-up).
            # The vision pipeline always 180-rotates incoming bytes inside
            # Camera.decode_image, so we counter-rotate here to mimic raw
            # upside-down camera bytes.
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"could not decode seed image {seed_path}")
            img = cv2.rotate(img, cv2.ROTATE_180)
            ok, encoded = cv2.imencode(".jpg", img)
            if not ok:
                raise ValueError(f"could not re-encode seed image {seed_path}")
            served = True
            logger.info(f"[EMU] seeded first photo from {seed_path}")
            return encoded.tobytes()
        return await real_source(label)

    return source


# Tracks the simulated robot pose. Seeded once from the real localizer on the
# first frame, then advanced by motion deltas the FakeExecutor reports.
class SimulationState:
    def __init__(self, mm_per_pixel: float) -> None:
        self.mm_per_pixel = mm_per_pixel
        self._seeded = False
        self._cx: float = 0.0
        self._cy: float = 0.0
        self._angle: float = 0.0
        self._x_lines: list[int] = []
        self._y_lines: list[int] = []
        self._crop_x1: int = 0
        self._crop_y1: int = 0

    def is_seeded(self) -> bool:
        return self._seeded

    def seed(self, robot_pose: RobotPose, frame) -> None:
        self._seeded = True
        self._cx = float(robot_pose.center[0])
        self._cy = float(robot_pose.center[1])
        self._angle = self._normalize(robot_pose.angle_deg)
        self._x_lines = list(frame.x_lines)
        self._y_lines = list(frame.y_lines)
        crop = frame.maze["crop_bbox"]
        self._crop_x1 = int(crop[0])
        self._crop_y1 = int(crop[1])
        logger.info(
            f"[EMU] seeded pose cell={robot_pose.cell} "
            f"angle={self._angle:.1f} center=({self._cx:.0f}, {self._cy:.0f})"
        )

    def apply_rotate(self, delta_deg: float) -> None:
        self._angle = self._normalize(self._angle + float(delta_deg))

    # PathCommandConverter uses atan2(-dy, dx) so angle 0 = +x and +90 = -y in
    # image coordinates. The reverse projection matches that convention.
    def apply_move(self, distance_mm: float) -> None:
        distance_px = float(distance_mm) / self.mm_per_pixel
        rad = math.radians(self._angle)
        self._cx += distance_px * math.cos(rad)
        self._cy += distance_px * (-math.sin(rad))

    def current_pose(self) -> RobotPose:
        cx, cy = int(round(self._cx)), int(round(self._cy))
        cell = self._cell_for(cx, cy)
        return RobotPose(
            cell=cell,
            angle_deg=self._angle,
            raw_angle_deg=self._angle,
            center=(cx, cy),
            pose={},
            corners=None,
            ids=None,
        )

    def _cell_for(self, full_x: int, full_y: int) -> Optional[str]:
        local_x = full_x - self._crop_x1
        local_y = full_y - self._crop_y1
        col = self._index_in_lines(local_x, self._x_lines)
        row = self._index_in_lines(local_y, self._y_lines)
        if col is None or row is None:
            return None
        return chr(ord("A") + row) + str(col + 1)

    @staticmethod
    def _index_in_lines(coord: int, lines: list[int]) -> Optional[int]:
        for i in range(len(lines) - 1):
            if lines[i] <= coord < lines[i + 1]:
                return i
        return None

    @staticmethod
    def _normalize(angle: float) -> float:
        return (float(angle) + 180.0) % 360.0 - 180.0


class FakeLocalizer:
    def __init__(self, real: RobotLocalizationStep, sim: SimulationState) -> None:
        self.real = real
        self.sim = sim

    def locate(self, frame) -> Optional[RobotPose]:
        if not self.sim.is_seeded():
            pose = self.real.locate(frame)
            if pose is None:
                return None
            self.sim.seed(pose, frame)
            return pose
        return self.sim.current_pose()

    def find_marker_cell(self, frame, target_id: int) -> Optional[str]:
        return self.real.find_marker_cell(frame, target_id)


class FakeExecutor:
    def __init__(self, sim: SimulationState) -> None:
        self.sim = sim

    async def execute_command(self, command: dict) -> bool:
        action = command.get("action")
        if action == "move":
            distance_mm = command.get("distance_mm")
            if distance_mm is None:
                logger.error(f"[EMU] missing distance_mm: {command}")
                return False
            self.sim.apply_move(float(distance_mm))
            logger.info(f"[EMU] move applied {float(distance_mm):.0f} mm")
            return True
        if action == "rotate":
            delta = command.get("angle_deg")
            if delta is None:
                logger.error(f"[EMU] missing angle_deg: {command}")
                return False
            self.sim.apply_rotate(float(delta))
            logger.info(f"[EMU] rotate applied {float(delta):+.1f} deg")
            return True
        logger.warning(f"[EMU] unknown action: {action}")
        return False

    async def rotate(self, angle_deg: float) -> bool:
        self.sim.apply_rotate(float(angle_deg))
        logger.info(f"[EMU] rotate applied {float(angle_deg):+.1f} deg")
        return True
