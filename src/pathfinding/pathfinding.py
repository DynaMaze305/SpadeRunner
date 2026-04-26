from __future__ import annotations

from vision.color_detector_image_cropper import ColorDetectorImageCropper
from vision.contour_processor import ContourProcessor
from vision.grid_detector import GridDetector
from vision.maze_grid_analyzer import MazeGridAnalyzer
from vision.maze_solver import MazeSolver
from vision.camera import Camera




def compute_path(
    image_data: bytes,
    start_cell: str,
    end_cell: str,
) -> list[str] | None:

    color_detector_image_cropper = ColorDetectorImageCropper()
    contour_processor = ContourProcessor()
    grid_detector = GridDetector()
    maze_analyzer = MazeGridAnalyzer()
    maze_solver = MazeSolver()
    cam = Camera()

    image = cam.decode_image(image_data)
    pink_mask = color_detector_image_cropper.detect_pink_mask(image)
    pink_result = color_detector_image_cropper.detect_and_crop_pink_object(image)

    if pink_result is None:
        print("No pink maze detected.")
        return None

    crop_bbox = pink_result["crop_bbox"]

    contour_result = contour_processor.get_filtered_contours_in_crop(
        mask=pink_mask,
        crop_bbox=crop_bbox,
        image=image,
        min_area=200,
    )

    cropped_mask = contour_result["cropped_mask"]

    wall_bin = contour_processor.create_wall_binary(cropped_mask)
    wall_clean = contour_processor.clean_wall_mask(wall_bin)

    grid_result = grid_detector.detect_grid_lines(
        wall_clean,
        threshold_ratio=0.1,
        min_gap=15,
    )

    x_lines = grid_result["x_lines"]
    y_lines = grid_result["y_lines"]

    n_rows, n_cols = maze_analyzer.get_grid_size(x_lines, y_lines)

    if n_rows <= 0 or n_cols <= 0:
        print("Could not detect a valid grid.")
        return None

    grid_walls = maze_analyzer.build_grid_walls(
        wall_clean=wall_clean,
        x_lines=x_lines,
        y_lines=y_lines,
        threshold=100,
    )

    # ================= DEBUG START =================
    print("\n=== DEBUG WALLS ===")
    print("Start:", start_cell, "End:", end_cell)

    if start_cell in grid_walls:
        print(f"{start_cell} walls:", grid_walls[start_cell])
    if end_cell in grid_walls:
        print(f"{end_cell} walls:", grid_walls[end_cell])

    print("\n=== ASCII MAZE ===")
    maze_analyzer.print_maze(grid_walls, n_rows, n_cols)
    # ================= DEBUG END =================


    path = maze_solver.shortest_path(
        grid_walls=grid_walls,
        start_cell=start_cell,
        end_cell=end_cell,
        n_rows=n_rows,
        n_cols=n_cols,
    )

    return path