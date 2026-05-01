"""Plots that show if the robot outputs consistent values form the linera models
    Co-author: ClaudeAI on all mattplotlib graphs
"""


import csv
import glob
import os
import sys

import matplotlib.pyplot as plt
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CALIBRATION_DIR = os.path.join(ROOT, "calibration_photos")

# share the canonical agent-driven plot + the grouping helper
sys.path.insert(0, os.path.join(ROOT, "src"))
from agents.calibrator.rotation_analysis import analyse_rotation_verify
from agents.calibrator.calibration_math import rotation_diffs_by_target
from common.config import ARUCO_ANGLE_OFFSET


REQUIRE_CSV = "verify_rotation.csv"


# CLI args:  <run_id>  --center <target_angle>
# run_id picks the calibration folder, --center adds a Gaussian-style detail plot for one target
run_id = None
center = None
arg_index = 1
while arg_index < len(sys.argv):
    if sys.argv[arg_index] == "--center":
        center = float(sys.argv[arg_index + 1])
        arg_index += 2
    else:
        run_id = sys.argv[arg_index]
        arg_index += 1


# pick the run folder: by id if given, else most recent with the right csv
if run_id is not None:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, f"calibration_{run_id}_*"))
else:
    folders = sorted(
        glob.glob(os.path.join(CALIBRATION_DIR, "calibration_*")),
        key=os.path.getmtime,
        reverse=True,
    )

candidates = [path for path in folders if os.path.exists(os.path.join(path, REQUIRE_CSV))]
if not candidates:
    sys.exit(f"no calibration folder containing {REQUIRE_CSV} in {CALIBRATION_DIR}/")
folder = candidates[0]


print(f"folder: {folder}")

# canonical agent-driven per-direction plot (saves rotation_verification.png)
score = analyse_rotation_verify(folder)
print(f"total L2 = {score:.2f} deg")


# --- per-target stats + optional distribution detail ---

# re-load the csv so we can group diffs by target and compute stats below
csv_path = os.path.join(folder, REQUIRE_CSV)
rows = []
with open(csv_path, "r", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# groups[target] = list of measured rotation diffs for that target
groups = rotation_diffs_by_target(rows, ARUCO_ANGLE_OFFSET)

# per-target stats table: trial count, mean diff, std, bias, max abs error
print()
print("target  n   mean      std     bias      max_abs_err")
for target in sorted(groups):
    diffs = np.array(groups[target])
    mean = diffs.mean()
    std = diffs.std()
    bias = mean - target
    max_abs_err = np.max(np.abs(diffs - target))
    print(f"{target:+6.1f}  {len(diffs):2d}  {mean:+7.3f}  {std:6.3f}  {bias:+7.3f}  {max_abs_err:7.3f}")


# --center: distribution detail (mean line, ±1σ, target ref, Gaussian curve, stats box)
if center is not None:
    if center not in groups:
        sys.exit(f"no data for target {center}, available: {sorted(groups)}")

    # stats for this single target
    diffs = np.array(groups[center])
    count = len(diffs)
    mean = diffs.mean()
    std = diffs.std()
    bias = mean - center

    # horizontal scatter of measured diffs at this target
    fig, ax2 = plt.subplots(figsize=(8, 6))

    # tiny vertical jitter so dots with the same value don't overlap
    jitter_y = np.random.uniform(-0.05, 0.05, count)
    ax2.scatter(diffs, jitter_y, color="tab:blue", alpha=0.8)

    # vertical lines: mean, ±1σ, target reference
    ax2.axvline(mean, color="tab:blue", linestyle="-", linewidth=1.5, label=f"mean = {mean:+.2f}")
    ax2.axvline(mean + std, color="tab:blue", linestyle="--", alpha=0.6, label=f"±1σ = {std:.2f}")
    ax2.axvline(mean - std, color="tab:blue", linestyle="--", alpha=0.6)
    ax2.axvline(center, color="black", linestyle=":", alpha=0.7, label=f"target = {center:+.1f}")

    # overlay a gaussian centered on the mean for visual reference
    if std > 0:
        x_curve = np.linspace(center - 50, center + 50, 400)
        pdf = np.exp(-((x_curve - mean) ** 2) / (2 * std ** 2))
        pdf_y = 0.5 + pdf * 0.4
        ax2.plot(x_curve, pdf_y, color="gray", alpha=0.7, label="Gaussian PDF")

    # stats summary box, top-left of the figure
    stats_text = (
        f"n = {count}\n"
        f"mean = {mean:+.3f}\n"
        f"std  = {std:.3f}\n"
        f"bias = {bias:+.3f}\n"
        f"min  = {diffs.min():+.3f}\n"
        f"max  = {diffs.max():+.3f}"
    )
    ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9,
             verticalalignment="top",
             bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    ax2.set_xlim(center - 50, center + 50)
    ax2.set_ylim(-0.5, 1.5)
    ax2.set_yticks([])
    ax2.set_xlabel("measured rotation diff (deg)")
    ax2.set_title(f"distribution at target {center:+.1f}°")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, axis="x")

    plt.tight_layout()
    detail_path = os.path.join(folder, "rotation_verification_detail.png")
    plt.savefig(detail_path)
    print(f"saved: {detail_path}")


plt.show()
