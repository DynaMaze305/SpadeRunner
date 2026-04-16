from camera import Camera
import cv2

# Create camera object
cam = Camera()

# Load image
cam.imread("assets/1.jpg")

# Detect ArUco markers
corners, ids, rejected = cam.detect_aruco()

# Draw detected markers on image
marker_image = cam.draw_detected_markers(corners, ids)

# Compute 2D pose of the marker
pose = cam.get_marker_pose_2d(corners, ids)

if pose is not None:
    # Print marker information
    print("Marker ID:", pose["id"])
    print("Center:", pose["center"])
    print("2D angle:", pose["angle_deg"])
    print("Homography:\n", pose["homography"])

    # Draw center point of the marker
    marker_image = cam.draw_point(pose["center"], marker_image)

    cv2.imwrite("output.jpg", marker_image)
else:
    # No marker detected
    print("No marker detected.")