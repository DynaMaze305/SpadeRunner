from __future__ import annotations

import os
from dataclasses import dataclass


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
    ratio: float = 1.02

    grid_threshold_ratio: float = 0.03
    grid_min_gap: int = 15

    lookahead: int = 2

    photos_dir: str = "navigation_photos"
    request_timeout_s: int = 9999

    angle_offset_deg: float = 0.0

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
            grid_threshold_ratio=float(os.getenv("NAVIGATOR_GRID_THRESHOLD_RATIO", "0.03")),
            grid_min_gap=int(os.getenv("NAVIGATOR_GRID_MIN_GAP", "15")),
            lookahead=int(os.getenv("NAVIGATOR_LOOKAHEAD", "2")),
            photos_dir=os.getenv("NAVIGATOR_PHOTOS_DIR", "navigation_photos"),
            request_timeout_s=int(os.getenv("NAVIGATOR_REQUEST_TIMEOUT_S", "9999")),
            angle_offset_deg=float(os.getenv("NAVIGATOR_ANGLE_OFFSET_DEG", "0")),
        )
