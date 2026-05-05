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
    hardcoded_grid_enabled: bool = True
    hardcoded_grid_x_fractions: tuple[float, ...] = (
        0.025, 0.1077, 0.2105, 0.2932, 0.3760, 0.4586,
        0.5414, 0.6240, 0.7068, 0.7895, 0.8923, 0.975,
    )
    hardcoded_grid_y_fractions: tuple[float, ...] = (
        0.05, 0.4, 0.667, 0.9,
    )

    lookahead: int = 2

    photos_dir: str = "navigation_photos"
    request_timeout_s: int = 9999

    angle_offset_deg: float = 0.0

    rotation_tolerance_deg: float = 2.0
    max_rotation_attempts: int = 3

    # Pixel-to-millimetre conversion for the camera-cropped maze view.
    # Cell width is 200 mm, average detected cell width is ~67.5 px -> ~2.96 mm/px.
    mm_per_pixel: float = 2.96

    obstacle_avoidance_margin_px: int = 2
    robot_clearance_margin_px: int = 0
    obstacle_mini_grid_divisions: int = 5
    # Fraction of the computed distance actually sent to the robot per step.
    # 1.0 = full move, 0.5 = half move (vision re-localizes between halves), etc.
    move_distance_fraction: float = 1.0

    # Radius around the target cell center that still counts as "reached" (mm).
    cell_reached_radius_mm: float = 15.0 #hack

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_float_tuple(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
        value = os.getenv(name)
        if value is None or not value.strip():
            return default
        return tuple(
            float(part.strip())
            for part in value.split(",")
            if part.strip()
        )

    @classmethod
    def from_env(cls) -> "NavigatorConfig":
        return cls(
            target_cell=os.getenv("TARGET_CELL", cls.target_cell),
            max_steps=int(os.getenv("MAX_STEPS", str(cls.max_steps))),
            max_bad_grid_retries=int(
                os.getenv("MAX_BAD_GRID_RETRIES", str(cls.max_bad_grid_retries))
            ),
            expected_rows=int(os.getenv("EXPECTED_GRID_ROWS", str(cls.expected_rows))),
            expected_cols=int(os.getenv("EXPECTED_GRID_COLS", str(cls.expected_cols))),
            move_distance=float(
                os.getenv("NAVIGATOR_MOVE_DISTANCE", str(cls.move_distance))
            ),
            move_pwm=int(os.getenv("NAVIGATOR_MOVE_PWM", str(cls.move_pwm))),
            rotation_pwm=int(
                os.getenv("NAVIGATOR_ROTATION_PWM", str(cls.rotation_pwm))
            ),
            ratio=float(os.getenv("NAVIGATOR_RATIO", str(cls.ratio))),
            rotation_ratio=float(
                os.getenv("NAVIGATOR_ROTATION_RATIO", str(cls.rotation_ratio))
            ),
            grid_threshold_ratio=float(
                os.getenv(
                    "NAVIGATOR_GRID_THRESHOLD_RATIO",
                    str(cls.grid_threshold_ratio),
                )
            ),
            grid_min_gap=int(
                os.getenv("NAVIGATOR_GRID_MIN_GAP", str(cls.grid_min_gap))
            ),
            hardcoded_grid_enabled=cls._env_bool(
                "NAVIGATOR_HARDCODED_GRID_ENABLED",
                cls.hardcoded_grid_enabled,
            ),
            hardcoded_grid_x_fractions=cls._env_float_tuple(
                "NAVIGATOR_HARDCODED_GRID_X_FRACTIONS",
                cls.hardcoded_grid_x_fractions,
            ),
            hardcoded_grid_y_fractions=cls._env_float_tuple(
                "NAVIGATOR_HARDCODED_GRID_Y_FRACTIONS",
                cls.hardcoded_grid_y_fractions,
            ),
            lookahead=int(os.getenv("NAVIGATOR_LOOKAHEAD", str(cls.lookahead))),
            photos_dir=os.getenv("NAVIGATOR_PHOTOS_DIR", cls.photos_dir),
            request_timeout_s=int(
                os.getenv("NAVIGATOR_REQUEST_TIMEOUT_S", str(cls.request_timeout_s))
            ),
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
                os.getenv("NAVIGATOR_MM_PER_PIXEL", str(cls.mm_per_pixel))
            ),
            obstacle_avoidance_margin_px=int(
                os.getenv(
                    "NAVIGATOR_OBSTACLE_AVOIDANCE_MARGIN_PX",
                    str(cls.obstacle_avoidance_margin_px),
                )
            ),
            robot_clearance_margin_px=int(
                os.getenv(
                    "NAVIGATOR_ROBOT_CLEARANCE_MARGIN_PX",
                    str(cls.robot_clearance_margin_px),
                )
            ),
            obstacle_mini_grid_divisions=int(
                os.getenv(
                    "NAVIGATOR_OBSTACLE_MINI_GRID_DIVISIONS",
                    str(cls.obstacle_mini_grid_divisions),
                )
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
