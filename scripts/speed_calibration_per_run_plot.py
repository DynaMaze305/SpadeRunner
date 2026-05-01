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

# distance > MAX_DISTANCE = outlier (marker jump or lost detection)
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


# new run = duration drops below previous (calibration loop restarted)
positive_runs = [[]]
negative_runs = [[]]
prev_pos_dur = 0.0
prev_neg_dur = 0.0
prev_pixel_x = None
prev_pixel_y = None

for row in rows:
    pixel_x = float(row["measured_x"])
    pixel_y = float(row["measured_y"])
    duration = float(row["duration"])

    if math.isnan(pixel_x) or math.isnan(pixel_y):
        prev_pixel_x = None
        prev_pixel_y = None
        continue

    if prev_pixel_x is None:
        prev_pixel_x = pixel_x
        prev_pixel_y = pixel_y
        continue

    # pixel distance between the previous and the current marker position
    delta_x = pixel_x - prev_pixel_x
    delta_y = pixel_y - prev_pixel_y
    distance_px = math.sqrt(delta_x * delta_x + delta_y * delta_y)
    prev_pixel_x = pixel_x
    prev_pixel_y = pixel_y

    if distance_px > MAX_DISTANCE:
        print(f"skipping outlier: duration={duration} distance={distance_px:.1f}")
        continue

    if duration > 0:
        if duration < prev_pos_dur:
            positive_runs.append([])
        positive_runs[-1].append((duration, distance_px))
        prev_pos_dur = duration
    elif duration < 0:
        abs_duration = abs(duration)
        if abs_duration < prev_neg_dur:
            negative_runs.append([])
        negative_runs[-1].append((abs_duration, distance_px))
        prev_neg_dur = abs_duration


# need at least 2 points to fit a line, drop the runs that are too short
positive_runs = [run for run in positive_runs if len(run) >= 2]
negative_runs = [run for run in negative_runs if len(run) >= 2]

print(f"forward runs: {len(positive_runs)}")
print(f"backward runs: {len(negative_runs)}")


plt.figure()

# one regression per forward run, all on the same figure
for run_index, run in enumerate(positive_runs):
    color = forward_colors[run_index % len(forward_colors)]
    xs = np.array([duration for duration, distance_px in run])
    ys = np.array([distance_px for duration, distance_px in run])
    slope, intercept = np.polyfit(xs, ys, 1)
    line = slope * xs + intercept
    ss_residual = np.sum((ys - line) ** 2)
    ss_total = np.sum((ys - np.mean(ys)) ** 2)
    r_squared = 1 - ss_residual / ss_total if ss_total > 0 else 0.0
    print(f"forward run {run_index + 1}: y = {slope:.2f} * x + {intercept:.2f}   R^2 = {r_squared:.4f}")
    plt.scatter(xs, ys, color=color)
    plt.plot(xs, line, color=color, linestyle="--",
             label=f"fwd run {run_index + 1}: y={slope:.1f}x+{intercept:.1f}  R^2={r_squared:.3f}")

# same thing for backward runs, with the second color palette
for run_index, run in enumerate(negative_runs):
    color = backward_colors[run_index % len(backward_colors)]
    xs = np.array([duration for duration, distance_px in run])
    ys = np.array([distance_px for duration, distance_px in run])
    slope, intercept = np.polyfit(xs, ys, 1)
    line = slope * xs + intercept
    ss_residual = np.sum((ys - line) ** 2)
    ss_total = np.sum((ys - np.mean(ys)) ** 2)
    r_squared = 1 - ss_residual / ss_total if ss_total > 0 else 0.0
    print(f"backward run {run_index + 1}: y = {slope:.2f} * x + {intercept:.2f}   R^2 = {r_squared:.4f}")
    plt.scatter(xs, ys, color=color)
    plt.plot(xs, line, color=color, linestyle="--",
             label=f"bwd run {run_index + 1}: y={slope:.1f}x+{intercept:.1f}  R^2={r_squared:.3f}")

plt.xlabel("duration (s)")
plt.ylabel("distance (px)")
plt.title(f"calibration per run: {os.path.basename(folder)}")
plt.legend()
plt.grid(True)

# save the figure next to the csv inside the run folder
output_path = os.path.join(folder, "speed_per_run_linear_regression.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

# pops the figure in an interactive window
plt.show()
