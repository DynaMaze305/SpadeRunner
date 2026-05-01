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


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CALIBRATION_DIR = os.path.join(ROOT, "calibration_photos")

# share the same fit + plot as the calibrator agent
sys.path.insert(0, os.path.join(ROOT, "src"))
from agents.calibrator.ratio_analysis import analyse_ratio
from common.config import ARUCO_ANGLE_OFFSET, ROBOT_NUM
print(f"robot {ROBOT_NUM}, aruco angle offset: {ARUCO_ANGLE_OFFSET} deg")


REQUIRE_CSV = "ratio.csv"


# parse cli args: optional run id and optional --step for per-step detail plot
parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="calibration run id; defaults to most recent run with ratio.csv")
parser.add_argument("--step", type=int, default=None,
                    help="show detailed geometry for the move ending at this row")
args = parser.parse_args()


# pick the run folder: by id if given, else most recent with the right csv
if args.run_id is not None:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, f"calibration_{args.run_id}_*"))
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
csv_path = os.path.join(folder, REQUIRE_CSV)
print(f"csv: {csv_path}")


# --step N: detailed view of the Nth valid frame pair (NaN breaks the chain)
if args.step is not None:

    # load all the rows from the csv
    rows = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"rows: {len(rows)}")

    # walk rows, keep only consecutive valid frame pairs (NaN breaks the chain)
    valid_pairs = []
    prev_valid = None
    for row in rows:
        angle = float(row["measured_angle"])
        pixel_x = float(row["measured_x"])
        pixel_y = float(row["measured_y"])
        if math.isnan(angle) or math.isnan(pixel_x) or math.isnan(pixel_y):
            prev_valid = None
            continue
        if prev_valid is None:
            prev_valid = row
            continue
        valid_pairs.append((prev_valid, row))
        prev_valid = row

    # how many rows had a missed detection
    nan_count = sum(
        1 for row in rows if math.isnan(float(row["measured_angle"]))
    )
    print(f"rows: {len(rows)}, NaN: {nan_count}, valid step pairs: {len(valid_pairs)}")

    if args.step < 1 or args.step > len(valid_pairs):
        sys.exit(f"step {args.step} out of range, valid: 1..{len(valid_pairs)}")

    # pull the two rows that define this step
    prev_row, curr_row = valid_pairs[args.step - 1]

    # previous pose (start of the move): apply offset and wrap into [-180, 180]
    prev_angle_raw = float(prev_row["measured_angle"])
    prev_angle = (prev_angle_raw + ARUCO_ANGLE_OFFSET + 180.0) % 360.0 - 180.0
    prev_pixel_x = float(prev_row["measured_x"])
    prev_pixel_y = float(prev_row["measured_y"])

    # current pose (end of the move): same offset + wrap
    curr_angle_raw = float(curr_row["measured_angle"])
    curr_angle = (curr_angle_raw + ARUCO_ANGLE_OFFSET + 180.0) % 360.0 - 180.0
    curr_pixel_x = float(curr_row["measured_x"])
    curr_pixel_y = float(curr_row["measured_y"])

    # the move's commanded ratio + target distance for the title
    ratio = float(curr_row["ratio"])
    target_distance = float(curr_row["target_distance"])

    # actual movement vector in image pixels
    delta_x = curr_pixel_x - prev_pixel_x
    delta_y_image = curr_pixel_y - prev_pixel_y

    # image y axis points down, flip for math convention
    delta_y_math = -delta_y_image

    # distance travelled (pixels)
    distance_px = math.sqrt(delta_x ** 2 + delta_y_math ** 2)

    # angle of the movement vector, math convention (deg, same convention as aruco)
    move_angle = math.degrees(math.atan2(delta_y_math, delta_x))

    # signed angle between movement and previous orientation, wrapped into [-180, 180]
    alpha = (move_angle - prev_angle + 180.0) % 360.0 - 180.0

    # backward: motion is 180° from facing, flip alpha so left/right matches forward
    if target_distance < 0:
        alpha = (180.0 - alpha + 180.0) % 360.0 - 180.0

    # arrow length = commanded distance; subtract sin in y because image y points down
    arrow_length = abs(target_distance) if target_distance != 0 else distance_px

    prev_arrow_x = prev_pixel_x + arrow_length * math.cos(math.radians(prev_angle))
    prev_arrow_y = prev_pixel_y - arrow_length * math.sin(math.radians(prev_angle))

    curr_arrow_x = curr_pixel_x + arrow_length * math.cos(math.radians(curr_angle))
    curr_arrow_y = curr_pixel_y - arrow_length * math.sin(math.radians(curr_angle))


    # plot in image-pixel coordinates with the y axis inverted so it matches the camera frame
    plt.figure()

    # previous orientation arrow
    plt.plot([prev_pixel_x, prev_arrow_x], [prev_pixel_y, prev_arrow_y], color="tab:blue", lw=2,
             label=f"prev orientation ({prev_angle:.1f} deg)")
    plt.annotate("", xy=(prev_arrow_x, prev_arrow_y), xytext=(prev_pixel_x, prev_pixel_y),
                 arrowprops=dict(arrowstyle="->", color="tab:blue", lw=2))

    # current orientation arrow
    plt.plot([curr_pixel_x, curr_arrow_x], [curr_pixel_y, curr_arrow_y], color="tab:orange", lw=2,
             label=f"curr orientation ({curr_angle:.1f} deg)")
    plt.annotate("", xy=(curr_arrow_x, curr_arrow_y), xytext=(curr_pixel_x, curr_pixel_y),
                 arrowprops=dict(arrowstyle="->", color="tab:orange", lw=2))

    # actual movement vector from start to end
    plt.plot([prev_pixel_x, curr_pixel_x], [prev_pixel_y, curr_pixel_y], color="tab:green", lw=2, linestyle="--",
             label=f"movement (distance={distance_px:.1f} px, move_angle={move_angle:.1f} deg)")
    plt.annotate("", xy=(curr_pixel_x, curr_pixel_y), xytext=(prev_pixel_x, prev_pixel_y),
                 arrowprops=dict(arrowstyle="->", color="tab:green", lw=2, linestyle="--"))

    # start and end markers
    plt.scatter(prev_pixel_x, prev_pixel_y, color="tab:red", s=90, zorder=5,
                label=f"start ({prev_pixel_x:.0f}, {prev_pixel_y:.0f})")
    plt.scatter(curr_pixel_x, curr_pixel_y, color="tab:red", s=90, zorder=5,
                label=f"end ({curr_pixel_x:.0f}, {curr_pixel_y:.0f})")

    plt.text(prev_pixel_x, prev_pixel_y, f"  alpha = {alpha:.2f} deg",
             color="black", fontsize=11, va="bottom", ha="left")

    # square axis limits so 1 px in x = 1 px in y both in scale and on screen
    all_x = [prev_pixel_x, curr_pixel_x, prev_arrow_x, curr_arrow_x]
    all_y = [prev_pixel_y, curr_pixel_y, prev_arrow_y, curr_arrow_y]
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


# default view: full ratio calibration regression for both directions
# runs the agent's calibration analysis: regression + saves the plot
fwd_ratio, bwd_ratio = analyse_ratio(folder)

# print the zero-crossing ratios so we can copy/paste them if needed
print(f"ratio_forward = {fwd_ratio}")
print(f"ratio_backward = {bwd_ratio}")

# pops the figure in an interactive window
plt.show()
