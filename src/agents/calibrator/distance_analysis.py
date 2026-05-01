"""linear regression + L2 scoring for distance moves, with matplotlib plots
called by the calibrator agent and by the matching scripts/
"""

import csv
import logging
import os

import matplotlib.pyplot as plt
import numpy as np

from agents.calibrator.calibration_math import (
    MM_PER_PIXEL,
    distance_errors,
    distance_points,
    l2_score,
    linear_fit,
)


logger = logging.getLogger(__name__)


def _read_csv(folder, name):
    csv_path = os.path.join(folder, name)
    with open(csv_path, "r", newline="") as f:
        return list(csv.DictReader(f))


# fits the (duration, distance_mm) data and plots the regression
def analyse_distance(folder):

    # loads the calibration rows
    rows = _read_csv(folder, "distance.csv")
    forward, backward = distance_points(rows)

    # converts pixel distance to mm and uses abs duration for backward
    fwd_x = np.array([duration for duration, distance_px in forward])
    fwd_y = np.array([distance_px * MM_PER_PIXEL for duration, distance_px in forward])
    bwd_x = np.array([abs(duration) for duration, distance_px in backward])
    bwd_y = np.array([distance_px * MM_PER_PIXEL for duration, distance_px in backward])

    # does linear regression on each direction
    fwd_slope, fwd_intercept, fwd_r2 = linear_fit(fwd_x, fwd_y)
    bwd_slope, bwd_intercept, bwd_r2 = linear_fit(bwd_x, bwd_y)

    fwd_line = fwd_slope * fwd_x + fwd_intercept
    bwd_line = bwd_slope * bwd_x + bwd_intercept

    logger.info(
        f"forward fit (mm/s): y={fwd_slope:.2f}x+{fwd_intercept:.2f}, R^2={fwd_r2:.3f}"
    )
    logger.info(
        f"backward fit (mm/s): y={bwd_slope:.2f}x+{bwd_intercept:.2f}, R^2={bwd_r2:.3f}"
    )

    # builds the regression plot
    plt.figure()
    plt.scatter(fwd_x, fwd_y, color="tab:blue", label="forward duration (>0) data")
    plt.plot(fwd_x, fwd_line, color="tab:blue", linestyle="--",
             label=f"forward fit: y={fwd_slope:.1f}x+{fwd_intercept:.1f}  R^2={fwd_r2:.3f}")
    plt.scatter(bwd_x, bwd_y, color="tab:red", label="backward |duration| data")
    plt.plot(bwd_x, bwd_line, color="tab:red", linestyle="--",
             label=f"backward fit: y={bwd_slope:.1f}x+{bwd_intercept:.1f}  R^2={bwd_r2:.3f}")
    plt.xlabel("duration (s)")
    plt.ylabel("distance travelled (mm)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    # saves the figure in the run folder
    output_path = os.path.join(folder, "distance_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return fwd_slope, fwd_intercept, bwd_slope, bwd_intercept


# scores the verification moves with L2 and plots the per-move error
def analyse_distance_verify(folder):

    # loads the verification rows
    rows = _read_csv(folder, "verify_distance.csv")

    # computes per-move errors and the overall L2 score
    errors = distance_errors(rows)
    score = l2_score(errors)

    logger.info(f"distance L2: {score:.2f} mm over {len(errors)} moves")

    xs = np.arange(1, len(errors) + 1)

    # builds the L2 plot
    plt.figure()
    plt.scatter(xs, errors, color="tab:blue", label="per-move error")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.axhline(y=score, color="tab:red", linestyle="--",
                label=f"L2 = {score:.2f} mm")
    plt.axhline(y=-score, color="tab:red", linestyle="--")
    plt.xlabel("move index")
    plt.ylabel("distance error (|target| - actual) [mm]")
    plt.title(f"verify_distance: {os.path.basename(folder)}  L2={score:.2f} mm")
    plt.legend()
    plt.grid(True)

    # saves the figure in the run folder
    output_path = os.path.join(folder, "distance_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
