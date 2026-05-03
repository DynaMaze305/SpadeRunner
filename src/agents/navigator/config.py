from __future__ import annotations

import os
from dataclasses import dataclass

from common.config import ARUCO_ANGLE_OFFSET


# Centralizes every tunable for the navigator session.
# Tests construct a NavigatorConfig directly; production reads env via from_env().
@dataclass(frozen=True)
class NavigatorConfig:
    target_cell: str = "C1"
    max_steps: int = 50
    max_bad_grid_retries: int = 5

    expected_rows: int = 3
    expected_cols: int = 11

    move_distance: float = 200.0
    move_pwm: int = 15
    rotation_pwm: int = 15
    ratio: float = 0.9
    rotation_ratio: float = 1.05

    grid_threshold_ratio: float = 0.03
    grid_min_gap: int = 15

    lookahead: int = 2

    photos_dir: str = "navigation_photos"
    request_timeout_s: int = 9999

    angle_offset_deg: float = 0.0

    rotation_tolerance_deg: float = 2.0
    max_rotation_attempts: int = 3

    # Pixel-to-millimetre conversion for the camera-cropped maze view.
    # Cell width is 200 mm, average detected cell width is ~67.5 px -> ~2.96 mm/px.
    mm_per_pixel: float = 2.96

    # Fraction of the computed distance actually sent to the robot per step.
    # 1.0 = full move, 0.5 = half move (vision re-localizes between halves), etc.
    move_distance_fraction: float = 1.0

    # Radius around the target cell center that still counts as "reached" (mm).
    cell_reached_radius_mm: float = 15.0

    @classmethod
    def from_env(cls) -> "NavigatorConfig":
        return cls(
            target_cell=os.getenv("TARGET_CELL", "C1"),
            max_steps=int(os.getenv("MAX_STEPS", "50")),
            max_bad_grid_retries=int(os.getenv("MAX_BAD_GRID_RETRIES", "5")),
            expected_rows=int(os.getenv("EXPECTED_GRID_ROWS", "3")),
            expected_cols=int(os.getenv("EXPECTED_GRID_COLS", "11")),
            move_distance=float(os.getenv("NAVIGATOR_MOVE_DISTANCE", "200")),
            move_pwm=int(os.getenv("NAVIGATOR_MOVE_PWM", "15")),
            rotation_pwm=int(os.getenv("NAVIGATOR_ROTATION_PWM", "15")),
            ratio=float(os.getenv("NAVIGATOR_RATIO", "1.02")),
            rotation_ratio=float(os.getenv("NAVIGATOR_ROTATION_RATIO", "1.05")),
            grid_threshold_ratio=float(os.getenv("NAVIGATOR_GRID_THRESHOLD_RATIO", "0.03")),
            grid_min_gap=int(os.getenv("NAVIGATOR_GRID_MIN_GAP", "15")),
            lookahead=int(os.getenv("NAVIGATOR_LOOKAHEAD", "2")),
            photos_dir=os.getenv("NAVIGATOR_PHOTOS_DIR", "navigation_photos"),
            request_timeout_s=int(os.getenv("NAVIGATOR_REQUEST_TIMEOUT_S", "9999")),
            angle_offset_deg=float(
                os.getenv("NAVIGATOR_ANGLE_OFFSET_DEG", str(ARUCO_ANGLE_OFFSET))
            ),
            rotation_tolerance_deg=float(
                os.getenv("NAVIGATOR_ROTATION_TOLERANCE_DEG", "5")
            ),
            max_rotation_attempts=int(
                os.getenv("NAVIGATOR_MAX_ROTATION_ATTEMPTS", "3")
            ),
            mm_per_pixel=float(
                os.getenv("NAVIGATOR_MM_PER_PIXEL", "2.96")
            ),
            move_distance_fraction=float(
                os.getenv(
                    "NAVIGATOR_MOVE_DISTANCE_FRACTION",
                    str(cls.move_distance_fraction),
                )
            ),
            cell_reached_radius_mm=float(
                os.getenv(
                    "NAVIGATOR_CELL_REACHED_RADIUS_MM",
                    str(cls.cell_reached_radius_mm),
                )
            ),
        )
