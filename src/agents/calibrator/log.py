import csv
import os


def log_row(csv_path: str, date: str, image_path: str,
            target_angle: float, pwm: int, measured_angle: float,
            target_distance: float = 0.0, duration=None,
            ratio: float = 0.0,
            measured_x: float = 0.0, measured_y: float = 0.0) -> None:
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow([
                "date", "image_path",
                "target_angle", "pwm",
                "measured_angle",
                "target_distance", "duration", "ratio",
                "measured_x", "measured_y",
            ])
        writer.writerow([
            date, image_path,
            target_angle, pwm,
            measured_angle,
            target_distance, duration, ratio,
            measured_x, measured_y,
        ])
