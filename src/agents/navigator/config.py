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

    obstacle_avoidance_margin_px: int = 5
    robot_clearance_margin_px: int = 0
    contour_demo_padding_px: int = 25
    contour_waypoint_reached_px: int = 8

    # Fraction of the computed distance actually sent to the robot per step.
    # 1.0 = full move, 0.5 = half move (vision re-localizes between halves), etc.
    move_distance_fraction: float = 1.0

    # Radius around the target cell center that still counts as "reached" (mm).
    cell_reached_radius_mm: float = 15.0

    # Set to False to skip obstacle detection entirely (debug / no obstacles in scene).
    obstacles_enabled: bool = True

    # Path to a saved maze JSON; honored only when use_saved_maze is True.
    maze_file: str | None = None

    # Debug toggle: when True the navigator skips wall detection and replays
    # maze_file. Off by default — saved-maze mode is for debugging only.
    use_saved_maze: bool = False

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
            contour_demo_padding_px=int(
                os.getenv(
                    "NAVIGATOR_CONTOUR_DEMO_PADDING_PX",
                    str(cls.contour_demo_padding_px),
                )
            ),
            contour_waypoint_reached_px=int(
                os.getenv(
                    "NAVIGATOR_CONTOUR_WAYPOINT_REACHED_PX",
                    str(cls.contour_waypoint_reached_px),
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
            obstacles_enabled=os.getenv(
                "NAVIGATOR_OBSTACLES_ENABLED",
                "1" if cls.obstacles_enabled else "0",
            ) == "1",
            maze_file=os.getenv("MAZE_FILE", cls.maze_file) or None,
            use_saved_maze=os.getenv(
                "NAVIGATOR_USE_SAVED_MAZE",
                "1" if cls.use_saved_maze else "0",
            ) == "1",
        )
