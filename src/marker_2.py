from camera import Camera
from maze_grid_analyzer import MazeGridAnalyzer
import cv2
import matplotlib.pyplot as plt

cam = Camera()
cam.imread("test.jpg")

# --- ArUco detection ---
corners, ids, rejected = cam.detect_aruco()
marker_image = cam.draw_detected_markers(corners, ids)
pose = cam.get_marker_pose_2d(corners, ids)

if pose is not None:
    print("Marker ID:", pose["id"])
    print("Center:", pose["center"])
    print("2D angle:", pose["angle_deg"])
    print("Homography:\n", pose["homography"])
    marker_image = cam.draw_point(pose["center"], marker_image)
else:
    print("No marker detected.")

# --- Pink object detection ---
pink_mask = cam.detect_pink_mask()
pink_result = cam.detect_and_crop_pink_object()

marker_image_rgb = cv2.cvtColor(marker_image, cv2.COLOR_BGR2RGB)

if pink_result is not None:
    x, y, w, h = pink_result["bbox"]
    x1, y1, x2, y2 = pink_result["crop_bbox"]

    print(f"Original Box: (x={x}, y={y}, x2={x + w}, y2={y + h})")
    print(f"Cropped Box : (x1={x1}, y1={y1}, x2={x2}, y2={y2})")

    boxed_rgb = cv2.cvtColor(pink_result["boxed_image"], cv2.COLOR_BGR2RGB)
    cropped_rgb = cv2.cvtColor(pink_result["cropped"], cv2.COLOR_BGR2RGB)

    # --- Build filled wall mask from contours ---
    wall_result = cam.get_wall_mask_from_contours(
        mask=pink_mask,
        crop_bbox=pink_result["crop_bbox"],
        min_area=200,
        thickness=-1,
    )

    contours_only_rgb = cv2.cvtColor(
        wall_result["contours_only_image"], cv2.COLOR_BGR2RGB
    )
    wall_mask = wall_result["wall_mask"]

    print("Number of filtered contours:", len(wall_result["contours"]))

    # --- Maze grid analysis ---
    analyzer = MazeGridAnalyzer(wall_mask)

    wall_parts = analyzer.extract_horizontal_vertical_walls(
        horizontal_kernel_size=25,
        vertical_kernel_size=25,
    )
    horizontal = wall_parts["horizontal"]
    vertical = wall_parts["vertical"]

    profiles = analyzer.get_wall_projection_profiles(horizontal, vertical)
    x_profile = profiles["x_profile"]
    y_profile = profiles["y_profile"]

    grid_result = analyzer.detect_grid_lines_from_profiles(
        x_profile,
        y_profile,
        x_threshold_ratio=0.3,
        y_threshold_ratio=0.1,
        min_gap=15,
    )

    x_lines = grid_result["x_lines"]
    y_lines = grid_result["y_lines"]

    print("Candidate x grid lines:", x_lines)
    print("Candidate y grid lines:", y_lines)

    # --- Grid shape ---
    n_cols = len(x_lines) - 1
    n_rows = len(y_lines) - 1

    print("Number of columns:", n_cols)
    print("Number of rows:", n_rows)

    # --- Draw grid lines ---
    overlay = cam.draw_grid_lines(wall_mask, x_lines, y_lines)

    # --- Compute and draw cell labels ---
    cell_centers = analyzer.get_cell_centers(x_lines, y_lines)
    labeled_overlay = cam.draw_cell_labels(overlay, cell_centers)

    if "A1" in cell_centers:
        print(f"Center of cell A1: {cell_centers['A1']}")
    if "B1" in cell_centers:
        print(f"Center of cell B1: {cell_centers['B1']}")
    if "C3" in cell_centers:
        print(f"Center of cell C3: {cell_centers['C3']}")

    # --- Extract walls per cell ---
    grid_walls = analyzer.get_grid_walls_with_band(
        x_lines=x_lines,
        y_lines=y_lines,
        threshold=100,
        band=3,
    )

    if "A1" in grid_walls:
        print(f"Walls for A1: {grid_walls['A1']}")

    print("\nASCII maze preview:")
    analyzer.print_ascii_grid_walls(
        grid_walls=grid_walls,
        n_rows=n_rows,
        n_cols=n_cols,
    )

    labeled_overlay_rgb = cv2.cvtColor(labeled_overlay, cv2.COLOR_BGR2RGB)

    # --- Single Figure: full pipeline ---
    plt.figure(figsize=(20, 18))

    # Row 1
    plt.subplot(4, 3, 1)
    plt.title("ArUco Marker Detection")
    plt.imshow(marker_image_rgb)
    plt.axis("on")
    plt.gca().invert_yaxis()

    plt.subplot(4, 3, 2)
    plt.title("Pink Mask")
    plt.imshow(pink_mask, cmap="gray")
    plt.axis("on")
    plt.gca().invert_yaxis()

    plt.subplot(4, 3, 3)
    plt.title("Detected Pink Object")
    plt.imshow(boxed_rgb)
    plt.axis("on")
    plt.gca().invert_yaxis()

    # Row 2
    plt.subplot(4, 3, 4)
    plt.title("Cropped Pink Object")
    plt.imshow(cropped_rgb)
    plt.axis("on")
    plt.gca().invert_yaxis()

    plt.subplot(4, 3, 5)
    plt.title("Contours Only")
    plt.imshow(contours_only_rgb)
    plt.axis("on")
    plt.gca().invert_yaxis()

    plt.subplot(4, 3, 6)
    plt.title("Wall Mask (Filled)")
    plt.imshow(wall_mask, cmap="gray", origin="lower")
    plt.xlabel("x")
    plt.ylabel("y")

    # Row 3
    plt.subplot(4, 3, 7)
    plt.title("Horizontal Walls")
    plt.imshow(horizontal, cmap="gray", origin="lower")
    plt.xlabel("x")
    plt.ylabel("y")

    plt.subplot(4, 3, 8)
    plt.title("Vertical Walls")
    plt.imshow(vertical, cmap="gray", origin="lower")
    plt.xlabel("x")
    plt.ylabel("y")

    plt.subplot(4, 3, 9)
    plt.title("Projection Profiles")
    plt.plot(x_profile, label="X profile (vertical)")
    plt.plot(y_profile, label="Y profile (horizontal)")
    plt.legend()
    plt.xlabel("index")
    plt.ylabel("sum")

    # Row 4
    plt.subplot(4, 3, 10)
    plt.title("Detected Grid Lines")
    plt.imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB), origin="lower")
    plt.xlabel("x")
    plt.ylabel("y")

    plt.subplot(4, 3, 11)
    plt.title("Grid With Cell Labels")
    plt.imshow(labeled_overlay_rgb, origin="lower")
    plt.xlabel("x")
    plt.ylabel("y")

    plt.tight_layout()
    plt.show()

else:
    print("No pink object detected.")