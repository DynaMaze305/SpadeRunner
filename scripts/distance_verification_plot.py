"""Plot for distance verification (per-trial mm error + L2 score)
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

# share the same scoring + plot as the calibrator agent
sys.path.insert(0, os.path.join(ROOT, "src"))
from agents.calibrator.distance_analysis import analyse_distance_verify


REQUIRE_CSV = "verify_distance.csv"


parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="calibration run id; defaults to most recent run with verify_distance.csv")
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

# runs the agent's verify analysis: per-move mm error + L2 score + plot
score = analyse_distance_verify(folder)
print(f"L2 = {score:.2f} mm")

# pops the figure in an interactive window
plt.show()