"""
    Plots for linear regression models on the speed, one regression per run
    (a "run" = one continuous sequence of growing durations in the same direction)
    Co-author: ClaudeAI on all matplotlib graphs
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


# default would be the most recent run, kept here for later
# folders = glob.glob(os.path.join(CALIBRATION_DIR, "calibration_*"))
# if not folders:
#     sys.exit(f"no calibration folder found in {CALIBRATION_DIR}/")
# folder = max(folders, key=os.path.getmtime)

# pinned to a specific run to compare runs side by side
folder = "calibration_photos/calibration_55_20260423_172249"

# anything farther than this between two consecutive frames is treated as an outlier (marker jump / lost detection)
MAX_DISTANCE = 100

# one color per run, two palettes so forward/backward stay visually separated
forward_colors = ["tab:blue", "tab:cyan", "tab:green", "navy", "teal", "mediumseagreen", "deepskyblue"]
backward_colors = ["tab:red", "tab:orange", "tab:pink", "crimson", "darkorange", "salmon", "magenta"]

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


# split the data into successive "runs" per direction
# a new run is detected when the duration drops back down (= calibration loop restarted from the smallest value)
positive_runs = [[]]
negative_runs = [[]]
prev_pos_dur = 0.0
prev_neg_dur = 0.0
prev_x = None
prev_y = None

for row in rows:
    x = float(row["measured_x"])
    y = float(row["measured_y"])
    duration = float(row["duration"])

    if math.isnan(x) or math.isnan(y):
        prev_x = None
        prev_y = None
        continue

    if prev_x is None:
        prev_x = x
        prev_y = y
        continue

    # distance in pixel between the previous and the current marker position
    dx = x - prev_x
    dy = y - prev_y
    distance = math.sqrt(dx * dx + dy * dy)
    prev_x = x
    prev_y = y

    if distance > MAX_DISTANCE:
        print(f"skipping outlier: duration={duration} distance={distance:.1f}")
        continue

    if duration > 0:
        if duration < prev_pos_dur:
            positive_runs.append([])
        positive_runs[-1].append((duration, distance))
        prev_pos_dur = duration
    elif duration < 0:
        d = abs(duration)
        if d < prev_neg_dur:
            negative_runs.append([])
        negative_runs[-1].append((d, distance))
        prev_neg_dur = d


# need at least 2 points to fit a line, drop the runs that are too short
positive_runs = [r for r in positive_runs if len(r) >= 2]
negative_runs = [r for r in negative_runs if len(r) >= 2]

print(f"forward runs: {len(positive_runs)}")
print(f"backward runs: {len(negative_runs)}")


plt.figure()

# one regression per forward run, all on the same figure
for i, run in enumerate(positive_runs):
    color = forward_colors[i % len(forward_colors)]
    xs = np.array([d for d, _ in run])
    ys = np.array([a for _, a in run])
    slope, intercept = np.polyfit(xs, ys, 1)
    pred = slope * xs + intercept
    ss_res = np.sum((ys - pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    print(f"forward run {i + 1}: y = {slope:.2f} * x + {intercept:.2f}   R^2 = {r2:.4f}")
    plt.scatter(xs, ys, color=color)
    plt.plot(xs, pred, color=color, linestyle="--",
             label=f"fwd run {i + 1}: y={slope:.1f}x+{intercept:.1f}  R^2={r2:.3f}")

# same thing for backward runs, with the second color palette
for i, run in enumerate(negative_runs):
    color = backward_colors[i % len(backward_colors)]
    xs = np.array([d for d, _ in run])
    ys = np.array([a for _, a in run])
    slope, intercept = np.polyfit(xs, ys, 1)
    pred = slope * xs + intercept
    ss_res = np.sum((ys - pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    print(f"backward run {i + 1}: y = {slope:.2f} * x + {intercept:.2f}   R^2 = {r2:.4f}")
    plt.scatter(xs, ys, color=color)
    plt.plot(xs, pred, color=color, linestyle="--",
             label=f"bwd run {i + 1}: y={slope:.1f}x+{intercept:.1f}  R^2={r2:.3f}")

plt.xlabel("duration (s)")
plt.ylabel("distance (px)")
plt.title(f"calibration per run: {os.path.basename(folder)}")
plt.legend()
plt.grid(True)

# save the figure next to the csv inside the run folder
output_path = os.path.join(folder, "speed_per_run_linear_regression.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

plt.show()