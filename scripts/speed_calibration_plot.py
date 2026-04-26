"""Plots for linear regression models on the speed (forward / backward distance per duration)
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


# walk the rows and compute the distance between two consecutive marker positions
# split the points by direction: forward (positive duration) and backward (negative duration)
positive_points = []
negative_points = []
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
        positive_points.append((duration, distance))
    elif duration < 0:
        negative_points.append((abs(duration), distance))

# sort by duration so the regression line plots in order
positive_points.sort()
negative_points.sort()

print(f"positive points: {len(positive_points)}")
print(f"negative points: {len(negative_points)}")

# split the (duration, distance) pairs into x/y arrays for numpy
pos_x = np.array([d for d, _ in positive_points])
pos_y = np.array([a for _, a in positive_points])
neg_x = np.array([d for d, _ in negative_points])
neg_y = np.array([a for _, a in negative_points])


# linear regression for each direction: y = slope * x + intercept, plus R^2
pos_slope, pos_intercept = np.polyfit(pos_x, pos_y, 1)
pos_pred = pos_slope * pos_x + pos_intercept
pos_ss_res = np.sum((pos_y - pos_pred) ** 2)
pos_ss_tot = np.sum((pos_y - np.mean(pos_y)) ** 2)
pos_r2 = 1 - pos_ss_res / pos_ss_tot
print(f"forward  fit: y = {pos_slope:.2f} * x + {pos_intercept:.2f}   R^2 = {pos_r2:.4f}")

neg_slope, neg_intercept = np.polyfit(neg_x, neg_y, 1)
neg_pred = neg_slope * neg_x + neg_intercept
neg_ss_res = np.sum((neg_y - neg_pred) ** 2)
neg_ss_tot = np.sum((neg_y - np.mean(neg_y)) ** 2)
neg_r2 = 1 - neg_ss_res / neg_ss_tot
print(f"backward fit: y = {neg_slope:.2f} * x + {neg_intercept:.2f}   R^2 = {neg_r2:.4f}")


# scatter + fit line, both directions on the same figure
plt.figure()
plt.scatter(pos_x, pos_y, color="tab:blue", label="positive duration (forward) data")
plt.plot(pos_x, pos_pred, color="tab:blue", linestyle="--",
         label=f"forward fit: y={pos_slope:.1f}x+{pos_intercept:.1f}  R^2={pos_r2:.3f}")
plt.scatter(neg_x, neg_y, color="tab:red", label="negative duration (backward) data")
plt.plot(neg_x, neg_pred, color="tab:red", linestyle="--",
         label=f"backward fit: y={neg_slope:.1f}x+{neg_intercept:.1f}  R^2={neg_r2:.3f}")
plt.xlabel("duration (s)")
plt.ylabel("distance (px)")
plt.title(f"calibration: {os.path.basename(folder)}")
plt.legend()
plt.grid(True)

# save the figure next to the csv inside the run folder
output_path = os.path.join(folder, "speed_linear_regression.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

plt.show()