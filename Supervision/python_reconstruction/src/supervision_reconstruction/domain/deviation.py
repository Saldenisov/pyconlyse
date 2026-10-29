"""Command/readback deviation semantics from the two Ecart_lu_ecr VIs.

The diagrams copy their input cluster then assign an ``orange`` indicator for
each visible channel when ``abs(command - readback) > threshold``.  They do
not establish the external controller names or threshold values; callers must
supply both rather than relying on invented mappings.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Sequence, Union


DIRECT_LINE_CHANNELS = (
    "dipole_1",
    "focale",
    "phase_hf_laser",
    "h1",
    "v1",
    "h2",
    "v2",
    "triplet_1_1",
    "triplet_1_2",
    "h3",
    "v3",
)

DEVIATED_LINE_CHANNELS = (
    "q1",
    "q2",
    "t2_1",
    "t2_2",
    "h4",
    "v4",
    "dipole_2",
    "h5",
    "v5",
)

Thresholds = Union[float, Mapping[str, float]]


@dataclass(frozen=True)
class DeviationResult:
    """Per-channel absolute differences and resulting legacy orange flags."""

    absolute_differences: Mapping[str, float]
    orange_flags: Mapping[str, bool]


def _threshold_for(channel: str, threshold: Thresholds) -> float:
    if isinstance(threshold, Mapping):
        return threshold[channel]
    return threshold


def _finite_nonnegative_threshold(channel: str, threshold: Thresholds) -> float:
    value = _threshold_for(channel, threshold)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"threshold for {channel!r} must be finite and non-negative")
    return value


def _finite_measurement(channel: str, name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} for {channel!r} must be finite")
    return value


def compute_deviation_flags(
    channels: Sequence[str],
    commands: Mapping[str, float],
    readbacks: Mapping[str, float],
    threshold: Thresholds,
) -> DeviationResult:
    """Return the exact strict-greater-than flag rule seen in the diagrams.

    Missing command, readback, or per-channel threshold values raise
    ``KeyError``.  Failing closed is intentional: silently treating an
    unresolved control field as non-orange would alter a safety-relevant UI
    signal.
    """

    differences = {
        channel: abs(
            _finite_measurement(channel, "command", commands[channel])
            - _finite_measurement(channel, "readback", readbacks[channel])
        )
        for channel in channels
    }
    return DeviationResult(
        absolute_differences=differences,
        orange_flags={
            channel: difference > _finite_nonnegative_threshold(channel, threshold)
            for channel, difference in differences.items()
        },
    )
