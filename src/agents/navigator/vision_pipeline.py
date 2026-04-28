from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from vision.camera import Camera
from vision.color_detector_image_cropper import ColorDetectorImageCropper
from vision.contour_processor import ContourProcessor
from vision.grid_detector import GridDetector
from vision.maze_grid_analyzer import MazeGridAnalyzer


# Failure codes returned by MazeVisionPipeline.analyze when no usable frame can be produced.
class VisionError(Enum):
    NO_IMAGE = "no_image"
    NO_MAZE = "no_maze"


# Single source of truth for one frame's vision state.
# Holds the decoded image plus every intermediate the orchestrator needs downstream
# (localization, planning, debug rendering) so nothing has to redo the pipeline.
@dataclass
class VisionFrame:
    image: np.ndarray
    image_bytes: bytes
    maze: dict
    wall_clean: np.ndarray
    x_lines: list[int]
    y_lines: list[int]
    n_rows: int
    n_cols: int
    grid_walls: dict[str, dict[str, bool]]


# Runs the full pink-mask -> walls -> grid -> walls-dict pipeline once per frame.
# Detector instances are constructed once and reused across calls.
class MazeVisionPipeline:

    def __init__(
        self,
        threshold_ratio: float = 0.03,
        min_gap: int = 15,
        wall_threshold: int = 100,
    ) -> None:
        self.threshold_ratio = threshold_ratio
        self.min_gap = min_gap
        self.wall_threshold = wall_threshold

        self.camera = Camera()
        self.cropper = ColorDetectorImageCropper()
        self.contour = ContourProcessor()
        self.grid = GridDetector()
        self.analyzer = MazeGridAnalyzer()

    def analyze(self, image_bytes: bytes | None) -> VisionFrame | VisionError:
        if image_bytes is None:
            return VisionError.NO_IMAGE

        try:
            image = Camera.decode_image(image_bytes)
        except ValueError:
            return VisionError.NO_IMAGE

        maze = self.cropper.detect_and_crop_pink_object(image)
        if maze is None:
            return VisionError.NO_MAZE

        cropped_mask = maze["cropped_mask"]
        wall_bin = self.contour.create_wall_binary(cropped_mask)
        wall_clean = self.contour.clean_wall_mask(wall_bin)

        grid_result = self.grid.detect_grid_lines(
            wall_clean,
            threshold_ratio=self.threshold_ratio,
            min_gap=self.min_gap,
        )
        x_lines: list[int] = grid_result["x_lines"]
        y_lines: list[int] = grid_result["y_lines"]

        n_rows = max(0, len(y_lines) - 1)
        n_cols = max(0, len(x_lines) - 1)

        if n_rows > 0 and n_cols > 0:
            grid_walls = self.analyzer.build_grid_walls(
                wall_clean=wall_clean,
                x_lines=x_lines,
                y_lines=y_lines,
                threshold=self.wall_threshold,
            )
        else:
            grid_walls = {}

        return VisionFrame(
            image=image,
            image_bytes=image_bytes,
            maze=maze,
            wall_clean=wall_clean,
            x_lines=x_lines,
            y_lines=y_lines,
            n_rows=n_rows,
            n_cols=n_cols,
            grid_walls=grid_walls,
        )
