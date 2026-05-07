"""
    Central place to switch coordinator host and robot number.
    Composes the recipient JIDs (robot, camera) and provides
    a helper to build any agent JID from its local-part.
"""

import os

PAUSE_TIME = 5

COORDINATOR_HOST = os.getenv("XMPP_DOMAIN", "isc-coordinator2.lan")
ROBOT_NUM = os.getenv("ROBOT_NUM", "1")
ROBOT_FILTRE = f"alphabot2{ROBOT_NUM}-agent"

ARUCO_IDS = {"1": 12, "3": 8}
ARUCO_ID = ARUCO_IDS[ROBOT_NUM]

# Per-robot target marker. The navigator detects this marker at the start of a
# run and uses the cell where it lies as the goal, instead of a hardcoded one.
TARGET_ARUCO_IDS = {"1": 1, "3": 1}
TARGET_ARUCO_ID = TARGET_ARUCO_IDS[ROBOT_NUM]

# Per-robot angle offset compensating for the marker mounting direction.
# Robot 1's marker is glued 180 deg flipped from robot 3's.
ARUCO_ANGLE_OFFSETS = {"1": 180.0, "3": 0.0}
ARUCO_ANGLE_OFFSET = ARUCO_ANGLE_OFFSETS[ROBOT_NUM]

# Agent on the AlphaBot2-Pi
ROBOT_JID = f"motion-{ROBOT_FILTRE}@{COORDINATOR_HOST}"
SENSORS_JID = f"sensors-{ROBOT_FILTRE}@{COORDINATOR_HOST}"
PICAMERA_JID = f"camera-{ROBOT_FILTRE}@'{COORDINATOR_HOST}"
NAVIGATOR_JID = f"navigator-{ROBOT_FILTRE}@{COORDINATOR_HOST}"
CALIBRATOR_JID = f"calibrator-{ROBOT_FILTRE}@{COORDINATOR_HOST}"
RECEIVER_JID = f"camera-receiver-{ROBOT_FILTRE}@{COORDINATOR_HOST}"

# Agent extern to the AlphaBot2-Pi
TELEMETRY_JID = f"telemetry@{COORDINATOR_HOST}"
CAMERA_JID = os.getenv("CAMERA_JID", f"camera_agent@{COORDINATOR_HOST}")
TIMEKEEPER_JID = os.getenv("TIMEKEEPER_JID", f"timekeeper@{COORDINATOR_HOST}")
UR_JID = os.getenv("UR_JID", f"ur-agent@{COORDINATOR_HOST}")

def agent_jid(user: str) -> str:
    return f"{user}@{COORDINATOR_HOST}"