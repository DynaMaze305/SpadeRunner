from __future__ import annotations

import math
import string

import cv2
import numpy as np

from vision.aruco_detector import ArucoDetector


# ArUco marker ID attached to the robot
TARGET_ID = 8


# Detects the robot position and orientation inside the maze grid
class RobotGridLocalizer:

    def __init__(self, angle_offset_deg: float) -> None:
        # ArUco detector used to find the robot marker
        self.aruco = ArucoDetector()

        # Angle correction applied to align marker direction with robot direction
        self.angle_offset_deg = angle_offset_deg

    def point_to_cell(
        self,
        point: tuple[int, int],
        crop_bbox: tuple[int, int, int, int],
        x_lines: list[int],
        y_lines: list[int],
    ) -> str | None:
        # Extract point coordinates in the full image
        px, py = point

        # Extract crop origin
        x1, y1, _, _ = crop_bbox

        # Convert full-image coordinates into cropped-image coordinates
        local_x = px - x1
        local_y = py - y1

        # If the point is outside the crop, it cannot belong to a cell
        if local_x < 0 or local_y < 0:
            return None

        col = None
        row = None

        # Find which column contains the x coordinate
        for c in range(len(x_lines) - 1):
            if x_lines[c] <= local_x < x_lines[c + 1]:
                col = c
                break

        # Find which row contains the y coordinate
        for r in range(len(y_lines) - 1):
            if y_lines[r] <= local_y < y_lines[r + 1]:
                row = r
                break

        # If no matching row or column was found, the point is outside the grid
        if row is None or col is None:
            return None

        # Convert row/column indexes into a cell label like A1, B2, etc.
        return f"{string.ascii_uppercase[row]}{col + 1}"

    def detect_robot_cell(
        self,
        image: np.ndarray,
        crop_bbox: tuple[int, int, int, int],
        x_lines: list[int],
        y_lines: list[int],
    ):
        # Detect the robot ArUco marker in the full image
        result = self.aruco.detect_pose(image, target_id=TARGET_ID)

        # Extract the marker pose result
        pose = result["pose"]

        # If the marker was not detected, robot position cannot be computed
        if pose is None:
            return None

        # Marker center in full-image coordinates
        center = pose["center"]

        # Convert marker center into a maze cell label
        cell = self.point_to_cell(
            point=center,
            crop_bbox=crop_bbox,
            x_lines=x_lines,
            y_lines=y_lines,
        )

        # Read raw angle from ArUco detection
        raw_angle = pose["angle_deg"]

        # Correct the marker angle so it matches the robot heading
        corrected_angle = self.aruco.correct_angle(
            raw_angle,
            self.angle_offset_deg,
        )

        # Return robot localization data and raw detection output
        return {
            "cell": cell,
            "center": center,
            "angle_deg": corrected_angle,
            "raw_angle_deg": raw_angle,
            "pose": pose,
            "corners": result["corners"],
            "ids": result["ids"],
        }

    def draw_robot_grid_debug(
        self,
        image: np.ndarray,
        robot_result: dict | None,
        crop_bbox: tuple[int, int, int, int],
        x_lines: list[int],
        y_lines: list[int],
    ) -> np.ndarray:
        # Extract crop coordinates
        x1, y1, x2, y2 = crop_bbox

        # Crop the image so the debug view focuses only on the maze
        cropped = image[y1:y2, x1:x2].copy()

        # Draw vertical grid lines
        for x in x_lines:
            cv2.line(
                cropped,
                (x, 0),
                (x, cropped.shape[0] - 1),
                (255, 0, 0),
                1,
            )

        # Draw horizontal grid lines
        for y in y_lines:
            cv2.line(
                cropped,
                (0, y),
                (cropped.shape[1] - 1, y),
                (0, 255, 0),
                1,
            )

        # If no robot was detected, return only the grid debug image
        if robot_result is None:
            return cropped

        # Get robot center in full-image coordinates
        cx, cy = robot_result["center"]

        # Convert robot center to cropped-image coordinates
        local_center = (cx - x1, cy - y1)

        # Get corrected robot angle, raw marker angle, and detected cell
        angle_deg = robot_result["angle_deg"]
        raw_angle = robot_result.get("raw_angle_deg")
        cell = robot_result["cell"]

        # Draw robot center point
        cv2.circle(cropped, local_center, 5, (0, 255, 255), -1)

        # Convert angle from degrees to radians for trigonometry
        angle_rad = math.radians(angle_deg)

        # Compute arrow endpoint from angle and fixed arrow length
        end = (
            int(local_center[0] + 35 * math.cos(angle_rad)),
            int(local_center[1] + 35 * math.sin(angle_rad)),
        )

        # Draw robot direction arrow
        cv2.arrowedLine(cropped, local_center, end, (0, 255, 255), 2)

        # Build debug label showing cell and angle information
        label = f"{cell} {angle_deg:.1f} deg"
        if raw_angle is not None:
            label += f" raw={raw_angle:.1f}"

        # Draw debug label near the robot
        cv2.putText(
            cropped,
            label,
            (local_center[0] - 80, local_center[1] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return cropped

    def draw_aruco_debug(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        # Detect ArUco marker and rejected marker candidates
        result = self.aruco.detect_pose(image, target_id=TARGET_ID)

        # Work on a copy so the original image stays unchanged
        output = image.copy()

        # Draw detected ArUco marker borders and IDs
        output = self.aruco.draw_detected_markers(
            output,
            result["corners"],
            result["ids"],
        )

        # Draw rejected ArUco candidates in red for debugging detection problems
        rejected = result["rejected"]
        if rejected is not None:
            for candidate in rejected:
                pts = candidate.astype(int)
                cv2.polylines(output, [pts], True, (0, 0, 255), 2)

        # Extract pose information for the target marker
        pose = result["pose"]

        if pose is not None:
            # Draw marker center
            center = pose["center"]
            cv2.circle(output, center, 6, (0, 255, 255), -1)

            # Get raw detected marker angle
            marker_angle = pose["angle_deg"]
            raw_robot_angle = marker_angle

            # Correct angle so the arrow points in the robot's real direction
            corrected_angle = self.aruco.correct_angle(
                raw_robot_angle,
                self.angle_offset_deg,
            )

            # Draw corrected robot direction arrow
            output = self.aruco.draw_arrow(
                output,
                center,
                corrected_angle,
                length=50,
                thickness=2,
            )

            # Draw angle debugging text
            cv2.putText(
                output,
                f"marker={marker_angle:.1f} raw={raw_robot_angle:.1f} corrected={corrected_angle:.1f}",
                (center[0] - 120, center[1] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        else:
            # Show clear warning when no marker is detected
            cv2.putText(
                output,
                "NO ARUCO DETECTED",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        return output