from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# All possible end states of one navigation session.
class NavigationOutcome(Enum):
    REACHED = "reached"
    FAILED_NO_IMAGE = "failed_no_image"
    FAILED_NO_MAZE = "failed_no_maze"
    FAILED_BAD_GRID = "failed_bad_grid"
    FAILED_NO_ROBOT = "failed_no_robot"
    FAILED_NO_PATH = "failed_no_path"
    FAILED_EXECUTION = "failed_execution"
    FAILED_MAX_STEPS = "failed_max_steps"


# Final report from NavigationOrchestrator.run().
# The behaviour translates this into a single reply Message.
@dataclass
class NavigationResult:
    outcome: NavigationOutcome
    last_cell: str | None = None
    steps_taken: int = 0
    message: str = ""
