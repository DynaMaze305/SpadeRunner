from __future__ import annotations

import math
import cv2
import cv2.aruco as aruco
import numpy as np

from vision.camera import Camera


# Detects ArUco markers and extracts their 2D position and orientation
class ArucoDetector:

    def __init__(self, dictionary=aruco.DICT_4X4_50, marker_size: float = 20.0) -> None:
        # Load the predefined ArUco dictionary used for marker detection
        self.aruco_dict = aruco.getPredefinedDictionary(dictionary)

        # Create detector parameters with OpenCV defaults
        self.parameters = aruco.DetectorParameters()

        # Create the ArUco detector object
        self.detector = aruco.ArucoDetector(self.aruco_dict, self.parameters)

        # Physical or logical marker size used for homography mapping
        self.marker_size = marker_size

    def detect(self, image: np.ndarray):
        # Detect ArUco markers in the image
        corners, ids, rejected = self.detector.detectMarkers(image)

        return corners, ids, rejected

    def draw_detected_markers(
        self,
        image: np.ndarray,
        corners,
        ids,
    ) -> np.ndarray:
        # Work on a copy so the original image is not modified
        output = image.copy()

        # Draw marker borders and IDs if markers were detected
        if ids is not None:
            aruco.drawDetectedMarkers(output, corners, ids)

        return output

    def get_marker_corners(self, corners, index: int = 0) -> np.ndarray:
        # Stop if no marker corners are available
        if corners is None or len(corners) == 0:
            raise ValueError("No marker corners available.")

        # Return the selected marker corners as float32 points
        return corners[index][0].astype(np.float32)

    def get_marker_center(self, pts: np.ndarray) -> tuple[int, int]:
        # Compute the center point by averaging the four marker corners
        center = pts.mean(axis=0)

        # Convert center coordinates to integers for drawing/indexing
        cx, cy = center.astype(int)

        return int(cx), int(cy)

    def get_marker_angle_2d(self, pts: np.ndarray) -> float:
        # Unpack marker corners in OpenCV order
        top_left, top_right, bottom_right, bottom_left = pts

        # Compute marker center
        center = pts.mean(axis=0)

        # Use the bottom edge midpoint as the marker "front" direction
        front_mid = (bottom_left + bottom_right) / 2.0

        # Horizontal vector from center to front
        dx = front_mid[0] - center[0]

        # Vertical vector from center to front
        # Image y-axis points downward, so invert it for math-style angle coordinates
        dy = center[1] - front_mid[1]

        # Convert vector direction to angle in degrees
        angle_deg = np.degrees(np.arctan2(dy, dx))

        return float(angle_deg)

    def get_marker_homography(self, pts: np.ndarray) -> np.ndarray:
        # Define destination square coordinates for a normalized marker plane
        dst_pts = np.array(
            [
                [0, 0],
                [self.marker_size, 0],
                [self.marker_size, self.marker_size],
                [0, self.marker_size],
            ],
            dtype=np.float32,
        )

        # Compute perspective transform from detected marker to normalized square
        return cv2.getPerspectiveTransform(pts, dst_pts)

    def get_marker_pose_2d(
        self,
        corners,
        ids,
        target_id: int | None = None,
        index: int = 0,
    ):
        # If no markers were detected, no pose can be computed
        if ids is None or corners is None or len(corners) == 0:
            return None

        # Flatten ids for easier searching
        ids_flat = ids.flatten()

        # If a target marker ID is provided, find its index
        if target_id is not None:
            matches = np.where(ids_flat == target_id)[0]

            # Return None if the requested marker is not detected
            if len(matches) == 0:
                return None

            index = matches[0]

        # Otherwise use the first detected marker
        else:
            index = 0

        # Get selected marker geometry
        pts = self.get_marker_corners(corners, index)

        # Compute center, angle, and homography for the marker
        cx, cy = self.get_marker_center(pts)
        angle_deg = self.get_marker_angle_2d(pts)
        homography = self.get_marker_homography(pts)

        # Return useful 2D pose information
        return {
            "id": int(ids[index][0]),
            "corners": pts,
            "center": (cx, cy),
            "angle_deg": angle_deg,
            "homography": homography,
        }

    def detect_pose(self, image: np.ndarray, target_id: int | None = None):
        # Detect marker corners, IDs, and rejected candidates
        corners, ids, rejected = self.detect(image)

        # Extract 2D pose for the selected marker
        pose = self.get_marker_pose_2d(corners, ids, target_id)

        return {
            "corners": corners,
            "ids": ids,
            "rejected": rejected,
            "pose": pose,
        }

    def detect_pose_from_path(self, image_path: str, index: int = 0):
        # Load image from disk
        cam = Camera()
        image = cam.imread(image_path)

        # Detect marker pose in the loaded image
        return self.detect_pose(image, index)

    def detect_qr_angle_pose(self, image_path: str):
        # Detect marker pose from an image path
        result = self.detect_pose_from_path(image_path)

        # Extract pose data
        pose = result["pose"]

        # Return None if no marker pose was found
        if pose is None:
            return None

        # Extract marker center coordinates
        cx, cy = pose["center"]

        # Return simplified angle and position data
        return {
            "angle_deg": -pose["angle_deg"],
            "x": float(cx),
            "y": float(cy),
        }

    @staticmethod
    def angle_diff(new: float, old: float) -> float:
        # Compute the shortest signed difference between two angles
        # Result is normalized to the range [-180, 180]
        return (new - old + 180.0) % 360.0 - 180.0

    @staticmethod
    def correct_angle(angle_deg: float, offset_deg: float) -> float:
        # Apply an offset to an angle and normalize the result to [-180, 180]
        return (angle_deg + offset_deg + 180.0) % 360.0 - 180.0

    def draw_point(
        self,
        image: np.ndarray,
        point: tuple[int, int],
    ) -> np.ndarray:
        # Work on a copy so the original image is not modified
        output = image.copy()

        # Draw a small point at the given coordinate
        cv2.circle(output, point, 2, (0, 255, 128), -1)

        return output

    def draw_arrow(
        self,
        image: np.ndarray,
        point: tuple[int, int],
        angle_deg: float,
        length: int = 10,
        thickness: int = 1,
    ) -> np.ndarray:
        # Work on a copy so the original image is not modified
        output = image.copy()

        # Extract arrow start point
        cx, cy = point

        # Convert angle from degrees to radians
        angle_rad = math.radians(angle_deg)

        # Compute arrow end point
        # X increases to the right
        # Y is subtracted because image coordinates increase downward
        end = (
            int(cx + length * math.cos(angle_rad)),
            int(cy - length * math.sin(angle_rad)),
        )

        # Draw arrow representing marker direction
        cv2.arrowedLine(output, (cx, cy), end, (0, 255, 128), thickness)

        return output

    def draw_axes(
        self,
        image: np.ndarray,
        origin: tuple[int, int] = (60, 60),
        length: int = 40,
    ) -> np.ndarray:
        # Work on a copy so the original image is not modified
        output = image.copy()

        # Extract axis origin coordinates
        ox, oy = origin

        # Draw positive X axis in red
        cv2.arrowedLine(output, (ox, oy), (ox + length, oy), (0, 0, 255), 2)
        cv2.putText(
            output,
            "X",
            (ox + length + 5, oy + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

        # Draw positive Y axis in blue
        # In image coordinates, positive Y points downward
        cv2.arrowedLine(output, (ox, oy), (ox, oy + length), (255, 0, 0), 2)
        cv2.putText(
            output,
            "Y",
            (ox - 5, oy + length + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 0),
            2,
        )

        # Draw a small arc showing the positive angle direction
        radius = length // 2
        cv2.ellipse(output, origin, (radius, radius), 0, 0, 60, (0, 255, 255), 2)

        # Label the angle arc
        cv2.putText(
            output,
            "+a",
            (ox + radius + 2, oy + radius + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
        )

        return output