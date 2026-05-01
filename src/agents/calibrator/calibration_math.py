"""pure math helpers used by the calibrator agent and the plot scripts"""

import math

import numpy as np


# pixel <-> mm conversion fixed by the maze cell width: 200 mm spans ~67.5 px
MM_PER_PIXEL = 2.96


# fits a line y = slope*x + intercept and returns (slope, intercept, R^2)
def linear_fit(x_values, y_values):
    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(y_values, dtype=float)

    # numpy does the fit
    slope, intercept = np.polyfit(x_arr, y_arr, 1)

    # computes R^2 by hand since polyfit doesn't return it
    predicted_y = slope * x_arr + intercept
    ss_residual = np.sum((y_arr - predicted_y) ** 2)
    ss_total = np.sum((y_arr - np.mean(y_arr)) ** 2)
    r_squared = 1.0 - ss_residual / ss_total if ss_total > 0 else 0.0

    return float(slope), float(intercept), float(r_squared)

# x value where the line y = slope*x + intercept crosses 0
def zero_crossing(slope, intercept):
    if slope == 0:
        return None
    return -intercept / slope

# L2 norm of a list of error values
def l2_score(values):
    if not values:
        return 0.0
    values_arr = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(values_arr ** 2)))


# test the ratio csv and returns (forward, backward) lists of (ratio, alpha)
# alpha = perpendicular deviation angle, + left / - right, same sign both ways
def ratio_points(rows, angle_offset_deg=0.0):
    forward = []
    backward = []
    prev_angle = None
    prev_pixel_x = None
    prev_pixel_y = None

    for row in rows:
        angle_raw = float(row["measured_angle"])

        # apply offset and wrap into [-180, 180]
        angle = (angle_raw + angle_offset_deg + 180.0) % 360.0 - 180.0
        pixel_x = float(row["measured_x"])
        pixel_y = float(row["measured_y"])
        ratio = float(row["ratio"])
        target_distance = float(row["target_distance"])

        # bad detection -> reset the chain so the next pair isn't bogus
        if math.isnan(angle) or math.isnan(pixel_x) or math.isnan(pixel_y):
            prev_angle = None
            prev_pixel_x = None
            prev_pixel_y = None
            continue

        # first row of a chain has no previous, just remember it and move on
        if prev_angle is None:
            prev_angle = angle
            prev_pixel_x = pixel_x
            prev_pixel_y = pixel_y
            continue

        # movement vector in image pixels (image y points down -> flip to math)
        delta_x = pixel_x - prev_pixel_x
        delta_y_math = -(pixel_y - prev_pixel_y)

        # angle of the movement vector, math convention (deg)
        move_angle = math.degrees(math.atan2(delta_y_math, delta_x))

        # alpha = how far the actual move strayed from the bot's facing
        alpha = (move_angle - prev_angle + 180.0) % 360.0 - 180.0

        # backward moves expect a 180 deg motion direction, so flip alpha
        # to keep the left/right sign convention consistent with forward
        if target_distance < 0:
            alpha = (180.0 - alpha + 180.0) % 360.0 - 180.0

        # bucket by move direction
        if target_distance > 0:
            forward.append((ratio, alpha))
        elif target_distance < 0:
            backward.append((ratio, alpha))

        prev_angle = angle
        prev_pixel_x = pixel_x
        prev_pixel_y = pixel_y

    return forward, backward


# walks the rotation csv and returns (positive, negative) lists of
# (duration, angle_diff). sorted by |duration| and unwrapped past +/-180
def rotation_points(rows):
    positive = []
    negative = []
    prev_angle = None

    for row in rows:
        angle = float(row["measured_angle"])
        duration_str = (row.get("duration") or "").strip()

        # duration may be empty for the initial reference frame
        try:
            duration = float(duration_str) if duration_str else 0.0
        except ValueError:
            duration = 0.0

        # bad detection -> reset chain
        if math.isnan(angle):
            prev_angle = None
            continue

        if prev_angle is None:
            prev_angle = angle
            continue

        # signed rotation between two consecutive frames, wrapped in [-180, 180]
        diff = (angle - prev_angle + 180.0) % 360.0 - 180.0
        prev_angle = angle

        # bucket by rotation direction
        if duration > 0:
            positive.append((duration, diff))
        elif duration < 0:
            negative.append((duration, diff))

    # sort by ascending |duration| so np.unwrap can detect 360 deg jumps
    positive.sort(key=lambda pair: pair[0])
    negative.sort(key=lambda pair: -pair[0])

    # unwraps so a 270° rotation doesn't show up as -90°
    if positive:
        diffs_deg = [diff_deg for duration, diff_deg in positive]
        unwrapped_deg = np.degrees(np.unwrap(np.radians(diffs_deg)))
        positive = [(duration, float(new_diff))
                    for (duration, _old_diff), new_diff in zip(positive, unwrapped_deg)]

    if negative:
        diffs_deg = [diff_deg for duration, diff_deg in negative]
        unwrapped_deg = np.degrees(np.unwrap(np.radians(diffs_deg)))
        negative = [(duration, float(new_diff))
                    for (duration, _old_diff), new_diff in zip(negative, unwrapped_deg)]

    return positive, negative


# walks the distance csv and returns (forward, backward) lists of
# (duration, distance_px) where distance is the pixel displacement
def distance_points(rows):
    forward = []
    backward = []
    prev_pixel_x = None
    prev_pixel_y = None

    for row in rows:
        pixel_x = float(row["measured_x"])
        pixel_y = float(row["measured_y"])
        duration_str = (row.get("duration") or "").strip()

        try:
            duration = float(duration_str) if duration_str else 0.0
        except ValueError:
            duration = 0.0

        # bad detection -> reset chain
        if math.isnan(pixel_x) or math.isnan(pixel_y):
            prev_pixel_x = None
            prev_pixel_y = None
            continue

        if prev_pixel_x is None:
            prev_pixel_x = pixel_x
            prev_pixel_y = pixel_y
            continue

        # pixel displacement between this row and the previous one
        delta_x = pixel_x - prev_pixel_x
        delta_y = pixel_y - prev_pixel_y
        distance_px = math.sqrt(delta_x ** 2 + delta_y ** 2)

        # bucket by move direction
        if duration > 0:
            forward.append((duration, distance_px))
        elif duration < 0:
            backward.append((duration, distance_px))

        prev_pixel_x = pixel_x
        prev_pixel_y = pixel_y

    return forward, backward


# walks the verify_rotation csv and groups every measured rotation diff
# by its target angle. unwraps each diff into the half-circle matching the
# target's sign (so a +90 target whose diff crossed +/-180 still shows positive)
def rotation_diffs_by_target(rows, angle_offset_deg=0.0):
    groups = {}
    prev_angle = None

    for row in rows:
        angle_raw = float(row["measured_angle"])

        # apply per-robot offset and wrap into [-180, 180]
        angle = (angle_raw + angle_offset_deg + 180.0) % 360.0 - 180.0
        target = float(row["target_angle"])

        # bad detection -> reset chain
        if math.isnan(angle):
            prev_angle = None
            continue

        if prev_angle is None:
            prev_angle = angle
            continue

        # signed rotation between two consecutive frames
        diff = (angle - prev_angle + 180.0) % 360.0 - 180.0

        # unwrap into the half-circle matching the target sign
        if target > 0 and diff < 0:
            diff += 360.0
        elif target < 0 and diff > 0:
            diff -= 360.0
        prev_angle = angle

        # the initial reference row has target = 0, skip it
        if target == 0:
            continue

        # group all diffs that share the same target
        groups.setdefault(target, []).append(diff)

    return groups


# walks the verify_distance csv and returns the per-move distance error
# error = |target_distance| - actual_mm. skips the initial reference frame.
def distance_errors(rows):
    errors = []
    prev_pixel_x = None
    prev_pixel_y = None

    for row in rows:
        pixel_x = float(row["measured_x"])
        pixel_y = float(row["measured_y"])
        target_distance = float(row["target_distance"])

        # bad detection -> reset chain
        if math.isnan(pixel_x) or math.isnan(pixel_y):
            prev_pixel_x = None
            prev_pixel_y = None
            continue

        if prev_pixel_x is None:
            prev_pixel_x = pixel_x
            prev_pixel_y = pixel_y
            continue

        # pixel displacement -> mm
        delta_x = pixel_x - prev_pixel_x
        delta_y = pixel_y - prev_pixel_y
        actual_px = math.sqrt(delta_x ** 2 + delta_y ** 2)
        actual_mm = actual_px * MM_PER_PIXEL

        # error = how far short / over the bot landed
        if target_distance != 0.0:
            error = abs(target_distance) - actual_mm
            errors.append(error)

        prev_pixel_x = pixel_x
        prev_pixel_y = pixel_y

    return errors
