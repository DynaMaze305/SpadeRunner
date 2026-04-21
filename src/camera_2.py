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
    
    def get_rgb_image(self) -> np.ndarray:
        return cv2.cvtColor(self.get_image(), cv2.COLOR_BGR2RGB)
    
    def get_hsv_image(self) -> np.ndarray:
        return cv2.cvtColor(self.get_image(), cv2.COLOR_BGR2HSV)


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
    


    def get_color_mask_hsv(
        self,
        lower: np.ndarray,
        upper: np.ndarray,
        image_hsv: np.ndarray | None = None,
    ) -> np.ndarray:
        if image_hsv is None:
            image_hsv = self.get_hsv_image()

        return cv2.inRange(image_hsv, lower, upper)
    
    #here we need 2 mask because pink/red is on the edge of the spectrum (hue 0 and hue 180), so we need to combine two ranges to capture all pink/red hues.
    def detect_pink_mask(self) -> np.ndarray:
        img_hsv = self.get_hsv_image()

        lower_pink_1 = np.array([140, 60, 60]) # light makes it hard to find pink, so we will need to have a controleed environment
        upper_pink_1 = np.array([179, 255, 255])

        lower_pink_2 = np.array([0, 60, 60])
        upper_pink_2 = np.array([7, 255, 255])

        mask1 = self.get_color_mask_hsv(lower_pink_1, upper_pink_1, img_hsv)
        mask2 = self.get_color_mask_hsv(lower_pink_2, upper_pink_2, img_hsv)

        pink_mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((3, 3), np.uint8)
        pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_CLOSE, kernel)
        pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_OPEN, kernel)

        return pink_mask
    
    def get_largest_mask_bounding_box(
    self,
    mask: np.ndarray,
    image: np.ndarray | None = None,
    padding_ratio: float = 0.01):
        if image is None:
            image = self.get_image()
        else:
            image = image.copy()

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        largest_contour = max(contours, key=cv2.contourArea)

        # Strict bounding box
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Padding only for cropping
        pad = int(padding_ratio * max(w, h))

        h_img, w_img = image.shape[:2]

        x1 = max(x - pad, 0)
        y1 = max(y - pad, 0)
        x2 = min(x + w + pad, w_img)
        y2 = min(y + h + pad, h_img)

        cropped = image[y1:y2, x1:x2]

        boxed_image = image.copy()
        cv2.rectangle(boxed_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return {
            "contour": largest_contour,
            "bbox": (x, y, w, h),
            "crop_bbox": (x1, y1, x2, y2),
            "cropped": cropped,
            "boxed_image": boxed_image,
        }

    def detect_and_crop_pink_object(self, padding_ratio: float = 0.01):
        """
        Detect the largest pink region, draw its strict bounding box,
        and return a padded crop.
        """
        pink_mask = self.detect_pink_mask()
        return self.get_largest_mask_bounding_box(
            mask=pink_mask,
            image=self.get_image(),
            padding_ratio=padding_ratio,
        )
    

    def get_contours_in_crop(
        self,
        mask: np.ndarray,
        crop_bbox: tuple[int, int, int, int],
        image: np.ndarray | None = None,
        min_area: int = 200,
    ):
        """
        Find contours inside a cropped region of a mask, filter by area,
        and draw them on the corresponding cropped image.

        Args:
            mask: full binary mask (e.g., pink_mask)
            crop_bbox: (x1, y1, x2, y2)
            image: original image (optional)
            min_area: minimum contour area to keep

        Returns:
            dict with:
                - contours (filtered)
                - cropped_mask
                - cropped_image
                - drawn_image
        """
        if image is None:
            image = self.get_image()

        x1, y1, x2, y2 = crop_bbox

        # Crop mask and image
        cropped_mask = mask[y1:y2, x1:x2]
        cropped_image = image[y1:y2, x1:x2].copy()

        # Find contours
        contours, _ = cv2.findContours(
            cropped_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter by area
        filtered = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]

        # Draw contours
        drawn = cropped_image.copy()
        cv2.drawContours(drawn, filtered, -1, (0, 255, 0), 2)

        return {
            "contours": filtered,
            "cropped_mask": cropped_mask,
            "cropped_image": cropped_image,
            "drawn_image": drawn,
        }
    def get_wall_mask_from_contours(
        self,
        mask: np.ndarray,
        crop_bbox: tuple[int, int, int, int],
        image: np.ndarray | None = None,
        min_area: int = 200,
        thickness: int = 2,
    ):
        """
        Build a wall mask directly from filtered contours inside a crop.

        Args:
            mask: full binary mask (e.g. pink mask)
            crop_bbox: (x1, y1, x2, y2)
            image: original image (optional)
            min_area: minimum contour area to keep
            thickness: contour drawing thickness

        Returns:
            dict with:
                - contours
                - cropped_mask
                - cropped_image
                - contours_only_image
                - wall_mask
        """
        if image is None:
            image = self.get_image()

        x1, y1, x2, y2 = crop_bbox

        # Crop mask and image
        cropped_mask = mask[y1:y2, x1:x2]
        cropped_image = image[y1:y2, x1:x2].copy()

        # Find contours from cropped mask
        contours, _ = cv2.findContours(
            cropped_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        # Keep only large enough contours
        filtered = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]

        # Draw contours only on black image
        contours_only_image = np.zeros_like(cropped_image)
        cv2.drawContours(contours_only_image, filtered, -1, (0, 255, 0), thickness)

        # Build binary wall mask directly from contours
        wall_mask = np.zeros(cropped_mask.shape, dtype=np.uint8)
        cv2.drawContours(wall_mask, filtered, -1, 255, -1)

        return {
            "contours": filtered,
            "cropped_mask": cropped_mask,
            "cropped_image": cropped_image,
            "contours_only_image": contours_only_image,
            "wall_mask": wall_mask,
        }
    





    def draw_grid_lines(
        self,
        wall_mask: np.ndarray,
        x_lines: list[int],
        y_lines: list[int],
    ) -> np.ndarray:
        """
        Draw detected grid lines on top of a wall mask.

        Args:
            wall_mask: binary wall image
            x_lines: vertical grid line x positions
            y_lines: horizontal grid line y positions

        Returns:
            RGB overlay image
        """
        h, w = wall_mask.shape
        overlay = cv2.cvtColor(wall_mask, cv2.COLOR_GRAY2RGB)

        for xg in x_lines:
            cv2.line(overlay, (xg, 0), (xg, h - 1), (255, 0, 0), 1)

        for yg in y_lines:
            cv2.line(overlay, (0, yg), (w - 1, yg), (0, 255, 0), 1)

        return overlay


    def draw_cell_labels(
        self,
        image: np.ndarray,
        cell_centers: dict[str, tuple[int, int]],
        color: tuple[int, int, int] = (0, 255, 255),  # BGR (yellow)
        font_scale: float = 0.4,
        thickness: int = 1,
    ) -> np.ndarray:
        """
        Draw cell labels directly on an image using OpenCV.

        Args:
            image: input image (BGR or RGB, but treated as raw array)
            cell_centers: dict from label -> (x, y)
            color: BGR color tuple
            font_scale: text size
            thickness: text thickness

        Returns:
            image with labels drawn
        """
        output = image.copy()

        for label, (cx, cy) in cell_centers.items():
            cv2.putText(
                output,
                label,
                (int(cx), int(cy)),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                color,
                thickness,
                cv2.LINE_AA,
            )

        return output
    

