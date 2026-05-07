import math
import os
import sys
import unittest
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from agents.navigator.emulation import SimulationState  # noqa: E402
from agents.navigator.localization import RobotPose  # noqa: E402


@dataclass
class FakeFrame:
    x_lines: list
    y_lines: list
    maze: dict


def make_frame(crop_x1=0, crop_y1=0, cell_w=60, cell_h=60, cols=3, rows=3):
    x_lines = [i * cell_w for i in range(cols + 1)]
    y_lines = [i * cell_h for i in range(rows + 1)]
    return FakeFrame(
        x_lines=x_lines,
        y_lines=y_lines,
        maze={"crop_bbox": (crop_x1, crop_y1, crop_x1 + cols * cell_w,
                            crop_y1 + rows * cell_h)},
    )


def make_pose(cx, cy, angle_deg=0.0, cell="A1"):
    return RobotPose(
        cell=cell,
        angle_deg=angle_deg,
        raw_angle_deg=angle_deg,
        center=(cx, cy),
        pose={},
        corners=None,
        ids=None,
    )


class TestSimulationState(unittest.TestCase):

    def setUp(self):
        self.mm_per_px = 2.96

    def test_pure_rotate_does_not_move_center(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=0.0), make_frame())
        sim.apply_rotate(45.0)
        pose = sim.current_pose()
        self.assertEqual(pose.center, (100, 100))
        self.assertAlmostEqual(pose.angle_deg, 45.0, places=4)

    def test_pure_move_east_at_zero_deg(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=0.0), make_frame())
        sim.apply_move(296.0)  # 296 mm / 2.96 = 100 px exactly
        pose = sim.current_pose()
        self.assertEqual(pose.center, (200, 100))
        self.assertAlmostEqual(pose.angle_deg, 0.0, places=4)

    def test_pure_move_north_at_90_deg(self):
        # angle=+90 in atan2(-dy, dx) convention means heading is image-up,
        # so cy must DECREASE.
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=90.0), make_frame())
        sim.apply_move(296.0)
        pose = sim.current_pose()
        self.assertEqual(pose.center, (100, 0))
        self.assertAlmostEqual(pose.angle_deg, 90.0, places=4)

    def test_pure_move_west_at_180_deg(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=180.0), make_frame())
        sim.apply_move(296.0)
        pose = sim.current_pose()
        # 180 normalises to -180 the way the orchestrator wraps; either is
        # valid - what matters is +x stops, -x starts.
        self.assertEqual(pose.center, (0, 100))

    def test_pure_move_south_at_minus90_deg(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=-90.0), make_frame())
        sim.apply_move(296.0)
        pose = sim.current_pose()
        self.assertEqual(pose.center, (100, 200))

    def test_combined_rotate_then_move(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=0.0), make_frame())
        sim.apply_rotate(90.0)  # now facing +90 (image-up)
        sim.apply_move(296.0)
        pose = sim.current_pose()
        self.assertEqual(pose.center, (100, 0))
        self.assertAlmostEqual(pose.angle_deg, 90.0, places=4)

    def test_angle_normalises_into_180_range(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=170.0), make_frame())
        sim.apply_rotate(40.0)  # 170 + 40 = 210 -> wraps to -150
        pose = sim.current_pose()
        self.assertAlmostEqual(pose.angle_deg, -150.0, places=4)

    def test_angle_normalises_below_minus_180(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(100, 100, angle_deg=-170.0), make_frame())
        sim.apply_rotate(-40.0)  # -170 + -40 = -210 -> wraps to 150
        pose = sim.current_pose()
        self.assertAlmostEqual(pose.angle_deg, 150.0, places=4)

    def test_cell_label_recomputes_from_pixel_position(self):
        # 3x3 grid, 60 px per cell. (30, 30) -> A1, (90, 30) -> A2, (90, 90) -> B2.
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(30, 30, angle_deg=0.0, cell="A1"), make_frame())
        self.assertEqual(sim.current_pose().cell, "A1")

        # Move east one cell width: 60 px = 60 * 2.96 = 177.6 mm.
        sim.apply_move(60.0 * self.mm_per_px)
        self.assertEqual(sim.current_pose().cell, "A2")

        # Rotate to face -90 (image-down) and move south one cell.
        sim.apply_rotate(-90.0)
        sim.apply_move(60.0 * self.mm_per_px)
        self.assertEqual(sim.current_pose().cell, "B2")

    def test_cell_is_none_when_outside_grid(self):
        sim = SimulationState(self.mm_per_px)
        sim.seed(make_pose(30, 30, angle_deg=180.0, cell="A1"), make_frame())
        # Step way west, off the grid.
        sim.apply_move(1000.0)
        self.assertIsNone(sim.current_pose().cell)

    def test_seed_respects_crop_bbox_offset(self):
        # Robot center is in full-image coords; grid lines are in local-crop
        # coords. With a crop of (50, 70), full-image (80, 100) -> local (30, 30) -> A1.
        sim = SimulationState(self.mm_per_px)
        frame = make_frame(crop_x1=50, crop_y1=70)
        sim.seed(make_pose(80, 100, angle_deg=0.0, cell="A1"), frame)
        self.assertEqual(sim.current_pose().cell, "A1")
        self.assertEqual(sim.current_pose().center, (80, 100))

    def test_is_seeded_flag(self):
        sim = SimulationState(self.mm_per_px)
        self.assertFalse(sim.is_seeded())
        sim.seed(make_pose(100, 100), make_frame())
        self.assertTrue(sim.is_seeded())


if __name__ == "__main__":
    unittest.main()
