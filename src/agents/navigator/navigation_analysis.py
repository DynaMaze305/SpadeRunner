"""per-step rotation + distance errors for a navigation run, with side-by-side plots.
called by scripts/navigation_plot.py.
"""

import csv
import logging
import math
import os

import matplotlib.pyplot as plt
import numpy as np

from agents.calibrator.calibration_math import MM_PER_PIXEL, l2_score


logger = logging.getLogger(__name__)


def _read_csv(folder, name):
    csv_path = os.path.join(folder, name)
    with open(csv_path, "r", newline="") as f:
        return list(csv.DictReader(f))


# walks consecutive non-NaN rows and pairs row N's command with row N+1's measurement
def navigation_series(rows):
    rotation_commanded_series = []
    rotation_actual_series = []
    rotation_error_series = []
    distance_commanded_series = []
    distance_actual_series = []
    distance_error_series = []
    drift_series = []

    prev_angle = None
    prev_pixel_x = None
    prev_pixel_y = None
    prev_target_angle = None
    prev_target_distance = None

    for row in rows:
        angle = float(row["measured_angle"])
        pixel_x = float(row["measured_x"])
        pixel_y = float(row["measured_y"])
        target_angle = float(row["target_angle"])
        target_distance = float(row["target_distance"])

        # bad detection -> reset chain so the next pair isn't bogus
        if math.isnan(angle) or math.isnan(pixel_x) or math.isnan(pixel_y):
            prev_angle = None
            prev_pixel_x = None
            prev_pixel_y = None
            prev_target_angle = None
            prev_target_distance = None
            continue

        # first valid row only seeds the chain
        if prev_angle is None:
            prev_angle = angle
            prev_pixel_x = pixel_x
            prev_pixel_y = pixel_y
            prev_target_angle = target_angle
            prev_target_distance = target_distance
            continue

        # rotation: commanded delta vs actual delta, both wrapped into [-180, 180]
        rotation_commanded = (prev_target_angle - prev_angle + 180.0) % 360.0 - 180.0
        rotation_actual = (angle - prev_angle + 180.0) % 360.0 - 180.0
        # error must be wrapped too: +179 vs -179 is a 2 deg miss, not 358 deg
        rotation_error = (rotation_commanded - rotation_actual + 180.0) % 360.0 - 180.0
        rotation_commanded_series.append(rotation_commanded)
        rotation_actual_series.append(rotation_actual)
        rotation_error_series.append(rotation_error)

        # distance: commanded magnitude vs actual euclidean displacement in mm
        delta_x = pixel_x - prev_pixel_x
        delta_y = pixel_y - prev_pixel_y
        distance_actual = math.sqrt(delta_x ** 2 + delta_y ** 2) * MM_PER_PIXEL
        distance_commanded = abs(prev_target_distance)
        distance_commanded_series.append(distance_commanded)
        distance_actual_series.append(distance_actual)
        distance_error_series.append(distance_commanded - distance_actual)

        # drift: how far the move vector strayed from the heading we wanted
        # same formula as ratio_points: move_angle - facing, wrapped to [-180, 180]
        # image y points down -> flip to math convention
        delta_y_math = -delta_y
        move_angle = math.degrees(math.atan2(delta_y_math, delta_x))
        drift = (move_angle - prev_target_angle + 180.0) % 360.0 - 180.0
        # backward moves expect a 180 deg motion direction, flip alpha to keep
        # the left/right sign convention consistent with forward
        if prev_target_distance < 0:
            drift = (180.0 - drift + 180.0) % 360.0 - 180.0
        drift_series.append(drift)

        prev_angle = angle
        prev_pixel_x = pixel_x
        prev_pixel_y = pixel_y
        prev_target_angle = target_angle
        prev_target_distance = target_distance

    return (
        rotation_commanded_series, rotation_actual_series, rotation_error_series,
        distance_commanded_series, distance_actual_series, distance_error_series,
        drift_series,
    )


# plots commanded (green), actual (blue) and error (red) per step, side by side
def analyse_navigation(folder):

    # loads the navigation rows
    rows = _read_csv(folder, "navigation.csv")
    (
        rotation_commanded, rotation_actual, rotation_error,
        distance_commanded, distance_actual, distance_error,
        drift,
    ) = navigation_series(rows)

    # L2 norms kept for the console summary
    rotation_score = l2_score(rotation_error)
    distance_score = l2_score(distance_error)
    drift_score = l2_score(drift)

    logger.info(
        f"rotation L2: {rotation_score:.2f} deg over {len(rotation_error)} steps"
    )
    logger.info(
        f"distance L2: {distance_score:.2f} mm over {len(distance_error)} steps"
    )
    logger.info(
        f"drift L2: {drift_score:.2f} deg over {len(drift)} steps"
    )

    # builds the side-by-side plot
    fig, (ax_rotation, ax_distance, ax_drift) = plt.subplots(1, 3, figsize=(20, 5))

    # left subplot: rotation commanded, actual, error
    # commanded and actual jump per step (no continuity), so scatter only.
    # error stays bounded so we draw a line to see drift across the run
    rotation_xs = np.arange(1, len(rotation_error) + 1)
    ax_rotation.scatter(rotation_xs, rotation_commanded, color="tab:green", label="commanded")
    ax_rotation.scatter(rotation_xs, rotation_actual, color="tab:blue", label="actual")
    ax_rotation.plot(rotation_xs, rotation_error, color="tab:red",
                     marker="o", label="error (commanded - actual)")
    ax_rotation.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    ax_rotation.set_xlabel("step index")
    ax_rotation.set_ylabel("rotation [deg]")
    ax_rotation.set_title("rotation")
    ax_rotation.legend()
    ax_rotation.grid(True)

    # middle subplot: distance commanded, actual, error
    distance_xs = np.arange(1, len(distance_error) + 1)
    ax_distance.scatter(distance_xs, distance_commanded, color="tab:green", label="commanded")
    ax_distance.scatter(distance_xs, distance_actual, color="tab:blue", label="actual")
    ax_distance.plot(distance_xs, distance_error, color="tab:red",
                     marker="o", label="error (commanded - actual)")
    ax_distance.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    ax_distance.set_xlabel("step index")
    ax_distance.set_ylabel("distance [mm]")
    ax_distance.set_title("distance")
    ax_distance.legend()
    ax_distance.grid(True)

    # right subplot: drift = move vector vs commanded heading
    # commanded drift is always 0 (we want to move straight ahead)
    drift_xs = np.arange(1, len(drift) + 1)
    ax_drift.plot(drift_xs, drift, color="tab:red", marker="o", label="drift")
    ax_drift.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    ax_drift.set_xlabel("step index")
    ax_drift.set_ylabel("drift [deg]  (+ left / - right)")
    ax_drift.set_title("drift")
    ax_drift.legend()
    ax_drift.grid(True)

    fig.suptitle(f"navigation: {os.path.basename(folder)}")
    fig.tight_layout()

    # saves the figure in the run folder
    output_path = os.path.join(folder, "navigation_errors.png")
    fig.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return rotation_score, distance_score, drift_score
