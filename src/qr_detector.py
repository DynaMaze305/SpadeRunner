from camera import Camera


# returns the ArUco marker 2D angle (degrees) found in the image, or None if absent
def detect_qr_angle(image_path: str):
    cam = Camera()
    cam.imread(image_path)
    corners, ids, _ = cam.detect_aruco()
    pose = cam.get_marker_pose_2d(corners, ids)
    if pose is None:
        return None
    # negate to match the trigonometric (CCW positive) convention used by the robot
    return -pose["angle_deg"]


# returns the angle diff between two angles
def angle_diff(new: float, old: float) -> float:
    return (new - old + 180.0) % 360.0 - 180.0