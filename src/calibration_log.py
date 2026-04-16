import csv
import os

# helper tool to log the calibration data in a CSV file
def log_row(csv_path: str, date: str, image_path: str, commanded_angle: float, measured_angle: float) -> None:
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["date", "image_path", "commanded_angle", "measured_angle"])
        writer.writerow([date, image_path, commanded_angle, measured_angle])
