import os
import cv2
import numpy as np
from vision.camera import Camera
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHOTOS_DIR = "navigation_photos"


class NavigatorDebug:

    @staticmethod
    def fmt(v):
        return f"{v:.2f}" if isinstance(v, (int, float)) else "None"
    
    def save_debug_images(
                self,
                step: int,
                image,
                maze,
                wall_clean,
                grid_detector,
                x_lines,
                y_lines,
                localizer=None,
                robot=None,
            ) -> None:
                os.makedirs(PHOTOS_DIR, exist_ok=True)

                camera_utils = Camera()
                image_with_axes = camera_utils.draw_axes(image)

                cv2.imwrite(
                    f"{PHOTOS_DIR}/debug_original_step_{step}.jpg",
                    image_with_axes,
                )

                cv2.imwrite(
                    f"{PHOTOS_DIR}/debug_crop_step_{step}.jpg",
                    maze["cropped"],
                )

                cv2.imwrite(
                    f"{PHOTOS_DIR}/debug_wall_mask_step_{step}.jpg",
                    wall_clean,
                )

                grid_overlay = grid_detector.draw_grid_lines(
                    wall_clean=wall_clean,
                    x_lines=x_lines,
                    y_lines=y_lines,
                )

                cv2.imwrite(
                    f"{PHOTOS_DIR}/debug_grid_step_{step}.jpg",
                    cv2.cvtColor(grid_overlay, cv2.COLOR_RGB2BGR),
                )

                if localizer is not None:
                    aruco_debug = localizer.draw_aruco_debug(image_with_axes)

                    cv2.imwrite(
                        f"{PHOTOS_DIR}/debug_aruco_step_{step}.jpg",
                        aruco_debug,
                    )

                if robot is not None and localizer is not None:
                    robot_debug = localizer.draw_robot_grid_debug(
                        image=image_with_axes,
                        robot_result=robot,
                        crop_bbox=maze["crop_bbox"],
                        x_lines=x_lines,
                        y_lines=y_lines,
                    )

                    cv2.imwrite(
                        f"{PHOTOS_DIR}/debug_robot_step_{step}.jpg",
                        robot_debug,
                    )

                logger.info(f"[DEBUG] Saved debug images for step {step}")