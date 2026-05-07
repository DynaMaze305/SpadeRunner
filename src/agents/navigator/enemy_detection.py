"""
Detect enemy ArUco markers in a vision frame and report their maze cells.

An "enemy" is any detected marker whose ID is neither this bot's own marker
(common.config.ARUCO_ID) nor a known non-enemy marker (the target marker(s)
placed in the maze). Anything else is assumed to be an opponent robot.

Detected enemy cells are returned to the planner so it can treat them as
instantly blocked for path-finding (they refresh every step).
"""

from __future__ import annotations

import logging
import string
from dataclasses import dataclass

import numpy as np

from common.config import ARUCO_ID

logger = logging.getLogger(__name__)

# Markers that are NEVER enemies. Our own marker plus the "target" / static
# markers placed in the maze. Update if you add more reserved IDs.
NON_ENEMY_IDS: frozenset[int] = frozenset({ARUCO_ID, 1, 2})


# One detected enemy marker. `corners` are in FULL-image pixel coords (the
# robot debug panel is drawn on the full image, not the crop).
@dataclass
class EnemyMarker:
    marker_id: int
    cell: str
    corners: np.ndarray


def detect_enemies(frame, aruco_detector) -> list[EnemyMarker]:
    if frame is None or getattr(frame, "image", None) is None:
        return []

    corners_list, ids, _ = aruco_detector.detect(frame.image)
    if ids is None or corners_list is None:
        return []

    crop_x1, crop_y1 = frame.maze["crop_bbox"][:2]
    enemies: list[EnemyMarker] = []

    for marker_corners, marker_id in zip(corners_list, ids.flatten()):
        marker_id = int(marker_id)
        if marker_id in NON_ENEMY_IDS:
            continue

        pts = np.asarray(marker_corners).reshape(-1, 2)
        if pts.size == 0:
            continue
        cx = float(pts[:, 0].mean()) - crop_x1
        cy = float(pts[:, 1].mean()) - crop_y1

        cell = _cell_for_local_point(cx, cy, frame.x_lines, frame.y_lines)
        if cell is None:
            continue

        enemies.append(EnemyMarker(marker_id=marker_id, cell=cell, corners=pts))
        logger.info(f"[ENEMY] aruco {marker_id} -> cell {cell}")

    return enemies


def detect_enemy_cells(frame, aruco_detector) -> set[str]:
    return {e.cell for e in detect_enemies(frame, aruco_detector)}


def _cell_for_local_point(
    x: float, y: float, x_lines: list[int], y_lines: list[int],
) -> str | None:
    col = _line_interval_index(x, x_lines)
    row = _line_interval_index(y, y_lines)
    if row is None or col is None or row >= len(string.ascii_uppercase):
        return None
    return f"{string.ascii_uppercase[row]}{col + 1}"


def _line_interval_index(value: float, lines: list[int]) -> int | None:
    for index in range(len(lines) - 1):
        if lines[index] <= value < lines[index + 1]:
            return index
    return None
