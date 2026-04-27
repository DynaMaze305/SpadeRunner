from __future__ import annotations

import cv2
import numpy as np


# Abstraction layer over OpenCV for image loading, color conversion, and debug drawing
class Camera:

    def __init__(self) -> None:
        # Current loaded image
        self.image: np.ndarray | None = None

    def imread(self, path: str) -> np.ndarray:
        # Load an image from disk using OpenCV
        image = cv2.imread(path)

        # Stop if the image could not be loaded
        if image is None:
            raise ValueError(f"Could not load image from path: {path}")

        # Store the loaded image inside the camera object
        self.image = image

        return image

    def get_image(self) -> np.ndarray:
        # Make sure an image has been loaded before accessing it
        if self.image is None:
            raise ValueError("No image loaded.")

        # Return the currently loaded image
        return self.image

    def copy(self) -> np.ndarray:
        # Return a copy of the current image so the original stays unchanged
        return self.get_image().copy()

    @staticmethod
    def angle_diff(new: float, old: float) -> float:
        # Compute the shortest signed difference between two angles
        # Result is normalized to the range [-180, 180]
        return (new - old + 180.0) % 360.0 - 180.0

    @staticmethod
    def correct_angle(angle_deg: float, offset_deg: float) -> float:
        # Apply an offset to an angle and normalize the result to [-180, 180]
        return (angle_deg + offset_deg + 180.0) % 360.0 - 180.0

    def draw_axes(
        self,
        image,
        origin=(60, 60),
        length=40,
        thickness=2,
    ):
        # Work on a copy so the original image is not modified
        output = image.copy()

        # Extract axis origin coordinates
        ox, oy = origin

        # Draw positive X axis in red
        cv2.arrowedLine(output, (ox, oy), (ox + length, oy), (0, 0, 255), thickness)
        cv2.putText(
            output,
            "X",
            (ox + length + 5, oy + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            thickness,
        )

        # Draw positive Y axis in blue
        # In image coordinates, positive Y points downward
        cv2.arrowedLine(output, (ox, oy), (ox, oy + length), (255, 0, 0), thickness)
        cv2.putText(
            output,
            "Y",
            (ox - 5, oy + length + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 0),
            thickness,
        )

        # Draw a small arc showing the positive angle direction
        radius = length // 2
        cv2.ellipse(
            output,
            origin,
            (radius, radius),
            0,
            0,
            60,
            (0, 255, 255),
            thickness,
        )

        # Label the angle direction
        cv2.putText(
            output,
            "+theta",
            (ox + radius + 5, oy + radius + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
        )

        return output

    @staticmethod
    def decode_image(image_data: bytes) -> np.ndarray:
        # Convert raw image bytes into a NumPy array
        arr = np.frombuffer(image_data, dtype=np.uint8)

        # Decode the NumPy array into an OpenCV BGR image
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # Stop if decoding failed
        if image is None:
            raise ValueError("Could not decode image data.")

        # Rotate image by 180 degrees to match the camera/setup orientation
        image = cv2.rotate(image, cv2.ROTATE_180)

        return image