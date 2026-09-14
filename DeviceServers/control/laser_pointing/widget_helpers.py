"""Pure helpers shared by the LaserPointing desktop widgets."""

import re


STANDA_STEP_SIZES = (0.5, 1.0, 2.0, 5.0)


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
    return role_number is not None and role_number == _camera_number(camera_device)
