"""Saved AI read/mean/calibration graph, with no acquisition or driver access.

Finite, nonempty sample rows are the supported arithmetic domain; empty-row,
nonfinite and floating reduction bit-parity are not claimed. The saved True
literal enables calibration. The False arm is retained as a projection option
for testing that inactive graph, not an available root operator command.
"""

from dataclasses import dataclass
from math import isfinite

from .boundary import (
    NO_ERROR,
    UNSUPPLIED,
    BoundaryCall,
    ErrorCluster,
    MissingValue,
    SampleMatrix,
    ScriptedBoundary,
    SourceVi,
    TaskReference,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_READ_NI6071E.vi",
    "C26AEFFBFC6D48393B2424343877CBC0C0A68239431A0AE63606D5A52F207037",
)
READ_UIDS_BY_CARD = ("1269", "269")
C1_SLOPES = (
    5,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    5,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    4,
    1,
    4,
    4,
    24,
    4,
    1,
    2,
    4,
    4,
    1,
    4,
    4,
    1,
    2,
    1,
    2,
    2,
    2,
    100,
    1,
    1,
    18,
    1,
    1,
    1,
    100,
    1,
    1,
    18,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
)
C1_OFFSETS = (10.0,) + (0.0,) * 7 + (10.0,) + (0.0,) * 55
C2_SLOPES = (
    1.37,
    1.8,
    1.0,
    1.0,
    4.83,
    4.04,
    3.7,
    2.44,
    21.1,
    15.8,
    5.6,
    0.4,
    10.0,
    2.21,
    1.0,
    0.22,
    30.0,
    7.23,
    1.6,
    3.0,
    3.0,
    1.0,
    1.0,
    1.92307692,
    30.0,
    1.0,
    1.6,
    3.0,
    1.0,
    1.0,
    1.92307692,
    1.92307692,
    1.92307692,
    2.04980842,
    -10.213,
    -2.75,
    10.213,
    10.213,
    2.0,
    1.0,
    2.061657,
    4.14728682,
    10.213,
    2.75,
    10.213,
    2.0,
    2.0,
    9.0,
    9.0,
    20.0,
    1.0,
    1.0,
    1.0,
    1.0,
    1.0,
    1.0,
    20.0,
    1.0,
    1.0,
    1.0,
    1.0,
    1.0,
    1.0,
    1.0,
)
C2_OFFSETS = (
    (0.0,) * 23
    + (0.1403846,)
    + (0.0,) * 6
    + (0.1403846,) * 3
    + (0.13733716, 51.065, 27.5)
    + (0.0,) * 4
    + (0.12576107, 0.41058139, -51.065)
    + (0.0,) * 21
)


def merge_card_errors(c1: ErrorCluster, c2: ErrorCluster) -> ErrorCluster:
    """First error, otherwise first warning: saved input order is C1 then C2.

    Default Merge Errors mode only, not modern Retain All Errors. See NI:
    https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/merge-errors.html
    """
    require_error(c1)
    require_error(c2)
    for error in (c1, c2):
        if error.status:
            return error
    for error in (c1, c2):
        if error.code != 0:
            return error
    return NO_ERROR


def project_card_samples(
    samples: SampleMatrix,
    *,
    card: int,
    calibrated: bool = True,
) -> tuple[float, ...]:
    """For N=64 auto-indexed channels -> mean -> optional slope+offset."""
    if type(samples) is not SampleMatrix or type(card) is not int or card not in (1, 2):
        raise TypeError("SampleMatrix and card 1 or 2 required")
    if type(calibrated) is not bool:
        raise TypeError("calibrated projection selector requires bool")
    means = []
    for row in samples.rows[:64]:
        if not row or any(not isfinite(value) for value in row):
            raise ValueError("Python-only guard: nonempty finite sample rows required")
        mean = sum(row) / len(row)
        if not isfinite(mean):
            raise ValueError("Python-only guard: finite mean required")
        means.append(mean)
    if not calibrated:
        return tuple(means)
    slopes, offsets = (C1_SLOPES, C1_OFFSETS) if card == 1 else (C2_SLOPES, C2_OFFSETS)
    projected = tuple(
        m * slope + offset for m, slope, offset in zip(means, slopes, offsets)
    )
    if any(not isfinite(value) for value in projected):
        raise ValueError("Python-only guard: finite calibrated result required")
    return projected


@dataclass(frozen=True)
class AnalogReadResult:
    source: SourceVi
    banks: tuple[tuple[float, ...] | MissingValue, ...]
    read_errors: tuple[ErrorCluster, ErrorCluster]
    error_out: ErrorCluster
    calls: tuple[BoundaryCall, ...]


def read(
    boundary: ScriptedBoundary,
    *,
    tasks: tuple[TaskReference, TaskReference],
    samples_per_channel: int,
    error_in: ErrorCluster,
) -> AnalogReadResult:
    """Two independent Read branches and unconditional saved calibration.

    Calls are listed C1 then C2 as one admissible schedule; no source edge
    orders them. Both receive the same input error, not each other's result.
    Read task/sample-count returns and Mean error outputs are unused. Data
    returned with an error is still projected; missing data remains unknown.
    """
    require_boundary(boundary)
    require_error(error_in)
    if (
        type(tasks) is not tuple
        or len(tasks) != 2
        or any(type(t) is not TaskReference for t in tasks)
    ):
        raise TypeError("two simulation task references required: C1, C2")
    if (
        type(samples_per_channel) is not int
        or not -(2**31) <= samples_per_channel < 2**31
    ):
        raise ValueError("Python-only guard: I32 sample count required")
    start = len(boundary.calls)
    returns = []
    for card, uid, task in zip((1, 2), READ_UIDS_BY_CARD, tasks):
        returns.append(
            boundary.invoke(
                SOURCE,
                uid,
                "3",
                "read_analog_2d_dbl_many_channels_many_samples",
                task_in=task,
                error_in=error_in,
                card=card,
                samples_per_channel=samples_per_channel,
                timeout_seconds=1.0,
                polymorphic_selector="08",
                independent_peer_uid=READ_UIDS_BY_CARD[2 - card],
            )
        )
    banks = tuple(
        UNSUPPLIED
        if result.data is UNSUPPLIED
        else project_card_samples(result.data, card=card)
        for card, result in zip((1, 2), returns)
    )
    errors = (returns[0].error, returns[1].error)
    return AnalogReadResult(
        SOURCE, banks, errors, merge_card_errors(*errors), boundary.calls[start:]
    )
