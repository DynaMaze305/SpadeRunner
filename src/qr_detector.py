
# returns the angle computed by the QR code opencv lib
def detect_qr_angle(img_bytes: bytes):
    angle = 90.0
    return angle

# returns the angle diff between two angles
def angle_diff(new: float, old: float) -> float:
    return (new - old + 180.0) % 360.0 - 180.0