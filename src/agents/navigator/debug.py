from __future__ import annotations

import logging
import os

import cv2

from vision.camera import Camera


logger = logging.getLogger(__name__)


# Saves per-step debug images to disk so a navigation session can be reviewed offline.
# All renderers and the photos directory are injected so this class is reusable in tests.
class NavigatorDebug:

    def __init__(
        self,
        photos_dir: str,
        grid_detector,
        localizer,
        camera: Camera | None = None,
    ) -> None:
        self.photos_dir = photos_dir
        self.grid_detector = grid_detector
        self.localizer = localizer
        self.camera = camera or Camera()

    @staticmethod
    def fmt(v) -> str:
        return f"{v:.2f}" if isinstance(v, (int, float)) else "None"

    def save_for_step(
        self,
        step: int,
        frame,
        robot_pose=None,
    ) -> None:
        os.makedirs(self.photos_dir, exist_ok=True)

        image_with_axes = self.camera.draw_axes(frame.image)

        cv2.imwrite(
            f"{self.photos_dir}/debug_original_step_{step}.jpg",
            image_with_axes,
        )

        cv2.imwrite(
            f"{self.photos_dir}/debug_crop_step_{step}.jpg",
            frame.maze["cropped"],
        )

        cv2.imwrite(
            f"{self.photos_dir}/debug_wall_mask_step_{step}.jpg",
            frame.wall_clean,
        )

        grid_overlay = self.grid_detector.draw_grid_lines(
            wall_clean=frame.wall_clean,
            x_lines=frame.x_lines,
            y_lines=frame.y_lines,
        )
        cv2.imwrite(
            f"{self.photos_dir}/debug_grid_step_{step}.jpg",
            cv2.cvtColor(grid_overlay, cv2.COLOR_RGB2BGR),
        )

        aruco_debug = self.localizer.draw_aruco_debug(image_with_axes)
        cv2.imwrite(
            f"{self.photos_dir}/debug_aruco_step_{step}.jpg",
            aruco_debug,
        )

        if robot_pose is not None:
            robot_result = {
                "cell": robot_pose.cell,
                "angle_deg": robot_pose.angle_deg,
                "raw_angle_deg": robot_pose.raw_angle_deg,
                "center": robot_pose.center,
            }
            robot_debug = self.localizer.draw_robot_grid_debug(
                image=image_with_axes,
                robot_result=robot_result,
                crop_bbox=frame.maze["crop_bbox"],
                x_lines=frame.x_lines,
                y_lines=frame.y_lines,
            )
            cv2.imwrite(
                f"{self.photos_dir}/debug_robot_step_{step}.jpg",
                robot_debug,
            )

        logger.info(f"[DEBUG] Saved debug images for step {step}")
