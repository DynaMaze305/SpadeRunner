"""Capture one photo from camera_agent, run the maze pipeline once,
    and dump the detected layout to a JSON so the navigator can replay it later.

Usage:
    python scripts/save_maze.py                       # mazes/maze_<timestamp>.json
    python scripts/save_maze.py mazes/lab.json        # custom path

Requires XMPP_PASSWORD (and XMPP_DOMAIN) in the environment.
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from spade import agent, behaviour

from agents.navigator.config import NavigatorConfig
from agents.navigator.vision_pipeline import MazeVisionPipeline, VisionError
from common.camera_client import CameraClient
from common.config import COORDINATOR_HOST


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description="snapshot the maze layout to a json")
parser.add_argument("output", nargs="?", default=None,
                    help="output json path; defaults to mazes/maze_<timestamp>.json")
args = parser.parse_args()


# pick the output path: explicit or timestamped default
if args.output:
    output_path = args.output
else:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(ROOT, "mazes", f"maze_{timestamp}.json")
os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)


# minimal one-shot agent that connects, fetches one photo, then stops
class SnapshotAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.snapshot = self.Snapshot()
        self.image_bytes = None

    async def setup(self):
        self.add_behaviour(self.snapshot)

    class Snapshot(behaviour.OneShotBehaviour):
        async def run(self):
            camera = CameraClient(self)
            self.agent.image_bytes = await camera.request_photo("save-maze")


async def main():
    user = os.getenv("CALIBRATOR_REQUEST_USER", "calibrator_request")
    password = os.getenv("XMPP_PASSWORD")
    if not password:
        sys.exit("XMPP_PASSWORD not set — source .env first or run inside the docker container")

    jid = f"{user}@{COORDINATOR_HOST}"
    logger.info(f"connecting as {jid} to fetch one camera photo")

    snapshot_agent = SnapshotAgent(jid, password)
    await snapshot_agent.start(auto_register=True)
    await snapshot_agent.snapshot.join()
    image_bytes = snapshot_agent.image_bytes
    await snapshot_agent.stop()

    if image_bytes is None:
        sys.exit("no photo received from camera_agent")
    logger.info(f"got photo: {len(image_bytes)} bytes")

    # Run the vision pipeline once and validate the grid size
    cfg = NavigatorConfig.from_env()
    vision = MazeVisionPipeline(
        threshold_ratio=cfg.grid_threshold_ratio,
        min_gap=cfg.grid_min_gap,
        obstacles_enabled=False,
    )
    frame_or_err = vision.analyze(image_bytes)
    if isinstance(frame_or_err, VisionError):
        sys.exit(f"vision pipeline failed: {frame_or_err.value}")

    frame = frame_or_err
    if frame.n_rows != cfg.expected_rows or frame.n_cols != cfg.expected_cols:
        sys.exit(
            f"grid size mismatch: expected {cfg.expected_rows}x{cfg.expected_cols}, "
            f"got {frame.n_rows}x{frame.n_cols} — refusing to save a bad maze"
        )

    # Dump the structure (everything the navigator needs to skip detection)
    saved = {
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "crop_bbox": list(frame.maze["crop_bbox"]),
        "x_lines": list(frame.x_lines),
        "y_lines": list(frame.y_lines),
        "n_rows": frame.n_rows,
        "n_cols": frame.n_cols,
        "grid_walls": frame.grid_walls,
    }
    with open(output_path, "w") as f:
        json.dump(saved, f, indent=2)
    logger.info(f"saved maze to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
