"""Linear regression + plot for the ratio calibration and verification.

Called by the calibrator agent right after each ratio run, and by the
matching scripts in scripts/ when the operator wants to re-render an old run.
"""

import csv
import logging
import os

import matplotlib.pyplot as plt
import numpy as np

from common.calibration_math import (
    l2_score,
    linear_fit,
    ratio_points,
    zero_crossing,
)
from common.config import ARUCO_ANGLE_OFFSET


logger = logging.getLogger(__name__)


def _read_csv(folder, name):
    csv_path = os.path.join(folder, name)
    with open(csv_path, "r", newline="") as f:
        return list(csv.DictReader(f))


# fits (ratio, alpha) per direction and returns the zero-crossings,
# i.e. the ratio that produces 0 deg deviation. saves the regression figure.
def analyse_ratio(folder):
    rows = _read_csv(folder, "ratio.csv")
    forward, backward = ratio_points(rows, ARUCO_ANGLE_OFFSET)

    forward.sort()
    backward.sort()

    fwd_x = np.array([r for r, _ in forward])
    fwd_y = np.array([a for _, a in forward])
    bwd_x = np.array([r for r, _ in backward])
    bwd_y = np.array([a for _, a in backward])

    fwd_slope, fwd_intercept, fwd_r2 = linear_fit(fwd_x, fwd_y)
    bwd_slope, bwd_intercept, bwd_r2 = linear_fit(bwd_x, bwd_y)

    fwd_pred = fwd_slope * fwd_x + fwd_intercept
    bwd_pred = bwd_slope * bwd_x + bwd_intercept

    fwd_ratio = zero_crossing(fwd_slope, fwd_intercept)
    bwd_ratio = zero_crossing(bwd_slope, bwd_intercept)

    logger.info(
        f"forward fit: y={fwd_slope:.2f}x+{fwd_intercept:.2f}, "
        f"R^2={fwd_r2:.3f}, ratio_forward={fwd_ratio}"
    )
    logger.info(
        f"backward fit: y={bwd_slope:.2f}x+{bwd_intercept:.2f}, "
        f"R^2={bwd_r2:.3f}, ratio_backward={bwd_ratio}"
    )

    plt.figure()
    plt.scatter(fwd_x, fwd_y, color="tab:blue", label="forward (target_distance > 0) data")
    plt.plot(fwd_x, fwd_pred, color="tab:blue", linestyle="--",
             label=f"forward fit: y={fwd_slope:.1f}x+{fwd_intercept:.1f}  R^2={fwd_r2:.3f}")
    plt.scatter(bwd_x, bwd_y, color="tab:red", label="backward (target_distance < 0) data")
    plt.plot(bwd_x, bwd_pred, color="tab:red", linestyle="--",
             label=f"backward fit: y={bwd_slope:.1f}x+{bwd_intercept:.1f}  R^2={bwd_r2:.3f}")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.xlabel("ratio")
    plt.ylabel("angle alpha (deg)\n+ left  /  - right (math convention)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    output_path = os.path.join(folder, "ratio_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return fwd_ratio, bwd_ratio


# concatenates forward + backward alphas, scatters per-move alpha + L2 line,
# returns the L2 score in degrees
def analyse_ratio_verify(folder):
    rows = _read_csv(folder, "verify_ratio.csv")
    forward, backward = ratio_points(rows, ARUCO_ANGLE_OFFSET)

    fwd_alphas = [a for _, a in forward]
    bwd_alphas = [a for _, a in backward]
    alphas = fwd_alphas + bwd_alphas
    score = l2_score(alphas)

    logger.info(f"ratio L2: {score:.2f} deg over {len(alphas)} moves")

    fwd_xs = np.arange(1, len(fwd_alphas) + 1)
    bwd_xs = np.arange(len(fwd_alphas) + 1, len(alphas) + 1)

    plt.figure()
    plt.scatter(fwd_xs, fwd_alphas, color="tab:blue", label="forward alpha")
    plt.scatter(bwd_xs, bwd_alphas, color="tab:red", label="backward alpha")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.axhline(y=score, color="tab:green", linestyle="--",
                label=f"L2 = {score:.2f} deg")
    plt.axhline(y=-score, color="tab:green", linestyle="--")
    plt.xlabel("move index")
    plt.ylabel("alpha (deg)\n+ left  /  - right")
    plt.title(f"verify_ratio: {os.path.basename(folder)}  L2={score:.2f} deg")
    plt.legend()
    plt.grid(True)

    output_path = os.path.join(folder, "ratio_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
