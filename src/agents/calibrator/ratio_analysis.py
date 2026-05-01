"""linear regression + L2 scoring for ratio moves, with matplotlib plots
called by the calibrator agent and by the matching scripts/
"""

import csv
import logging
import os

import matplotlib.pyplot as plt
import numpy as np

from agents.calibrator.calibration_math import (
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


# fits (ratio, alpha) per direction and returns the zero-crossing ratios
def analyse_ratio(folder):

    # loads the calibration rows
    rows = _read_csv(folder, "ratio.csv")
    forward, backward = ratio_points(rows, ARUCO_ANGLE_OFFSET)

    # sorts by ratio so the regression line draws cleanly
    forward.sort()
    backward.sort()

    fwd_x = np.array([ratio for ratio, alpha in forward])
    fwd_y = np.array([alpha for ratio, alpha in forward])
    bwd_x = np.array([ratio for ratio, alpha in backward])
    bwd_y = np.array([alpha for ratio, alpha in backward])

    # does linear regression on each direction
    fwd_slope, fwd_intercept, fwd_r2 = linear_fit(fwd_x, fwd_y)
    bwd_slope, bwd_intercept, bwd_r2 = linear_fit(bwd_x, bwd_y)

    fwd_line = fwd_slope * fwd_x + fwd_intercept
    bwd_line = bwd_slope * bwd_x + bwd_intercept

    # finds the ratio that gives 0 deg deviation
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

    # builds the regression plot
    plt.figure()
    plt.scatter(fwd_x, fwd_y, color="tab:blue", label="forward (target_distance > 0) data")
    plt.plot(fwd_x, fwd_line, color="tab:blue", linestyle="--",
             label=f"forward fit: y={fwd_slope:.1f}x+{fwd_intercept:.1f}  R^2={fwd_r2:.3f}")
    plt.scatter(bwd_x, bwd_y, color="tab:red", label="backward (target_distance < 0) data")
    plt.plot(bwd_x, bwd_line, color="tab:red", linestyle="--",
             label=f"backward fit: y={bwd_slope:.1f}x+{bwd_intercept:.1f}  R^2={bwd_r2:.3f}")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.xlabel("ratio")
    plt.ylabel("angle alpha (deg)\n+ left  /  - right (math convention)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    # saves the figure in the run folder
    output_path = os.path.join(folder, "ratio_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return fwd_ratio, bwd_ratio


# scores the verification moves with L2 and plots per-move alpha
def analyse_ratio_verify(folder):

    # loads the verification rows
    rows = _read_csv(folder, "verify_ratio.csv")
    forward, backward = ratio_points(rows, ARUCO_ANGLE_OFFSET)

    # computes the overall L2 score across both directions
    fwd_alphas = [alpha for ratio, alpha in forward]
    bwd_alphas = [alpha for ratio, alpha in backward]
    alphas = fwd_alphas + bwd_alphas
    score = l2_score(alphas)

    logger.info(f"ratio L2: {score:.2f} deg over {len(alphas)} moves")

    fwd_xs = np.arange(1, len(fwd_alphas) + 1)
    bwd_xs = np.arange(len(fwd_alphas) + 1, len(alphas) + 1)

    # builds the L2 plot
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

    # saves the figure in the run folder
    output_path = os.path.join(folder, "ratio_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
