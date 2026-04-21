from camera import Camera
from aruco_detector import ArucoDetector
from maze_grid_analyzer import MazeGridAnalyzer
from visualizer import Visualizer

cam = Camera()
viz = Visualizer()
aruco_detector = ArucoDetector()

cam.imread("t2.jpg")

# --- ArUco detection ---
corners, ids, rejected = aruco_detector.detect(cam.get_image())
marker_image = aruco_detector.draw_detected_markers(cam.get_image(), corners, ids)
pose = aruco_detector.get_marker_pose_2d(corners, ids)

if pose is not None:
    print("Marker ID:", pose["id"])
    print("Center:", pose["center"])
    print("2D angle:", pose["angle_deg"])
    print("Homography:\n", pose["homography"])
    marker_image = aruco_detector.draw_point(marker_image, pose["center"])
else:
    print("No marker detected.")

# --- Pink object detection ---
pink_mask = cam.detect_pink_mask()
pink_result = cam.detect_and_crop_pink_object()

if pink_result is not None:
    x, y, w, h = pink_result["bbox"]
    x1, y1, x2, y2 = pink_result["crop_bbox"]

    print(f"Original Box: (x={x}, y={y}, x2={x + w}, y2={y + h})")
    print(f"Cropped Box : (x1={x1}, y1={y1}, x2={x2}, y2={y2})")

    # --- Build filled wall mask from contours ---
    wall_result = cam.get_wall_mask_from_contours(
        mask=pink_mask,
        crop_bbox=pink_result["crop_bbox"],
        min_area=200,
        thickness=-1,
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

    # --- Draw grid lines and labels ---
    overlay = cam.draw_grid_lines(wall_mask, x_lines, y_lines)

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

    # --- Show full pipeline ---
    viz.show_full_pipeline(
        marker_image=marker_image,
        pink_mask=pink_mask,
        boxed_image=pink_result["boxed_image"],
        cropped_image=pink_result["cropped"],
        contours_only_image=wall_result["contours_only_image"],
        wall_mask=wall_mask,
        horizontal=horizontal,
        vertical=vertical,
        x_profile=x_profile,
        y_profile=y_profile,
        overlay=overlay,
        labeled_overlay=labeled_overlay,
    )

else:
    print("No pink object detected.")