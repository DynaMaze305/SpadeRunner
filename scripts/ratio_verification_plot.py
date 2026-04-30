"""Plot for ratio verification (per-trial alpha + L2 score)
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
from agents.calibrator.ratio_analysis import analyse_ratio_verify


REQUIRE_CSV = "verify_ratio.csv"


parser = argparse.ArgumentParser()
parser.add_argument("run_id", nargs="?", default=None,
                    help="calibration run id; defaults to most recent run with verify_ratio.csv")
args = parser.parse_args()


# pick the run folder by run id (if given), otherwise the most recent folder
# that actually contains verify_ratio.csv (so we skip calibration-only folders)
if args.run_id is not None:
    folders = glob.glob(os.path.join(CALIBRATION_DIR, f"calibration_{args.run_id}_*"))
else:
    folders = sorted(
        glob.glob(os.path.join(CALIBRATION_DIR, "calibration_*")),
        key=os.path.getmtime,
        reverse=True,
    )

candidates = [f for f in folders if os.path.exists(os.path.join(f, REQUIRE_CSV))]
if not candidates:
    sys.exit(f"no calibration folder containing {REQUIRE_CSV} in {CALIBRATION_DIR}/")
folder = candidates[0]


print(f"folder: {folder}")

score = analyse_ratio_verify(folder)
print(f"L2 = {score:.2f} deg")

plt.show()
