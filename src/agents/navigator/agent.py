import datetime
import logging
import os

from spade import agent, behaviour
from spade.message import Message

from common.camera_client import CameraClient
from common.path_motion_executor import PathMotionExecutor
from common.photo_io import save_bytes

from pathfinding.path_command_converter import PathCommandConverter
from pathfinding.pathfinding import compute_path

from agents.navigator.debug import NavigatorDebug
from vision.camera import Camera
from vision.color_detector_image_cropper import ColorDetectorImageCropper
from vision.contour_processor import ContourProcessor
from vision.grid_detector import GridDetector
from vision.robot_grid_localizer import RobotGridLocalizer
from vision.camera import Camera

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHOTOS_DIR = "navigation_photos"


class NavigatorAgent(agent.Agent):
    ENV_PREFIX = "NAVIGATOR"
    class NavigateBehaviour(behaviour.CyclicBehaviour):

        async def run(self):
            logger.info("[WAIT] Waiting for robot request...")
            request = await self.receive(timeout=9999)

            if request is None:
                return

            robot_jid = os.getenv(
                "ROBOT_JID",
                "alphabot21-agent@isc-coordinator2.lan",
            )

            logger.info(f"[REQUEST] From: {request.sender} | Body: {request.body}")
            logger.info(f"[ROBOT JID] {robot_jid}")

            if request.body != "request path":
                logger.warning(f"[WARN] Unknown request: {request.body}")
                return

            logger.info("[START] Navigation requested")

            camera = CameraClient(self)
            converter = PathCommandConverter()

            executor = PathMotionExecutor(
                behaviour=self,
                robot_jid=robot_jid,
                move_distance=200,
                move_pwm=15,
                rotation_pwm=15,
                ratio=1.02,
            )

            bad_grid_count = 0
            max_bad_grid_retries = 5

            localizer = RobotGridLocalizer(angle_offset_deg=0)
            color_detector_image_cropper = ColorDetectorImageCropper()
            contour_processor = ContourProcessor()
            grid_detector = GridDetector()
            cam = Camera()
            debug = NavigatorDebug()


            target_cell = os.getenv("TARGET_CELL", "C1")
            max_steps = int(os.getenv("MAX_STEPS", "50"))

            logger.info(f"[CONFIG] target_cell={target_cell}, max_steps={max_steps}")

            for step in range(max_steps):
                logger.info(f"\n========== STEP {step} ==========")

                img_data = await camera.request_photo("navigator")

                if img_data is None:
                    logger.error("[ERROR] No image received")
                    break

                logger.info(f"[IMAGE] Received {len(img_data)} bytes")

                image = cam.decode_image(img_data)
                

                logger.info(f"[IMAGE] Shape: {image.shape}")

                timestamp = datetime.datetime.now().strftime("%H%M%S")

                await save_bytes(
                    img_data,
                    f"step_{step}_{timestamp}.jpg",
                    PHOTOS_DIR,
                )

                maze = color_detector_image_cropper.detect_and_crop_pink_object(image)

                if maze is None:
                    logger.error("[ERROR] Maze detection failed")
                    break

                logger.info(f"[MAZE] crop_bbox: {maze['crop_bbox']}")

                cropped_mask = maze["cropped_mask"]
                logger.info(f"[MAZE] cropped_mask shape: {cropped_mask.shape}")

                wall_bin = contour_processor.create_wall_binary(cropped_mask)
                wall_clean = contour_processor.clean_wall_mask(wall_bin)

                grid_result = grid_detector.detect_grid_lines(
                    wall_clean,
                    threshold_ratio=0.03,
                    min_gap=15,
                )

                x_lines = grid_result["x_lines"]
                y_lines = grid_result["y_lines"]

                n_rows = len(y_lines) - 1
                n_cols = len(x_lines) - 1

                logger.info(f"[GRID] x_lines: {x_lines}")
                logger.info(f"[GRID] y_lines: {y_lines}")
                logger.info(f"[GRID] rows: {n_rows}, cols: {n_cols}")

                if n_rows != 3 or n_cols != 11:
                    bad_grid_count += 1
                    logger.warning(
                        f"[ERROR] Invalid grid size. Expected 3x11, got {n_rows}x{n_cols}"
                    )

                    if bad_grid_count >= max_bad_grid_retries:
                        logger.error("[ERROR] Too many invalid grid detections")
                        break
                    continue

                robot = localizer.detect_robot_cell(
                    image=image,
                    crop_bbox=maze["crop_bbox"],
                    x_lines=x_lines,
                    y_lines=y_lines,
                )

                debug.save_debug_images(
                    step=step,
                    image=image,
                    maze=maze,
                    wall_clean=wall_clean,
                    grid_detector=grid_detector,
                    x_lines=x_lines,
                    y_lines=y_lines,
                    localizer=localizer,
                    robot=robot,
                )

                if robot is None:
                    logger.error("[ERROR] Robot detection failed: no ArUco pose")
                    break

                current_cell = robot["cell"]
                current_angle = robot["angle_deg"]

                logger.info(
                    f"[ROBOT] cell={current_cell}, "
                    f"corrected_angle={debug.fmt(robot.get('angle_deg'))}, "
                    f"raw_angle={debug.fmt(robot.get('raw_angle_deg'))}, "
                    f"marker_angle={debug.fmt(robot.get('marker_angle_deg'))}, "
                    f"offset={debug.fmt(robot.get('angle_offset_deg'))}, "
                    f"center={robot.get('center')}, "
                    f"rejected={robot.get('rejected_count')}"
                )

                px, py = robot["center"]
                x1, y1, _, _ = maze["crop_bbox"]

                logger.info(
                    f"[ROBOT LOCAL] ({px - x1}, {py - y1}) in crop space"
                )

                if current_cell == target_cell:
                    logger.info("[SUCCESS] Reached destination")

                    reply = Message(to=robot_jid)
                    reply.set_metadata("performative", "response")
                    reply.body = "navigation done"
                    await self.send(reply)
                    return

                path = compute_path(
                    image_data=img_data,
                    start_cell=current_cell,
                    end_cell=target_cell,
                )

                if path is None or len(path) < 2:
                    logger.error("[ERROR] No valid path")
                    break

                logger.info(f"[PATH] full: {path}")
                logger.info(f"[PATH] length: {len(path)}")

                next_step = path[:2]
                logger.info(f"[STEP] next_step: {next_step}")

                commands = converter.path_to_commands(
                    path=next_step,
                    start_angle=current_angle,
                )

                logger.info(f"[COMMANDS] {commands}")

                success = await executor.execute_commands(commands)
                logger.info(f"[EXECUTION] success={success}")

                if not success:
                    logger.error("[ERROR] Execution failed")
                    break

            logger.error("[FAIL] Navigation failed or max steps reached")

            reply = Message(to=robot_jid)
            reply.set_metadata("performative", "response")
            reply.body = "navigation failed"
            await self.send(reply)

    async def setup(self):
        logger.info("[INIT] Navigator ready")
        self.add_behaviour(self.NavigateBehaviour())