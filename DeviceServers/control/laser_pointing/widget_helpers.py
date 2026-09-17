"""Pure helpers shared by the LaserPointing desktop widgets."""

import re


STANDA_STEP_SIZES = (0.5, 1.0, 2.0, 5.0, 20.0, 50.0, 100.0)


def _camera_number(value):
    match = re.search(r"cam(?:era)?[_-]?(\d+)", str(value or ""), re.IGNORECASE)
    return int(match.group(1)) if match else None


def is_other_optical_role(role, camera_device=""):
    """Return whether a controller role belongs in the Other optics tab."""

    normalized = str(role or "").lower().replace(" ", "").replace("-", "_")
    if "diaphragm" in normalized or any(
        marker in normalized
        for marker in ("halfwaveplate", "half_wave_plate", "lambda")
    ):
        return True

    if "shutter" not in normalized and "flipper" not in normalized:
        return False
    role_number = next(
        (int(value) for value in re.findall(r"\d+", normalized)), None
    )
    camera_number = _camera_number(camera_device)
    if camera_number == 2:
        return role_number in (1, 2)
    return role_number is not None and role_number == camera_number


def format_optical_status_value(role, value):
    """Format live optical readback for the compact component-status panel."""

    raw_value = getattr(value, "magnitude", value)
    normalized = str(role or "").lower().replace(" ", "").replace("-", "_")
    if "shutter" in normalized or "flipper" in normalized:
        endpoint = str(raw_value or "").strip().upper()
        if endpoint == "UP_BLOCKED":
            return "UP · BLOCKED"
        if endpoint == "DOWN_CLEAR":
            return "DOWN · CLEAR"
        if endpoint == "RIGHT":
            return "DOWN"
        if endpoint == "LEFT":
            return "UP · BLOCKED"
        if endpoint in {"BETWEEN", "CONFLICT", "UNKNOWN"}:
            return endpoint

    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        return "—"

    if "shutter" in normalized or "flipper" in normalized:
        if abs(numeric + 1.0) <= 0.2:
            return "−1"
        if abs(numeric - 1.0) <= 0.2:
            return "+1"
        return "UNKNOWN"

    if "diaphragm" in normalized or any(
        marker in normalized
        for marker in ("halfwaveplate", "half_wave_plate", "lambda")
    ):
        return f"{numeric:g}%"

    return f"{numeric:g}"


def manual_alignment_motion_enabled(
    pair_ready,
    point_application_busy=False,
    pair_initialization_busy=False,
    automatic_search_running=False,
):
    """Keep ready manual axes available except while a controller owns motion."""

    return bool(pair_ready) and not any(
        (
            point_application_busy,
            pair_initialization_busy,
            automatic_search_running,
        )
    )
