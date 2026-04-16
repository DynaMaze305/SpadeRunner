import os

import aiofiles


PHOTOS_DIR = os.path.join(os.getcwd(), "received_photos")

# Wrapper that saves the picture in the directory
async def save_bytes(data: bytes, name: str, directory: str = PHOTOS_DIR) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)
    return path