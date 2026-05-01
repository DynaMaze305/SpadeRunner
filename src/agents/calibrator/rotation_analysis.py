"""linear regression + L2 scoring for rotation moves, with matplotlib plots
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
    rotation_diffs_by_target,
    rotation_points,
)
from common.config import ARUCO_ANGLE_OFFSET


logger = logging.getLogger(__name__)


def _read_csv(folder, name):
    csv_path = os.path.join(folder, name)
    with open(csv_path, "r", newline="") as f:
        return list(csv.DictReader(f))


# fits (duration, angle_diff) per direction and plots the regression
def analyse_rotation(folder):

    # loads the calibration rows
    rows = _read_csv(folder, "rotation.csv")
    positive, negative = rotation_points(rows)

    # abs domain so slope/intercept match the bot's duration formula
    pos_x = np.array([abs(duration) for duration, angle_diff in positive])
    pos_y = np.array([abs(angle_diff) for duration, angle_diff in positive])
    neg_x = np.array([abs(duration) for duration, angle_diff in negative])
    neg_y = np.array([abs(angle_diff) for duration, angle_diff in negative])

    # does linear regression on each direction
    pos_slope, pos_intercept, pos_r2 = linear_fit(pos_x, pos_y)
    neg_slope, neg_intercept, neg_r2 = linear_fit(neg_x, neg_y)

    pos_line = pos_slope * pos_x + pos_intercept
    neg_line = neg_slope * neg_x + neg_intercept

    logger.info(
        f"positive fit: y={pos_slope:.2f}x+{pos_intercept:.2f}, R^2={pos_r2:.3f}"
    )
    logger.info(
        f"negative fit: y={neg_slope:.2f}x+{neg_intercept:.2f}, R^2={neg_r2:.3f}"
    )

    # builds the regression plot
    plt.figure()
    plt.scatter(pos_x, pos_y, color="tab:blue", label="positive duration (CW) data")
    plt.plot(pos_x, pos_line, color="tab:blue", linestyle="--",
             label=f"CW fit: y={pos_slope:.1f}x+{pos_intercept:.1f}  R^2={pos_r2:.3f}")
    plt.scatter(neg_x, neg_y, color="tab:red", label="negative duration (CCW) data")
    plt.plot(neg_x, neg_line, color="tab:red", linestyle="--",
             label=f"CCW fit: y={neg_slope:.1f}x+{neg_intercept:.1f}  R^2={neg_r2:.3f}")
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)
    plt.axvline(x=0, color="black", linestyle=":", linewidth=0.8)
    plt.xlabel("duration (s)")
    plt.ylabel("measured rotation diff (deg)")
    plt.title(f"calibration: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)

    # saves the figure in the run folder
    output_path = os.path.join(folder, "rotation_linear_regression.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return pos_slope, pos_intercept, neg_slope, neg_intercept


# scores +/- targets separately with L2 and plots per-target scatter
def analyse_rotation_verify(folder):

    # loads the verification rows and groups them per target angle
    rows = _read_csv(folder, "verify_rotation.csv")
    groups = rotation_diffs_by_target(rows, ARUCO_ANGLE_OFFSET)

    palette = ["tab:blue", "tab:red", "tab:green", "tab:orange", "tab:purple"]

    # builds the per-target plot
    plt.figure()
    plt.axhline(y=0, color="black", linestyle=":", linewidth=0.8)

    # for each target, plots its trials and computes per-target L2
    all_errors = []
    for target_index, target in enumerate(sorted(groups)):
        diffs = groups[target]
        errors = [target - measured for measured in diffs]
        target_l2 = l2_score(errors)
        all_errors.extend(errors)
        color = palette[target_index % len(palette)]
        trial_indices = np.arange(1, len(diffs) + 1)
        plt.scatter(trial_indices, diffs, color=color,
                    label=f"target {target:+.0f}°  (L2 = {target_l2:.2f}°, n={len(diffs)})")
        plt.axhline(y=target, color=color, linestyle="--", alpha=0.6)
        logger.info(f"target {target:+.0f}° L2: {target_l2:.2f} deg over {len(diffs)} moves")

    # computes the overall L2 across all directions
    score = l2_score(all_errors)
    logger.info(f"rotation overall L2: {score:.2f} deg over {len(all_errors)} moves")

    plt.xlabel("trial index per direction")
    plt.ylabel("measured rotation diff (deg)")
    plt.title(f"verify_rotation: {os.path.basename(folder)}  total L2 = {score:.2f}°")
    plt.legend()
    plt.grid(True)

    # saves the figure in the run folder
    output_path = os.path.join(folder, "rotation_verification.png")
    plt.savefig(output_path)
    logger.info(f"saved: {output_path}")

    return score
