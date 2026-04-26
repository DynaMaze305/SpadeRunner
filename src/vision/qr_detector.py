from vision.camera import Camera


# returns the full marker pose {angle_deg, x, y} or None
# opencv does the same heavy job whether we want the angle alone or angle + position
# if aruco_id is given: returns that single marker's pose (or None if not on the field)
# if aruco_id is None: returns a dict {id: pose} of every detected marker (or None if no marker at all)
def detect_qr_angle_pose(image_path: str, aruco_id: int = None):
    cam = Camera()
    cam.imread(image_path)
    corners, ids, _ = cam.detect_aruco()
    if ids is None or len(corners) == 0:
        return None

    poses = {}
    for i in range(len(corners)):
        pose = cam.get_marker_pose_2d(corners, ids, index=i)
        if pose is None:
            continue
        # negate to match the trigonometric (CCW positive) convention used by the robot
        cx, cy = pose["center"]
        poses[pose["id"]] = {"angle_deg": -pose["angle_deg"], "x": float(cx), "y": float(cy)}

    if aruco_id is not None:
        return poses.get(aruco_id)
    return poses


# returns the angle diff between two angles
def angle_diff(new: float, old: float) -> float:
    return (new - old + 180.0) % 360.0 - 180.0