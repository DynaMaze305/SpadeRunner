from vision.camera import Camera


# returns the full marker pose {angle_deg, x, y} or None
# opencv does the same heavy job whether we want the angle alone or angle + position
def detect_qr_angle_pose(image_path: str):
    cam = Camera()
    cam.imread(image_path)
    corners, ids, _ = cam.detect_aruco()
    pose = cam.get_marker_pose_2d(corners, ids)
    if pose is None:
        return None
    # negate to match the trigonometric (CCW positive) convention used by the robot
    cx, cy = pose["center"]
    return {"angle_deg": -pose["angle_deg"], "x": float(cx), "y": float(cy)}


# returns the angle diff between two angles
def angle_diff(new: float, old: float) -> float:
    return (new - old + 180.0) % 360.0 - 180.0