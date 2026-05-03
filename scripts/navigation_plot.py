"""Plot for navigation runs (per-step rotation + distance errors, L2 scores)
    Co-author: ClaudeAI on all matplotlib graphs
"""

import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAVIGATION_DIR = os.path.join(ROOT, "navigation_photos")

sys.path.insert(0, os.path.join(ROOT, "src"))
from agents.navigator.navigation_analysis import analyse_navigation


REQUIRE_CSV = "navigation.csv"


parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="navigation run id; defaults to most recent run with navigation.csv")
args = parser.parse_args()


if args.run_id is not None:
    folders = glob.glob(os.path.join(NAVIGATION_DIR, f"navigation_{args.run_id}*"))
else:
    folders = sorted(
        glob.glob(os.path.join(NAVIGATION_DIR, "navigation_*")),
        key=os.path.getmtime,
        reverse=True,
    )

candidates = [path for path in folders if os.path.exists(os.path.join(path, REQUIRE_CSV))]
if not candidates:
    sys.exit(f"no navigation folder containing {REQUIRE_CSV} in {NAVIGATION_DIR}/")
folder = candidates[0]


print(f"folder: {folder}")

rotation_score, distance_score, drift_score = analyse_navigation(folder)
print(f"rotation L2 = {rotation_score:.2f} deg")
print(f"distance L2 = {distance_score:.2f} mm")
print(f"drift L2 = {drift_score:.2f} deg")

plt.show()
