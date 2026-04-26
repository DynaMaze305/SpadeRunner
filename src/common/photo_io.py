import os

import aiofiles
import cv2
import numpy as np


PHOTOS_DIR = os.path.join(os.getcwd(), "received_photos")


async def save_bytes(
    data: bytes,
    name: str,
    directory: str = PHOTOS_DIR,
    rotate_code: int = cv2.ROTATE_180,
) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)

    image_array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image bytes")

    rotated = cv2.rotate(image, rotate_code)

    success = cv2.imwrite(path, rotated)
    if not success:
        raise IOError(f"Could not save image to {path}")

    return path