"""Plots for linear regression models on the rotation
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


# pick the run folder from a CLI run id, otherwise take the most recent one
if len(sys.argv) > 1:
    run_id = sys.argv[1]
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


# walk the rows and compute the rotation between two consecutive frames
# split the points by direction: CW (positive duration) and CCW (negative duration)
positive_points = []
negative_points = []
prev_angle = None

for row in rows:
    angle = float(row["measured_angle"])
    duration = float(row["duration"])

    if math.isnan(angle):
        prev_angle = None
        continue

    if prev_angle is None:
        prev_angle = angle
        continue

    # wrap the diff into [-180, 180]
    diff = (angle - prev_angle + 180.0) % 360.0 - 180.0
    prev_angle = angle

    if duration > 0:
        positive_points.append((duration, diff))
    elif duration < 0:
        negative_points.append((duration, diff))

# sort by duration so the regression line plots in order
positive_points.sort()
negative_points.sort()

print(f"positive points: {len(positive_points)}")
print(f"negative points: {len(negative_points)}")

# split the (duration, rotation) pairs into x/y arrays for numpy
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
print(f"CW  fit: y = {pos_slope:.2f} * x + {pos_intercept:.2f}   R^2 = {pos_r2:.4f}")

neg_slope, neg_intercept = np.polyfit(neg_x, neg_y, 1)
neg_pred = neg_slope * neg_x + neg_intercept
neg_ss_res = np.sum((neg_y - neg_pred) ** 2)
neg_ss_tot = np.sum((neg_y - np.mean(neg_y)) ** 2)
neg_r2 = 1 - neg_ss_res / neg_ss_tot
print(f"CCW fit: y = {neg_slope:.2f} * x + {neg_intercept:.2f}   R^2 = {neg_r2:.4f}")


# scatter + fit line, both directions on the same figure
plt.figure()
plt.scatter(pos_x, pos_y, color="tab:blue", label="positive duration (CW) data")
plt.plot(pos_x, pos_pred, color="tab:blue", linestyle="--",
         label=f"CW fit: y={pos_slope:.1f}x+{pos_intercept:.1f}  R^2={pos_r2:.3f}")
plt.scatter(neg_x, neg_y, color="tab:red", label="negative duration (CCW) data")
plt.plot(neg_x, neg_pred, color="tab:red", linestyle="--",
         label=f"CCW fit: y={neg_slope:.1f}x+{neg_intercept:.1f}  R^2={neg_r2:.3f}")
plt.xlabel("duration (s)")
plt.ylabel("measured rotation (deg)")
plt.title(f"calibration: {os.path.basename(folder)}")
plt.legend()
plt.grid(True)

# save the figure next to the csv inside the run folder
output_path = os.path.join(folder, "rotation_linear_regression.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

plt.show()
