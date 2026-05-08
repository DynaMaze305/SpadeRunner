"""
Predict the opponent's coarse path and find a bypass cell when needed.

The opponent is whichever ArUco marker we see that isn't a target marker
(1, 2) and isn't us. Their target is whichever of {1, 2} we don't have.
We run plain coarse A* (no mini-grid) so we just see WHERE they're heading,
not how they'd thread an obstacle. If they sit on a cell of our path AND
they're within 4 cells of us, we bail to the closest cell that isn't on
their predicted path.
"""

from __future__ import annotations

import logging
import string
from collections import deque

from common.config import TARGET_ARUCO_ID
from pathfinding.pathfinding import solve_from_frame


logger = logging.getLogger(__name__)


# Their target marker is whichever of {1, 2} we don't have.
OPPONENT_TARGET_ARUCO_ID: int = 2 if TARGET_ARUCO_ID == 1 else 1

# Manhattan radius below which the emergency bypass kicks in. If the
# opponent is farther than this, we don't bother running the
# "go to the closest cell off their path" fallback -- a far opponent
# is unlikely to be the actual reason plan_points failed.
EMERGENCY_AVOIDANCE_DISTANCE_CELLS: int = 3


def find_marker_cell(localizer, frame, marker_id: int) -> str | None:
    # Wraps the localizer so the orchestrator doesn't need to know which
    # specific id the OPPONENT is targeting.
    return localizer.find_marker_cell(frame, marker_id)


def opponent_target_cell(localizer, frame) -> str | None:
    return find_marker_cell(localizer, frame, OPPONENT_TARGET_ARUCO_ID)


def predict_opponent_path(
    frame, opponent_cell: str | None, opponent_target: str | None,
) -> list[str] | None:
    # Coarse-only A*. Same wall + obstacle logic as our planner, but no
    # mini-grid expansion -- this is just the route they're likely to take.
    if not opponent_cell or not opponent_target:
        return None
    if opponent_cell == opponent_target:
        return [opponent_cell]
    return solve_from_frame(frame, opponent_cell, opponent_target)


def is_opponent_blocking(
    our_path_cells: list[str] | None, opponent_cell: str | None,
) -> bool:
    if not our_path_cells or not opponent_cell:
        return False
    return opponent_cell in our_path_cells


def manhattan_cells(a: str | None, b: str | None) -> int | None:
    ar = _cell_rc(a)
    br = _cell_rc(b)
    if ar is None or br is None:
        return None
    return abs(ar[0] - br[0]) + abs(ar[1] - br[1])


def find_bypass_cell(
    frame,
    our_cell: str,
    opponent_path: list[str] | None,
    blocked_for_expansion: set[str] | None = None,
) -> str | None:
    # BFS through the wall graph from our_cell. Returns the closest cell
    # that is NOT on the opponent's predicted path. `blocked_for_expansion`
    # cells (typically the opponent's CURRENT cell) are treated as walls
    # for the BFS itself so we only find cells reachable without driving
    # THROUGH the opponent -- otherwise the BFS would happily walk past
    # them and pick a candidate on the far side, forcing the bypass plan
    # to take the long way around.
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


# 4-orthogonal neighbours that have no wall between them. Wall convention
# matches src/pathfinding/mini_grid_planner.py:_parent_step_is_open --
# walls["top"] is the boundary toward row+1, walls["bottom"] is the
# boundary toward row-1.
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


def _rc_cell(row: int, col: int, n_rows: int, n_cols: int) -> str | None:
    if row < 0 or col < 0 or row >= n_rows or col >= n_cols:
        return None
    return f"{string.ascii_uppercase[row]}{col + 1}"
