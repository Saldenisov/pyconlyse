"""Pure V0 scan-setting validation; explicit delay order is authoritative."""

import math


MIN_DELAY_POINTS = 2
MAX_DELAY_POINTS = 400
_AXIS_FIELDS = ("point_count", "scan_start_ps", "delay_step_ps", "scan_span_ps")


def preview_kinetics(delay):
    """V0's existing synthetic preview formula, with a finite-result boundary."""
    try:
        value = 0.18 * (1 - math.exp(-(delay + 30) / 42))
    except OverflowError:
        raise ValueError("Delay is outside the numeric range of the V0 preview") from None
    if not math.isfinite(value):
        raise ValueError("Delay is outside the numeric range of the V0 preview")
    return value


def _finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _integer(value, name, low, high):
    number = _finite_number(value, name)
    if not number.is_integer():
        raise ValueError(f"{name} must be an integer")
    return max(low, min(high, int(number)))


def _explicit_delays(values):
    if not isinstance(values, list):
        raise ValueError("delay_points_ps must be an array or null")
    if not MIN_DELAY_POINTS <= len(values) <= MAX_DELAY_POINTS:
        raise ValueError(f"delay_points_ps must contain {MIN_DELAY_POINTS}..{MAX_DELAY_POINTS} points")
    delays = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"delay_points_ps[{index}] must be a finite number")
        delays.append(_finite_number(value, f"delay_points_ps[{index}]"))
    return delays


def resolve_scan_settings(current, payload):
    """Return a validated copy before controller or hardware state changes.

    A nonempty explicit array overrides linear-axis fields in the same payload.
    Null/[] selects generated mode. Without an explicit array, scalar axis edits
    select generated mode; unrelated updates preserve the existing custom axis.
    Scalar counts retain V0 clamps, but fractional counts are rejected.
    """
    if not isinstance(payload, dict):
        raise ValueError("Scan configuration must be an object")
    settings = dict(current)
    if "delay_points_ps" in payload:
        values = payload["delay_points_ps"]
        if values is None or (isinstance(values, list) and not values):
            settings["delay_points_ps"] = None
        else:
            settings["delay_points_ps"] = _explicit_delays(values)
    elif any(key in payload for key in _AXIS_FIELDS[:3]):
        settings["delay_points_ps"] = None

    custom = settings.get("delay_points_ps")
    if custom:
        delays = _explicit_delays(custom)
        settings.update(
            delay_points_ps=delays,
            point_count=len(delays),
            scan_start_ps=delays[0],
            delay_step_ps=_finite_number(delays[1] - delays[0], "delay_step_ps"),
            scan_span_ps=_finite_number(delays[-1] - delays[0], "scan_span_ps"),
        )
    else:
        settings["point_count"] = _integer(
            payload.get("point_count", settings["point_count"]),
            "point_count", MIN_DELAY_POINTS, MAX_DELAY_POINTS,
        )
        for key in ("scan_start_ps", "delay_step_ps"):
            settings[key] = _finite_number(payload.get(key, settings[key]), key)
        if "scan_span_ps" in payload:
            _finite_number(payload["scan_span_ps"], "scan_span_ps")
        count = settings["point_count"]
        start = settings["scan_start_ps"]
        step = settings["delay_step_ps"]
        delays = [_finite_number(start + index * step, f"delay_points_ps[{index}]")
                  for index in range(count)]
        settings["scan_span_ps"] = _finite_number((count - 1) * step, "scan_span_ps")

    settings["pulses_per_point"] = _integer(
        payload.get("pulses_per_point", settings["pulses_per_point"]),
        "pulses_per_point", 1, 200,
    )
    settings["real_zero_ps"] = _finite_number(
        payload.get("real_zero_ps", settings["real_zero_ps"]), "real_zero_ps",
    )
    # configure resets the synthetic preview even in Tango mode. Check its
    # numeric domain before committing settings; this is not optical calibration.
    for index, delay in enumerate(delays):
        _finite_number(delay + settings["real_zero_ps"], f"delay_points_ps[{index}] + real_zero_ps")
        try:
            preview_kinetics(delay)
        except ValueError as exc:
            raise ValueError(f"delay_points_ps[{index}]: {exc}") from None
    return settings
