"""
    Central place to switch coordinator host and robot number.
    Composes the recipient JIDs (robot, camera) and provides
    a helper to build any agent JID from its local-part.
"""

import os

COORDINATOR_HOST = os.getenv("COORDINATOR_HOST", "isc-coordinator2.lan")
ROBOT_NUM = os.getenv("ROBOT_NUM", "1")

ARUCO_IDS = {"1": 12, "3": 8}
ARUCO_ID = ARUCO_IDS[ROBOT_NUM]

# Per-robot angle offset compensating for the marker mounting direction.
# Robot 1's marker is glued 180 deg flipped from robot 3's.
ARUCO_ANGLE_OFFSETS = {"1": 180.0, "3": 0.0}
ARUCO_ANGLE_OFFSET = ARUCO_ANGLE_OFFSETS[ROBOT_NUM]

ROBOT_JID = f"motion-alphabot2{ROBOT_NUM}-agent@{COORDINATOR_HOST}"
CAMERA_JID = f"camera_agent@{COORDINATOR_HOST}"
LOGGER_JID = f"logger@{COORDINATOR_HOST}"
NAVIGATOR_JID = os.getenv("NAVIGATOR_JID", f"navigator@{COORDINATOR_HOST}")


def agent_jid(user: str) -> str:
    return f"{user}@{COORDINATOR_HOST}"