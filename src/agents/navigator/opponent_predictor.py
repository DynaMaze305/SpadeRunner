"""
Predict the opponent's coarse path and find a bypass cell when needed.
"""

from __future__ import annotations

import logging
import string
from collections import deque

from common.config import TARGET_ARUCO_ID
from pathfinding.pathfinding import solve_from_frame


logger = logging.getLogger(__name__)


# Opponent's target ArUco id, the one of {1, 2} that isn't ours.
OPPONENT_TARGET_ARUCO_ID: int = 2 if TARGET_ARUCO_ID == 1 else 1

# Manhattan radius for triggering emergency avoidance.
EMERGENCY_AVOIDANCE_DISTANCE_CELLS: int = 2


# Look up which cell a given ArUco marker sits in.
def find_marker_cell(localizer, frame, marker_id: int) -> str | None:
    return localizer.find_marker_cell(frame, marker_id)


# Cell where the opponent's goal ArUco sits this frame.
def opponent_target_cell(localizer, frame) -> str | None:
    return find_marker_cell(localizer, frame, OPPONENT_TARGET_ARUCO_ID)


# Coarse cell A* from opponent to their target, no mini-grid.
def predict_opponent_path(
    frame, opponent_cell: str | None, opponent_target: str | None,
) -> list[str] | None:
    if not opponent_cell or not opponent_target:
        return None
    if opponent_cell == opponent_target:
        return [opponent_cell]
    return solve_from_frame(frame, opponent_cell, opponent_target)


# True when the opponent's cell lies on our planned path.
def is_opponent_blocking(
    our_path_cells: list[str] | None, opponent_cell: str | None,
) -> bool:
    if not our_path_cells or not opponent_cell:
        return False
    return opponent_cell in our_path_cells


# Manhattan distance in cells between two grid labels.
def manhattan_cells(a: str | None, b: str | None) -> int | None:
    ar = _cell_rc(a)
    br = _cell_rc(b)
    if ar is None or br is None:
        return None
    return abs(ar[0] - br[0]) + abs(ar[1] - br[1])


# Closest cell reachable from our_cell that is off the opponent's path.
def find_bypass_cell(
    frame,
    our_cell: str,
    opponent_path: list[str] | None,
    blocked_for_expansion: set[str] | None = None,
) -> str | None:
    forbidden = set(opponent_path or [])
    expand_blocked = set(blocked_for_expansion or [])
    visited = {our_cell}
    queue: deque[str] = deque([our_cell])
    while queue:
        cell = queue.popleft()
        if cell != our_cell and cell not in forbidden:
            return cell
        for nb in _neighbors(cell, frame):
            if nb in visited or nb in expand_blocked:
                continue
            visited.add(nb)
            queue.append(nb)
    return None


# Adjacent cells with no wall between them.
def _neighbors(cell: str, frame) -> list[str]:
    rc = _cell_rc(cell)
    if rc is None:
        return []
    walls = frame.grid_walls.get(cell, {}) or {}
    out: list[str] = []
    if not walls.get("right", True):
        nb = _rc_cell(rc[0], rc[1] + 1, frame.n_rows, frame.n_cols)
        if nb is not None:
            out.append(nb)
    if not walls.get("left", True):
        nb = _rc_cell(rc[0], rc[1] - 1, frame.n_rows, frame.n_cols)
        if nb is not None:
            out.append(nb)
    if not walls.get("top", True):
        nb = _rc_cell(rc[0] + 1, rc[1], frame.n_rows, frame.n_cols)
        if nb is not None:
            out.append(nb)
    if not walls.get("bottom", True):
        nb = _rc_cell(rc[0] - 1, rc[1], frame.n_rows, frame.n_cols)
        if nb is not None:
            out.append(nb)
    return out


# Parse a cell label like B5 into row col indices.
def _cell_rc(label: str | None) -> tuple[int, int] | None:
    if not label or len(label) < 2:
        return None
    row = string.ascii_uppercase.find(label[0].upper())
    if row < 0:
        return None
    try:
        col = int(label[1:]) - 1
    except ValueError:
        return None
    if col < 0:
        return None
    return (row, col)


# Build a cell label from row and col indices.
def _rc_cell(row: int, col: int, n_rows: int, n_cols: int) -> str | None:
    if row < 0 or col < 0 or row >= n_rows or col >= n_cols:
        return None
    return f"{string.ascii_uppercase[row]}{col + 1}"
