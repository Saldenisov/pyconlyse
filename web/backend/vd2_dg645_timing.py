"""Operator-supplied VD2 timing; no interpolation, gate writes or slot saves."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
from pathlib import Path
import re


CONFIG_PATH = Path(__file__).resolve().parents[1] / "pump_probe" / "config" / "vd2_streak_dg645_recall9.json"
_TIME_UNITS = {"ns": Decimal("1e-9"), "us": Decimal("1e-6"), "ms": Decimal("1e-3")}
# DG645 delay resolution is 5 ps. Never use a relative float tolerance here.
_READBACK_TOLERANCE_S = Decimal("5e-12")


def _range_seconds(value):
    normalized = str(value).strip().lower().replace("µ", "u").replace("μ", "u")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ns|us|ms)", normalized)
    if not match:
        raise ValueError(f"Time range needs explicit ns/us/ms units: {value}")
    return Decimal(match[1]) * _TIME_UNITS[match[2]]


@dataclass(frozen=True)
class TimingProfile:
    time_range: str
    delay_a_ms: Decimal
    delay_e_ms: Decimal

    @property
    def commands(self):
        return tuple(
            f"DLAY {channel},0,{format(delay_ms * Decimal('0.001'), 'f')}"
            for channel, delay_ms in ((2, self.delay_a_ms), (6, self.delay_e_ms))
        )

    def as_dict(self):
        return {"time_range": self.time_range, "reference": "T0", "delay_unit": "ms",
                "delay_a": str(self.delay_a_ms), "delay_e": str(self.delay_e_ms),
                "commands": list(self.commands), "gates": "unchanged"}


@lru_cache(maxsize=1)
def _profiles():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["timing_calibration"]
    if config["reference"] != "T0" or config["delay_unit"] != "ms":
        raise ValueError("VD2 calibration must use T0 reference and millisecond delays")
    delay_a = Decimal(config["delay_a"])
    result = {}
    for label, value in config["delay_e_by_time_range"].items():
        delay_e = Decimal(value)
        if not all(delay.is_finite() and delay >= 0 for delay in (delay_a, delay_e)):
            raise ValueError("VD2 calibrated delays must be finite and non-negative")
        key = _range_seconds(label)
        if key in result:
            raise ValueError(f"Duplicate calibrated time range: {label}")
        result[key] = TimingProfile(label, delay_a, delay_e)
    return result


def timing_for_range(value):
    try:
        return _profiles()[_range_seconds(value)]
    except KeyError:
        raise ValueError(f"No VD2 DG645 timing calibration for {value}; no interpolation permitted") from None


def verify_timing(dg645, profile):
    for channel, expected_ms in ((2, profile.delay_a_ms), (6, profile.delay_e_ms)):
        raw = str(dg645.command_inout("scpi_query", f"DLAY? {channel}")).strip()
        try:
            reference, seconds = raw.split(",")
            measured = Decimal(seconds.strip())
            expected = expected_ms * Decimal("0.001")
            valid = (int(reference.strip()) == 0 and measured.is_finite()
                     and abs(measured - expected) <= _READBACK_TOLERANCE_S)
        except (ValueError, InvalidOperation):
            valid = False
        if not valid:
            raise RuntimeError(f"DG645 channel {channel} timing unverified: {raw}; expected T0 + {expected_ms} ms")


def apply_timing(dg645, profile):
    # Writes are sent once. A timeout can mean an accepted write; never replay
    # it or restore a guessed old setting. A partial failure remains explicit.
    for command in profile.commands:
        dg645.command_inout("scpi_write", command)
    if str(dg645.command_inout("scpi_query", "*OPC?")).strip() not in {"1", "+1"}:
        raise RuntimeError("DG645 did not confirm timing command completion")
    verify_timing(dg645, profile)
