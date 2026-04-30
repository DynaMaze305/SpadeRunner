"""
    Central place to switch coordinator host and robot number.
    Composes the recipient JIDs (robot, camera) and provides
    a helper to build any agent JID from its local-part.
"""

import os

COORDINATOR_HOST = os.getenv("XMPP_DOMAIN", "isc-coordinator2.lan")
ROBOT_NUM = os.getenv("ROBOT_NUM", "1")

ARUCO_IDS = {"1": 12, "3": 8}
ARUCO_ID = ARUCO_IDS[ROBOT_NUM]

# Per-robot angle offset compensating for the marker mounting direction.
# Robot 1's marker is glued 180 deg flipped from robot 3's.
ARUCO_ANGLE_OFFSETS = {"1": 180.0, "3": 0.0}
ARUCO_ANGLE_OFFSET = ARUCO_ANGLE_OFFSETS[ROBOT_NUM]

# Agent on the AlphaBot2-Pi
ROBOT_JID = f"motion-alphabot2{ROBOT_NUM}-agent@{COORDINATOR_HOST}"
SENSORS_JID = f"sensors-alphabot2{ROBOT_NUM}-agent@{COORDINATOR_HOST}"
PICAMERA_JID = f"camera-alphabot2{ROBOT_NUM}-agent@'{COORDINATOR_HOST}"
NAVIGATOR_JID = f"navigator@{COORDINATOR_HOST}"

# Agent extern to the AlphaBot2-Pi
TELEMETRY_JID = f"telemetry@{COORDINATOR_HOST}"
CAMERA_JID = f"camera_agent@{COORDINATOR_HOST}"

def agent_jid(user: str) -> str:
    return f"{user}@{COORDINATOR_HOST}"