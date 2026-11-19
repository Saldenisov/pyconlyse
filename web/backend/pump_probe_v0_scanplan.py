"""Immutable, transport-independent V0 scan intent and calibrated targets."""

import hashlib
import json
import math
from dataclasses import dataclass
from numbers import Real


SCAN_PLAN_SCHEMA = "pyconlyse-v0-scan-plan-v1"
DEFAULT_CALIBRATION_VERSION = "v0-fixed-mm-per-ps-v1"


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _integer(value, name, low, high):
    value = _finite(value, name)
    if not value.is_integer() or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return int(value)


@dataclass(frozen=True)
class ScanPlan:
    delays: tuple[float, ...]
    positions: tuple[float, ...]
    shots_per_point: int
    real_zero_ps: float
    mm_per_ps: float
    stage_min_mm: float
    stage_max_mm: float
    calibration_version: str = DEFAULT_CALIBRATION_VERSION

    def __post_init__(self):
        delays = tuple(_finite(v, f"delay[{i}]") for i, v in enumerate(self.delays))
        positions = tuple(_finite(v, f"position[{i}]") for i, v in enumerate(self.positions))
        if not 2 <= len(delays) <= 400 or len(positions) != len(delays):
            raise ValueError("Scan plan requires 2..400 delay/position pairs")
        zero = _finite(self.real_zero_ps, "real_zero_ps")
        factor = _finite(self.mm_per_ps, "mm_per_ps")
        lower = _finite(self.stage_min_mm, "stage_min_mm")
        upper = _finite(self.stage_max_mm, "stage_max_mm")
        if factor <= 0 or lower >= upper:
            raise ValueError("Calibration factor must be positive and stage limits ordered")
        if not isinstance(self.calibration_version, str) or not self.calibration_version.strip():
            raise ValueError("calibration_version must be a nonempty string")
        for i, (delay, position) in enumerate(zip(delays, positions)):
            expected = -(delay + zero) * factor
            if not math.isfinite(expected) or position != expected:
                raise ValueError(f"Calibrated target[{i}] is invalid")
            if not lower <= position <= upper:
                raise ValueError(f"Calibrated target[{i}]={position} is outside stage limits [{lower}, {upper}]")
        for key, value in (("delays", delays), ("positions", positions),
                           ("shots_per_point", _integer(self.shots_per_point, "shots_per_point", 1, 200)),
                           ("real_zero_ps", zero), ("mm_per_ps", factor),
                           ("stage_min_mm", lower), ("stage_max_mm", upper)):
            object.__setattr__(self, key, value)

    def _payload(self):
        return {
            "schema": SCAN_PLAN_SCHEMA,
            "delays_ps": list(self.delays),
            "positions_mm": list(self.positions),
            "shots_per_point": self.shots_per_point,
            "real_zero_ps": self.real_zero_ps,
            "mm_per_ps": self.mm_per_ps,
            "stage_min_mm": self.stage_min_mm,
            "stage_max_mm": self.stage_max_mm,
            "calibration_version": self.calibration_version,
        }

    @property
    def fingerprint(self):
        data = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {**self._payload(), "fingerprint": self.fingerprint}


def build_scan_plan(settings, mm_per_ps, stage_min_mm, stage_max_mm):
    """Validate every target before a controller mutates state or creates files.

    Explicit delay order and repeats identify distinct rows. This function does
    not clip positions, infer hardware readiness or extend an existing run.
    """
    if not isinstance(settings, dict):
        raise ValueError("Scan settings must be an object")
    custom = settings.get("delay_points_ps")
    if custom is not None and not isinstance(custom, (list, tuple)):
        raise ValueError("delay_points_ps must be an array or null")
    if custom:
        delays = tuple(_finite(v, f"delay_points_ps[{i}]") for i, v in enumerate(custom))
    else:
        count = _integer(settings.get("point_count"), "point_count", 2, 400)
        start = _finite(settings.get("scan_start_ps"), "scan_start_ps")
        step = _finite(settings.get("delay_step_ps"), "delay_step_ps")
        delays = tuple(_finite(start + i * step, f"delay_points_ps[{i}]") for i in range(count))
    zero = _finite(settings.get("real_zero_ps"), "real_zero_ps")
    factor = _finite(mm_per_ps, "mm_per_ps")
    positions = tuple(_finite(-(delay + zero) * factor, f"position[{i}]")
                      for i, delay in enumerate(delays))
    return ScanPlan(delays, positions, settings.get("pulses_per_point"), zero, factor,
                    stage_min_mm, stage_max_mm,
                    settings.get("calibration_version", DEFAULT_CALIBRATION_VERSION))
