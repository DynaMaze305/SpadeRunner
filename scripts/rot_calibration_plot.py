"""Plots for linear regression models on the rotation
    Co-author: ClaudeAI on all matplotlib graphs
"""

import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CALIBRATION_DIR = os.path.join(ROOT, "calibration_photos")

# share the same fit + plot as the calibrator agent
sys.path.insert(0, os.path.join(ROOT, "src"))
from agents.calibrator.rotation_analysis import analyse_rotation


REQUIRE_CSV = "rotation.csv"


parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="calibration run id; defaults to most recent run with rotation.csv")
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

# runs the agent's calibration analysis: linear regression + saves the plot
pos_slope, pos_intercept, neg_slope, neg_intercept = analyse_rotation(folder)

# print the fit so we can copy/paste the numbers if needed
print(f"CW  fit: y = {pos_slope:.2f} * x + {pos_intercept:.2f}")
print(f"CCW fit: y = {neg_slope:.2f} * x + {neg_intercept:.2f}")

# pops the figure in an interactive window
plt.show()
