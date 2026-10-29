"""Saved NI6703 conversion/error wiring; records requests, never writes NI.

Only four ten-element, finite banks are supported. Shape, finiteness and
acos-domain rejection are Python representation guards, not proved LabVIEW
failure behavior. No clamp, permission gate, physical state or rollback is
introduced. Standard DAQmx behavior belongs to supplied external returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, isfinite

from .boundary import (
    BoundaryCall,
    ErrorCluster,
    ScriptedBoundary,
    SourceVi,
    TaskReference,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_WRITE_NI6703.vi",
    "5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D",
)
WRITE_UIDS = ("592", "1696", "1989", "1200")  # Error-wire order C6 -> C9.
SLOPES = (
    (1.0, 1.0, 0.5, 0.5, 1.0, 0.5, 1.0, 0.5, 1.0, 0.5),
    (0.25, 0.25, 0.25, 0.25, 0.25, 0.0416666, 0.25, 0.25, 0.25, 0.25),
    (1.0, 0.2, 0.2, 1.0, 1.0, 0.0277777777, 0.025, 0.1111111111, 0.1111111111, 1.0),
    (0.5, 0.25, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
)
C8_OFFSETS = (0.0, -2.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class LogicalAoBanks:
    """Explicit input data ordered C6, C7, C8, C9; zero-based channel index."""

    values: tuple[tuple[float, ...], ...]

    def __post_init__(self):
        if type(self.values) is not tuple or len(self.values) != 4:
            raise ValueError("four tuple banks required in C6/C7/C8/C9 order")
        for bank in self.values:
            if type(bank) is not tuple or len(bank) != 10:
                raise ValueError("each logical bank requires ten tuple elements")
            if any(type(x) not in (int, float) or not isfinite(x) for x in bank):
                raise ValueError("logical banks require finite numeric elements")


@dataclass(frozen=True)
class AoWriterResult:
    source: SourceVi
    logical: LogicalAoBanks
    requested_voltages: tuple[tuple[float, ...], ...]
    error_out: ErrorCluster
    calls: tuple[BoundaryCall, ...]


def project_requested_voltages(
    logical: LogicalAoBanks,
) -> tuple[tuple[float, ...], ...]:
    """Convert logical values; output is not a voltage measurement or permission."""
    if type(logical) is not LogicalAoBanks:
        raise TypeError("logical input requires LogicalAoBanks")
    banks = [
        [x * slope for x, slope in zip(bank, slopes)]
        for bank, slopes in zip(logical.values, SLOPES)
    ]
    banks[2] = [x + offset for x, offset in zip(banks[2], C8_OFFSETS)]
    x = banks[2][3]
    try:
        banks[2][3] = (
            (8 * 10**-9) * (x**4)
            - ((7 * 10**-7) * x**3)
            - ((3 * 10**-5) * x**2)
            - (0.0181 * x)
            + 2.1775
        )
        # The acos result feeds the cubic, not the original attenuation input.
        argument = 10 ** (-banks[2][4] / 20)
        if not -1 <= argument <= 1:
            raise ValueError("Python-only guard: C8[4] outside real acos domain")
        x = 57.3 * acos(argument)
        banks[2][4] = (-4 * 10**-6) * x**3 + 0.0006 * x**2 - 0.0624 * x + 3.8587
    except OverflowError as exc:
        raise ValueError("Python-only guard: conversion overflow") from exc
    if any(not isfinite(x) for bank in banks for x in bank):
        raise ValueError("Python-only guard: converted values must be finite")
    return tuple(tuple(bank) for bank in banks)


def write(
    boundary: ScriptedBoundary,
    logical: LogicalAoBanks,
    *,
    tasks: tuple[TaskReference, ...],
    error_in: ErrorCluster,
) -> AoWriterResult:
    """Record all four source call sites with each preceding returned error.

    A true incoming/returned error does not remove downstream graph nodes.
    Recording them does not establish that DAQmx would execute a physical
    write. Each task comes from its original input-cluster field; returned
    tasks and samples-written values have no consumer in the saved helper.
    """
    require_boundary(boundary)
    require_error(error_in)
    if (
        type(tasks) is not tuple
        or len(tasks) != 4
        or any(type(t) is not TaskReference for t in tasks)
    ):
        raise TypeError("four simulation task references required in C6/C7/C8/C9 order")
    voltages = project_requested_voltages(logical)
    start = len(boundary.calls)
    error = error_in
    for card, uid, task, data in zip(range(6, 10), WRITE_UIDS, tasks, voltages):
        returned = boundary.invoke(
            SOURCE,
            uid,
            "3",
            "write_analog_1d_dbl_n_channels_one_sample",
            task_in=task,
            error_in=error,
            card=card,
            data=data,
            auto_start=True,
            timeout_s=20.0,
        )
        error = returned.error
    return AoWriterResult(SOURCE, logical, voltages, error, boundary.calls[start:])
