from __future__ import annotations  # Enable postponed evaluation of type hints (cleaner typing)
import cv2                         # OpenCV main library (image processing)
import cv2.aruco as aruco         # ArUco module (marker detection)
import numpy as np                # Numerical computations (arrays, geometry)


# Abstraction layer over OpenCV for image loading and ArUco marker detection.
class Camera:

    def __init__(self) -> None:
        # Current loaded image
        self.image = None

    def imread(self, path: str) -> np.ndarray:
        # Load an image from disk
        image = cv2.imread(path)

        if image is None:
            raise ValueError(f"Could not load image from path: {path}")

        self.image = image
        return image

    def get_image(self) -> np.ndarray:
        # Return the current image
        if self.image is None:
            raise ValueError("No image loaded.")
        return self.image

    def copy(self) -> np.ndarray:
        # Return a copy of the current image
        return self.get_image().copy()

    # ArUco
    #https://stackoverflow.com/questions/77397697/opencv-aruco-marker-detection


    def create_aruco_detector(self) -> aruco.ArucoDetector:
        # Create and return an ArUco detector
        aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        detector = aruco.ArucoDetector(aruco_dict, parameters)
        return detector

    def detect_aruco(self):
        # Detect ArUco markers in the current image
        detector = self.create_aruco_detector()
        corners, ids, rejected = detector.detectMarkers(self.get_image())
        return corners, ids, rejected

    def draw_detected_markers(self, corners, ids) -> np.ndarray:
        # Draw detected ArUco markers on a copy of the image
        image = self.copy()

        if ids is not None:
            aruco.drawDetectedMarkers(image, corners, ids)

        return image

    def get_marker_corners(self, corners, index: int = 0) -> np.ndarray:
        # Return the 4 corner points of a detected marker as float32
        if not corners:
            raise ValueError("No marker corners available.")

        return corners[index][0].astype(np.float32)

    def get_marker_center(self, pts: np.ndarray) -> tuple[int, int]:
        # Compute the center of a marker from its 4 corner points
        center = pts.mean(axis=0)
        cx, cy = center.astype(int)
        return int(cx), int(cy)

    def get_marker_angle_2d(self, pts: np.ndarray) -> float:
        # Compute the 2D angle of the marker from its top edge
        p0, p1 = pts[0], pts[1]
        angle_deg = np.degrees(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
        return float(angle_deg)
    
    #https://stackoverflow.com/questions/79327929/using-opencv-to-achieve-a-top-down-view-of-an-image-with-aruco-markers
    def get_marker_homography(self, pts: np.ndarray) -> np.ndarray:
        # Compute the image -> marker local 2D homography
        marker_size = 20.0

        dst_pts = np.array(
            [
                [0, 0],
                [marker_size, 0],
                [marker_size, marker_size],
                [0, marker_size],
            ],
            dtype=np.float32,
        )

        H = cv2.getPerspectiveTransform(pts, dst_pts)
        return H

    def get_marker_pose_2d(self, corners, ids, index: int = 0):
        # Return 2D pose information for one detected ArUco marker
        if ids is None or len(corners) == 0:
            return None

        pts = self.get_marker_corners(corners, index)
        cx, cy = self.get_marker_center(pts)
        angle_deg = self.get_marker_angle_2d(pts)
        H = self.get_marker_homography(pts)

        return {
            "id": int(ids[index][0]),
            "corners": pts,
            "center": (cx, cy),
            "angle_deg": angle_deg,
            "homography": H,
        }

    #https://stackoverflow.com/questions/49799057/how-to-draw-a-point-in-an-image-using-given-co-ordinate-with-python-opencv?utm_source=chatgpt.com
    def draw_point(self, point: tuple[int, int], image: np.ndarray | None = None) -> np.ndarray:
        # Use provided image, otherwise fallback to current image
        if image is None:
            image = self.copy()
        else:
            image = image.copy()

        cv2.circle(image, point, 5, (0, 0, 255), -1)
        return image