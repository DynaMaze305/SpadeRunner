"""Plot for linear regression model on the ratio (angle deviation)
    Co-author: ClaudeAI on all matplotlib graphs
"""

import argparse
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

# match the navigator: read the per-robot aruco offset from common.config
sys.path.insert(0, os.path.join(ROOT, "src"))
from common.config import ARUCO_ANGLE_OFFSET, ROBOT_NUM
print(f"robot {ROBOT_NUM}, aruco angle offset: {ARUCO_ANGLE_OFFSET} deg")


# parse cli args: optional run id and optional --step for per-step detail plot
parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="calibration run id; defaults to most recent run")
parser.add_argument("--step", type=int, default=None,
                    help="show detailed geometry for the move ending at this row")
args = parser.parse_args()


# pick the run folder from the run id, otherwise take the most recent one
if args.run_id is not None:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, f"calibration_{args.run_id}_*"))
    if not folders:
        sys.exit(f"no calibration folder for run {args.run_id} in {CALIBRATION_DIR}/")
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


# detailed view of one move: --step N analyses the move from row N-1 to row N
if args.step is not None:
    if args.step < 1 or args.step >= len(rows):
        sys.exit(f"step {args.step} out of range, valid: 1..{len(rows)-1}")

    prev_row = rows[args.step - 1]
    curr_row = rows[args.step]

    prev_angle_raw = float(prev_row["measured_angle"])
    prev_angle = (prev_angle_raw + ARUCO_ANGLE_OFFSET + 180.0) % 360.0 - 180.0
    prev_x = float(prev_row["measured_x"])
    prev_y = float(prev_row["measured_y"])

    curr_angle_raw = float(curr_row["measured_angle"])
    curr_angle = (curr_angle_raw + ARUCO_ANGLE_OFFSET + 180.0) % 360.0 - 180.0
    curr_x = float(curr_row["measured_x"])
    curr_y = float(curr_row["measured_y"])

    ratio = float(curr_row["ratio"])
    target_distance = float(curr_row["target_distance"])

    # actual movement vector in image pixels
    dx = curr_x - prev_x
    dy_image = curr_y - prev_y

    # image y axis points down, flip for math convention
    dy_math = -dy_image

    # distance travelled (pixels)
    distance = math.sqrt(dx ** 2 + dy_math ** 2)

    # angle of the movement vector, math convention (deg, same convention as aruco)
    move_angle = math.degrees(math.atan2(dy_math, dx))

    # signed angle between movement and previous orientation, wrapped into [-180, 180]
    alpha = (move_angle - prev_angle + 180.0) % 360.0 - 180.0

    # for backward moves the expected direction is opposite to prev_angle,
    # so flip alpha so left/right match the forward sign convention (left=+, right=-)
    if target_distance < 0:
        alpha = (180.0 - alpha + 180.0) % 360.0 - 180.0

    # orientation arrow length matches the commanded distance for visual scale
    # apply the angle in math convention but subtract sin for y because image y points down,
    # so the arrow visually matches what aruco reports
    L = abs(target_distance) if target_distance != 0 else distance

    prev_arrow_x = prev_x + L * math.cos(math.radians(prev_angle))
    prev_arrow_y = prev_y - L * math.sin(math.radians(prev_angle))

    curr_arrow_x = curr_x + L * math.cos(math.radians(curr_angle))
    curr_arrow_y = curr_y - L * math.sin(math.radians(curr_angle))


    # plot in image-pixel coordinates with the y axis inverted so it matches the camera frame
    plt.figure()

    # previous orientation arrow
    plt.plot([prev_x, prev_arrow_x], [prev_y, prev_arrow_y], color="tab:blue", lw=2,
             label=f"prev orientation ({prev_angle:.1f} deg)")
    plt.annotate("", xy=(prev_arrow_x, prev_arrow_y), xytext=(prev_x, prev_y),
                 arrowprops=dict(arrowstyle="->", color="tab:blue", lw=2))

    # current orientation arrow
    plt.plot([curr_x, curr_arrow_x], [curr_y, curr_arrow_y], color="tab:orange", lw=2,
             label=f"curr orientation ({curr_angle:.1f} deg)")
    plt.annotate("", xy=(curr_arrow_x, curr_arrow_y), xytext=(curr_x, curr_y),
                 arrowprops=dict(arrowstyle="->", color="tab:orange", lw=2))

    # actual movement vector from start to end
    plt.plot([prev_x, curr_x], [prev_y, curr_y], color="tab:green", lw=2, linestyle="--",
             label=f"movement (distance={distance:.1f} px, move_angle={move_angle:.1f} deg)")
    plt.annotate("", xy=(curr_x, curr_y), xytext=(prev_x, prev_y),
                 arrowprops=dict(arrowstyle="->", color="tab:green", lw=2, linestyle="--"))

    # start and end markers
    plt.scatter(prev_x, prev_y, color="tab:red", s=90, zorder=5,
                label=f"start ({prev_x:.0f}, {prev_y:.0f})")
    plt.scatter(curr_x, curr_y, color="tab:red", s=90, zorder=5,
                label=f"end ({curr_x:.0f}, {curr_y:.0f})")

    plt.text(prev_x, prev_y, f"  alpha = {alpha:.2f} deg",
             color="black", fontsize=11, va="bottom", ha="left")

    # square axis limits so 1 px in x = 1 px in y both in scale and on screen
    all_x = [prev_x, curr_x, prev_arrow_x, curr_arrow_x]
    all_y = [prev_y, curr_y, prev_arrow_y, curr_arrow_y]
    center_x = (min(all_x) + max(all_x)) / 2
    center_y = (min(all_y) + max(all_y)) / 2
    half_range = max(max(all_x) - min(all_x), max(all_y) - min(all_y)) / 2 * 1.25
    if half_range == 0:
        half_range = 50
    plt.xlim(center_x - half_range, center_x + half_range)
    plt.ylim(center_y - half_range, center_y + half_range)

    plt.xlabel("x (px)")
    plt.ylabel("y (px)")
    plt.title(f"step {args.step}: ratio={ratio}, target_distance={target_distance}, alpha={alpha:.2f} deg")
    plt.grid(True)
    plt.gca().set_aspect("equal")
    plt.gca().invert_yaxis()
    plt.legend()

    output_path = os.path.join(folder, f"ratio_step_{args.step}.png")
    plt.savefig(output_path)
    print(f"saved: {output_path}")

    plt.show()
    sys.exit(0)


# walk the rows and compute the angle between the previous orientation and the
# actual movement vector
# split the points by direction: forward (positive distance) and backward (negative distance)
forward_points = []
backward_points = []
prev_angle = None
prev_x = None
prev_y = None

for row in rows:
    angle_raw = float(row["measured_angle"])
    angle = (angle_raw + ARUCO_ANGLE_OFFSET + 180.0) % 360.0 - 180.0
    x = float(row["measured_x"])
    y = float(row["measured_y"])
    ratio = float(row["ratio"])
    target_distance = float(row["target_distance"])

    if math.isnan(angle) or math.isnan(x) or math.isnan(y):
        prev_angle = None
        prev_x = None
        prev_y = None
        continue

    if prev_angle is None:
        prev_angle = angle
        prev_x = x
        prev_y = y
        continue

    # movement vector in image pixels
    dx = x - prev_x
    dy = y - prev_y

    # image y axis points down, flip for math convention
    dy_math = -dy

    # angle of the movement vector, math convention (deg)
    move_angle = math.degrees(math.atan2(dy_math, dx))

    # signed angle between movement and previous orientation, wrapped into [-180, 180]
    alpha = (move_angle - prev_angle + 180.0) % 360.0 - 180.0

    # for backward moves the expected direction is opposite to prev_angle,
    # so flip alpha so left/right match the forward sign convention (left=+, right=-)
    if target_distance < 0:
        alpha = (180.0 - alpha + 180.0) % 360.0 - 180.0

    if target_distance > 0:
        forward_points.append((ratio, alpha))
    elif target_distance < 0:
        backward_points.append((ratio, alpha))

    prev_angle = angle
    prev_x = x
    prev_y = y


# sort by ratio so the regression line plots in order
forward_points.sort()
backward_points.sort()

print(f"forward points: {len(forward_points)}")
print(f"backward points: {len(backward_points)}")

# split (ratio, alpha) pairs into x/y arrays for numpy
fwd_x = np.array([r for r, _ in forward_points])
fwd_y = np.array([a for _, a in forward_points])
bwd_x = np.array([r for r, _ in backward_points])
bwd_y = np.array([a for _, a in backward_points])


# linear regression for each direction: y = slope * x + intercept, plus R^2
fwd_slope, fwd_intercept = np.polyfit(fwd_x, fwd_y, 1)
fwd_pred = fwd_slope * fwd_x + fwd_intercept
fwd_ss_res = np.sum((fwd_y - fwd_pred) ** 2)
fwd_ss_tot = np.sum((fwd_y - np.mean(fwd_y)) ** 2)
fwd_r2 = 1 - fwd_ss_res / fwd_ss_tot
print(f"forward  fit: y = {fwd_slope:.2f} * x + {fwd_intercept:.2f}   R^2 = {fwd_r2:.4f}")

bwd_slope, bwd_intercept = np.polyfit(bwd_x, bwd_y, 1)
bwd_pred = bwd_slope * bwd_x + bwd_intercept
bwd_ss_res = np.sum((bwd_y - bwd_pred) ** 2)
bwd_ss_tot = np.sum((bwd_y - np.mean(bwd_y)) ** 2)
bwd_r2 = 1 - bwd_ss_res / bwd_ss_tot
print(f"backward fit: y = {bwd_slope:.2f} * x + {bwd_intercept:.2f}   R^2 = {bwd_r2:.4f}")


# scatter + fit line, both directions on the same figure
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

# save the figure next to the csv inside the run folder
output_path = os.path.join(folder, "ratio_linear_regression.png")
plt.savefig(output_path)
print(f"saved: {output_path}")

plt.show()
