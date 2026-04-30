"""Pure math helpers shared by the calibrator agent and the plot scripts."""

import math

import numpy as np


# pixel <-> mm conversion fixed by the maze cell width: 200 mm spans ~67.5 px
MM_PER_PIXEL = 2.96


def linear_fit(xs, ys):
    xs_arr = np.asarray(xs, dtype=float)
    ys_arr = np.asarray(ys, dtype=float)
    slope, intercept = np.polyfit(xs_arr, ys_arr, 1)
    pred = slope * xs_arr + intercept
    ss_res = np.sum((ys_arr - pred) ** 2)
    ss_tot = np.sum((ys_arr - np.mean(ys_arr)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), float(r2)


def zero_crossing(slope, intercept):
    if slope == 0:
        return None
    return -intercept / slope


def l2_score(values):
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(arr ** 2)))


# walks the calibration csv rows and returns (forward, backward) lists of
# (ratio, alpha) pairs where alpha is the perpendicular deviation angle
# (left = +, right = -) consistent across forward and backward moves.
def ratio_points(rows, angle_offset_deg=0.0):
    forward = []
    backward = []
    prev_angle = None
    prev_x = None
    prev_y = None

    for row in rows:
        angle_raw = float(row["measured_angle"])
        angle = (angle_raw + angle_offset_deg + 180.0) % 360.0 - 180.0
        x = float(row["measured_x"])
        y = float(row["measured_y"])
        ratio = float(row["ratio"])
        target_distance = float(row["target_distance"])

        if math.isnan(angle) or math.isnan(x) or math.isnan(y):
            prev_angle = None
            prev_x = None
            prev_y = None
            continue

        if prev_angle is None:
            prev_angle = angle
            prev_x = x
            prev_y = y
            continue

        # movement vector in image pixels (image y points down -> flip to math)
        dx = x - prev_x
        dy_math = -(y - prev_y)

        # angle of the movement vector, math convention (deg)
        move_angle = math.degrees(math.atan2(dy_math, dx))

        # signed angle between movement and previous orientation, in [-180, 180]
        alpha = (move_angle - prev_angle + 180.0) % 360.0 - 180.0

        # backward moves expect a 180 deg motion direction, so flip alpha
        # to keep the left/right sign convention consistent with forward
        if target_distance < 0:
            alpha = (180.0 - alpha + 180.0) % 360.0 - 180.0

        if target_distance > 0:
            forward.append((ratio, alpha))
        elif target_distance < 0:
            backward.append((ratio, alpha))

        prev_angle = angle
        prev_x = x
        prev_y = y

    return forward, backward


# walks the calibration csv rows and returns (positive, negative) lists of
# (duration, angle_diff) pairs. each list is sorted by ascending magnitude
# of duration and unwrapped past the +/-180 deg boundary.
def rotation_points(rows):
    positive = []
    negative = []
    prev_angle = None

    for row in rows:
        angle = float(row["measured_angle"])
        duration_str = (row.get("duration") or "").strip()
        try:
            duration = float(duration_str) if duration_str else 0.0
        except ValueError:
            duration = 0.0

        if math.isnan(angle):
            prev_angle = None
            continue

        if prev_angle is None:
            prev_angle = angle
            continue

        # signed rotation between two consecutive frames, wrapped in [-180, 180]
        diff = (angle - prev_angle + 180.0) % 360.0 - 180.0
        prev_angle = angle

        if duration > 0:
            positive.append((duration, diff))
        elif duration < 0:
            negative.append((duration, diff))

    # sort by ascending magnitude so np.unwrap can detect 360 deg jumps
    positive.sort(key=lambda p: p[0])
    negative.sort(key=lambda p: -p[0])

    if positive:
        diffs_deg = [d for _, d in positive]
        diffs_rad = np.radians(diffs_deg)
        unwrapped_rad = np.unwrap(diffs_rad)
        unwrapped_deg = np.degrees(unwrapped_rad)
        positive = [(t, float(d)) for (t, _), d in zip(positive, unwrapped_deg)]

    if negative:
        diffs_deg = [d for _, d in negative]
        diffs_rad = np.radians(diffs_deg)
        unwrapped_rad = np.unwrap(diffs_rad)
        unwrapped_deg = np.degrees(unwrapped_rad)
        negative = [(t, float(d)) for (t, _), d in zip(negative, unwrapped_deg)]

    return positive, negative


# walks the calibration csv rows and returns (forward, backward) lists of
# (duration, distance_px) pairs. distance is the euclidean displacement in pixels.
def distance_points(rows):
    forward = []
    backward = []
    prev_x = None
    prev_y = None

    for row in rows:
        x = float(row["measured_x"])
        y = float(row["measured_y"])
        duration_str = (row.get("duration") or "").strip()
        try:
            duration = float(duration_str) if duration_str else 0.0
        except ValueError:
            duration = 0.0

        if math.isnan(x) or math.isnan(y):
            prev_x = None
            prev_y = None
            continue

        if prev_x is None:
            prev_x = x
            prev_y = y
            continue

        dx = x - prev_x
        dy = y - prev_y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        if duration > 0:
            forward.append((duration, distance))
        elif duration < 0:
            backward.append((duration, distance))

        prev_x = x
        prev_y = y

    return forward, backward


# verification helper: walks the verify_rotation csv and groups every measured
# rotation diff by its target angle. unwraps the diff into the half-circle that
# matches the target sign so a +90 target whose measurement crossed the +/-180
# boundary still shows up as a positive diff (and vice-versa).
def rotation_diffs_by_target(rows, angle_offset_deg=0.0):
    groups = {}
    prev_angle = None

    for row in rows:
        angle_raw = float(row["measured_angle"])
        angle = (angle_raw + angle_offset_deg + 180.0) % 360.0 - 180.0
        target = float(row["target_angle"])

        if math.isnan(angle):
            prev_angle = None
            continue

        if prev_angle is None:
            prev_angle = angle
            continue

        diff = (angle - prev_angle + 180.0) % 360.0 - 180.0
        if target > 0 and diff < 0:
            diff += 360.0
        elif target < 0 and diff > 0:
            diff -= 360.0
        prev_angle = angle

        # the initial reference row has target = 0, skip it
        if target == 0:
            continue
        groups.setdefault(target, []).append(diff)

    return groups


# verification helper: per-move distance error = |target_distance| - actual_mm.
# only includes rows whose target_distance is non-zero (skips the initial frame).
def distance_errors(rows):
    errors = []
    prev_x = None
    prev_y = None

    for row in rows:
        x = float(row["measured_x"])
        y = float(row["measured_y"])
        target_distance = float(row["target_distance"])

        if math.isnan(x) or math.isnan(y):
            prev_x = None
            prev_y = None
            continue

        if prev_x is None:
            prev_x = x
            prev_y = y
            continue

        dx = x - prev_x
        dy = y - prev_y
        actual_px = math.sqrt(dx ** 2 + dy ** 2)
        actual_mm = actual_px * MM_PER_PIXEL

        if target_distance != 0.0:
            error = abs(target_distance) - actual_mm
            errors.append(error)

        prev_x = x
        prev_y = y

    return errors