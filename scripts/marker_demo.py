import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vision.camera import Camera
import cv2

# Our robots
robot_ids = [8,12]

# Create camera object
cam = Camera()

# Pick the most recent photo in received_photos/
photos = glob.glob("received_photos/*.jpg")
if not photos:
    raise FileNotFoundError("No photos found in received_photos/")
latest = max(photos, key=os.path.getmtime)
print("Loading:", latest)

# Load image
cam.imread(latest)

# Detect ArUco markers
corners, ids, rejected = cam.detect_aruco()

# Draw detected markers on image
marker_image = cam.draw_detected_markers(corners, ids)

# marker is physically mounted 90° off the car's forward direction, correct it
ANGLE_OFFSET = 90

if ids is None or len(corners) == 0:
    # No marker detected
    print("No marker detected.")
else:
    # Loop over every detected marker
    for i in range(len(corners)):
        pose = cam.get_marker_pose_2d(corners, ids, index=i)

        if pose["id"] not in robot_ids:
            continue

        # Print marker information
        print("Marker ID:", pose["id"])
        print("Center:", pose["center"])
        print("2D angle (raw):", pose["angle_deg"])

        # processing: align the detected marker angle with the car's forward direction
        # then wrap to (-180, 180]
        corrected_angle = cam.correct_angle(pose["angle_deg"], ANGLE_OFFSET)
        print("2D angle (corrected):", corrected_angle)
        print("Homography:\n", pose["homography"])

        # Draw center point of the marker
        marker_image = cam.draw_point(pose["center"], marker_image)

        # Draw arrow based on center point and orientation
        marker_image = cam.draw_arrow(pose["center"], corrected_angle, length=40,
                                      image=marker_image)

    # Draw reference coordinates for debugging
    marker_image = cam.draw_axes(image=marker_image)

    cv2.imwrite("output.jpg", marker_image)