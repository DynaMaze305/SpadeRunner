"""Plots that show if the robot outputs consistent values form the linera models
    Co-author: ClaudeAI on all mattplotlib graphs
"""


import csv
import glob
import math
import os
import sys

import matplotlib.pyplot as plt
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CALIBRATION_DIR = os.path.join(ROOT, "calibration_photos")


# CLI args:  <run_id>  --center <target_angle>
# run_id picks the calibration folder, --center adds a Gaussian-style detail plot for one target
run_id = None
center = None
argi = 1
while argi < len(sys.argv):
    if sys.argv[argi] == "--center":
        center = float(sys.argv[argi + 1])
        argi += 2
    else:
        run_id = sys.argv[argi]
        argi += 1


# pick the run folder from the run id, otherwise take the most recent one
if run_id is not None:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, f"calibration_{run_id}_*"))
    if not folders:
        sys.exit(f"no calibration folder for run {run_id} in {CALIBRATION_DIR}/")
    folder = folders[0]
else:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, "calibration_*"))
    if not folders:
        sys.exit(f"no calibration folder found in {CALIBRATION_DIR}/")
    folder = max(folders, key=os.path.getmtime)


print(f"folder: {folder}")

# load all csv rows into a list of dicts
csv_paths = glob.glob(os.path.join(folder, "*.csv"))
if not csv_paths:
    sys.exit(f"no csv found in {folder}")
csv_path = csv_paths[0]
print(f"csv: {csv_path}")

rows = []
with open(csv_path, "r", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)
print(f"rows: {len(rows)}")


# walk the rows and group every measured rotation diff by its target angle
groups = {}
prev_angle = None

for row in rows:
    angle = float(row["measured_angle"])
    target = float(row["target_angle"])

    if math.isnan(angle):
        prev_angle = None
        continue

    if prev_angle is None:
        prev_angle = angle
        continue

    # wrap the diff into [-180, 180] then push the sign to match the target direction
    diff = (angle - prev_angle + 180.0) % 360.0 - 180.0
    if target > 0 and diff < 0:
        diff += 360.0
    elif target < 0 and diff > 0:
        diff -= 360.0
    prev_angle = angle

    # the initial reference row has target = 0, skip it
    if target == 0:
        continue

    groups.setdefault(target, []).append(diff)


# stats per target: mean, std, bias vs target, worst error
print()
print("target  n   mean      std     bias      max_abs_err")
for target in sorted(groups):
    diffs = np.array(groups[target])
    mean = diffs.mean()
    std = diffs.std()
    bias = mean - target
    max_abs_err = np.max(np.abs(diffs - target))
    print(f"{target:+6.1f}  {len(diffs):2d}  {mean:+7.3f}  {std:6.3f}  {bias:+7.3f}  {max_abs_err:7.3f}")


colors = ["tab:blue", "tab:red", "tab:green", "tab:orange", "tab:purple"]

# if --center was given, build a side-by-side figure: scatter on the left, distribution on the right
if center is not None:
    if center not in groups:
        sys.exit(f"no data for target {center}, available: {sorted(groups)}")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
else:
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = None

# left plot: every measured diff against its repetition number, with the target as a dashed line
for i, target in enumerate(sorted(groups)):
    diffs = groups[target]
    xs = np.arange(1, len(diffs) + 1)
    color = colors[i % len(colors)]
    ax1.scatter(xs, diffs, color=color, label=f"target {target:+.1f}° (n={len(diffs)})")
    ax1.axhline(target, color=color, linestyle="--", alpha=0.5)

ax1.set_xlabel("repetition")
ax1.set_ylabel("measured rotation diff (deg)")
ax1.set_title(f"rotation verification: {os.path.basename(folder)}")
ax1.set_ylim(-180, 180)
ax1.legend()
ax1.grid(True)


# right plot: distribution detail for the chosen target — mean line, ±1σ, target ref, Gaussian curve, stats box
if ax2 is not None:
    diffs = np.array(groups[center])
    n = len(diffs)
    mean = diffs.mean()
    std = diffs.std()
    bias = mean - center
    dot_color = colors[sorted(groups).index(center) % len(colors)]

    # tiny vertical jitter so dots with the same value don't overlap
    jitter_y = np.random.uniform(-0.05, 0.05, n)
    ax2.scatter(diffs, jitter_y, color=dot_color, alpha=0.8)

    ax2.axvline(mean, color=dot_color, linestyle="-", linewidth=1.5, label=f"mean = {mean:+.2f}")
    ax2.axvline(mean + std, color=dot_color, linestyle="--", alpha=0.6, label=f"±1σ = {std:.2f}")
    ax2.axvline(mean - std, color=dot_color, linestyle="--", alpha=0.6)
    ax2.axvline(center, color="black", linestyle=":", alpha=0.7, label=f"target = {center:+.1f}")

    if std > 0:
        x_curve = np.linspace(center - 50, center + 50, 400)
        pdf = np.exp(-((x_curve - mean) ** 2) / (2 * std ** 2))
        pdf_y = 0.5 + pdf * 0.4
        ax2.plot(x_curve, pdf_y, color="gray", alpha=0.7, label="Gaussian PDF")

    stats_text = (
        f"n = {n}\n"
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


# save the figure next to the csv inside the run folder
plt.tight_layout()
output_path = os.path.join(folder, "rotation_verification.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

plt.show()
