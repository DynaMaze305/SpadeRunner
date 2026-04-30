"""Linear regression + plot for the rotation calibration and verification.

Called by the calibrator agent right after each rotation run, and by the
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
    rotation_diffs_by_target,
    rotation_points,
)
from common.config import ARUCO_ANGLE_OFFSET


logger = logging.getLogger(__name__)


def _read_csv(folder, name):
    csv_path = os.path.join(folder, name)
    with open(csv_path, "r", newline="") as f:
        return list(csv.DictReader(f))


# fits (duration, angle_diff) for positive and negative durations,
# saves the scatter + regression figure, returns the four numbers
# the calibrator pushes to the MotionAgent: (pos_slope, pos_intercept,
# neg_slope, neg_intercept) — same signed convention as rotation_points
def analyse_rotation(folder):
    rows = _read_csv(folder, "rotation.csv")
    positive, negative = rotation_points(rows)

    # bot solves duration = (abs(target_angle) - intercept) / slope and applies
    # the sign separately, so fit both directions in the abs domain — that way
    # the slope/intercept we send match the bot's convention
    pos_x = np.array([abs(d) for d, _ in positive])
    pos_y = np.array([abs(a) for _, a in positive])
    neg_x = np.array([abs(d) for d, _ in negative])
    neg_y = np.array([abs(a) for _, a in negative])

    pos_slope, pos_intercept, pos_r2 = linear_fit(pos_x, pos_y)
    neg_slope, neg_intercept, neg_r2 = linear_fit(neg_x, neg_y)

    pos_pred = pos_slope * pos_x + pos_intercept
    neg_pred = neg_slope * neg_x + neg_intercept

    logger.info(
        f"positive fit: y={pos_slope:.2f}x+{pos_intercept:.2f}, R^2={pos_r2:.3f}"
    )
    logger.info(
        f"negative fit: y={neg_slope:.2f}x+{neg_intercept:.2f}, R^2={neg_r2:.3f}"
    )

    plt.figure()
    plt.scatter(pos_x, pos_y, color="tab:blue", label="positive duration (CW) data")
    plt.plot(pos_x, pos_pred, color="tab:blue", linestyle="--",
             label=f"CW fit: y={pos_slope:.1f}x+{pos_intercept:.1f}  R^2={pos_r2:.3f}")
    plt.scatter(neg_x, neg_y, color="tab:red", label="negative duration (CCW) data")
    plt.plot(neg_x, neg_pred, color="tab:red", linestyle="--",
             label=f"CCW fit: y={neg_slope:.1f}x+{neg_intercept:.1f}  R^2={neg_r2:.3f}")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.axvline(x=0, color="black", linestyle=":", linewidth=0.8)
    plt.xlabel("duration (s)")
    plt.ylabel("measured rotation diff (deg)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    output_path = os.path.join(folder, "rotation_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return pos_slope, pos_intercept, neg_slope, neg_intercept


# groups per-move rotation diff by target angle, scatters each direction in
# its own color with a horizontal target reference line, prints per-direction
# L2 in the legend. returns the overall L2 (used for score.txt).
def analyse_rotation_verify(folder):
    rows = _read_csv(folder, "verify_rotation.csv")
    groups = rotation_diffs_by_target(rows, ARUCO_ANGLE_OFFSET)

    palette = ["tab:blue", "tab:red", "tab:green", "tab:orange", "tab:purple"]

    plt.figure()
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)

    all_errors = []
    for i, target in enumerate(sorted(groups)):
        diffs = groups[target]
        errors = [target - d for d in diffs]
        l2 = l2_score(errors)
        all_errors.extend(errors)
        color = palette[i % len(palette)]
        xs = np.arange(1, len(diffs) + 1)
        plt.scatter(xs, diffs, color=color,
                    label=f"target {target:+.0f}°  (L2 = {l2:.2f}°, n={len(diffs)})")
        plt.axhline(y=target, color=color, linestyle="--", alpha=0.6)
        logger.info(f"target {target:+.0f}° L2: {l2:.2f} deg over {len(diffs)} moves")

    score = l2_score(all_errors)
    logger.info(f"rotation overall L2: {score:.2f} deg over {len(all_errors)} moves")

    plt.xlabel("trial index per direction")
    plt.ylabel("measured rotation diff (deg)")
    plt.title(f"verify_rotation: {os.path.basename(folder)}  total L2 = {score:.2f}°")
    plt.legend()
    plt.grid(True)

    output_path = os.path.join(folder, "rotation_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
