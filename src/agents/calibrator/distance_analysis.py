"""Linear regression + plot for the distance calibration and verification.

Called by the calibrator agent right after each distance run, and by the
matching scripts in scripts/ when the operator wants to re-render an old run.
"""

import csv
import logging
import os

import matplotlib.pyplot as plt
import numpy as np

from common.calibration_math import (
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


# fits (duration, distance_mm) for forward and backward moves,
# saves the scatter + regression figure, returns
# (fwd_slope, fwd_intercept, bwd_slope, bwd_intercept) in mm/s
def analyse_distance(folder):
    rows = _read_csv(folder, "distance.csv")
    forward, backward = distance_points(rows)

    # convert pixel distance -> mm, abs duration so backward fit also gives positive slope
    fwd_x = np.array([t for t, _ in forward])
    fwd_y = np.array([d * MM_PER_PIXEL for _, d in forward])
    bwd_x = np.array([abs(t) for t, _ in backward])
    bwd_y = np.array([d * MM_PER_PIXEL for _, d in backward])

    fwd_slope, fwd_intercept, fwd_r2 = linear_fit(fwd_x, fwd_y)
    bwd_slope, bwd_intercept, bwd_r2 = linear_fit(bwd_x, bwd_y)

    fwd_pred = fwd_slope * fwd_x + fwd_intercept
    bwd_pred = bwd_slope * bwd_x + bwd_intercept

    logger.info(
        f"forward fit (mm/s): y={fwd_slope:.2f}x+{fwd_intercept:.2f}, R^2={fwd_r2:.3f}"
    )
    logger.info(
        f"backward fit (mm/s): y={bwd_slope:.2f}x+{bwd_intercept:.2f}, R^2={bwd_r2:.3f}"
    )

    plt.figure()
    plt.scatter(fwd_x, fwd_y, color="tab:blue", label="forward duration (>0) data")
    plt.plot(fwd_x, fwd_pred, color="tab:blue", linestyle="--",
             label=f"forward fit: y={fwd_slope:.1f}x+{fwd_intercept:.1f}  R^2={fwd_r2:.3f}")
    plt.scatter(bwd_x, bwd_y, color="tab:red", label="backward |duration| data")
    plt.plot(bwd_x, bwd_pred, color="tab:red", linestyle="--",
             label=f"backward fit: y={bwd_slope:.1f}x+{bwd_intercept:.1f}  R^2={bwd_r2:.3f}")
    plt.xlabel("duration (s)")
    plt.ylabel("distance travelled (mm)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    output_path = os.path.join(folder, "distance_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return fwd_slope, fwd_intercept, bwd_slope, bwd_intercept


# computes per-move distance errors (|target| - actual_mm), saves a scatter +
# horizontal L2 line, returns the L2 score in mm
def analyse_distance_verify(folder):
    rows = _read_csv(folder, "verify_distance.csv")
    errors = distance_errors(rows)
    score = l2_score(errors)

    logger.info(f"distance L2: {score:.2f} mm over {len(errors)} moves")

    xs = np.arange(1, len(errors) + 1)

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

    output_path = os.path.join(folder, "distance_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
