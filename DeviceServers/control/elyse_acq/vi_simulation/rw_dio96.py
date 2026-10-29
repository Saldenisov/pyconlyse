"""Original DIO96 read/publication/write/error flow at supplied boundaries.

No driver, hardware adapter or transport is accepted. Input/output array
lengths are preserved, not inferred from card names. Missing read fixtures
remain UNSUPPLIED, never an invented all-False measurement. Tuple/bool guards
are Python-only representation checks, not legacy error or interlock logic.
"""

from dataclasses import dataclass

from .boundary import (
    UNSUPPLIED,
    BoundaryCall,
    ErrorCluster,
    MissingValue,
    ScriptedBoundary,
    SourceVi,
    TaskReference,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_RW_DIO96.vi",
    "6F46D4E9551442DC32C0BA3C769341B6AB8D0A467372B5154485078A4606F5BC",
)
READ_UIDS = ("232", "667", "1028")
WRITE_UIDS = ("2840", "38", "742")


@dataclass(frozen=True)
class DigitalOutputBanks:
    """C3/C4/C5 outgoing Boolean arrays, not physical contact states."""

    values: tuple[tuple[bool, ...], ...]

    def __post_init__(self):
        if (
            type(self.values) is not tuple
            or len(self.values) != 3
            or any(
                type(bank) is not tuple or any(type(bit) is not bool for bit in bank)
                for bank in self.values
            )
        ):
            raise ValueError("three immutable Boolean tuple banks required: C3/C4/C5")


@dataclass(frozen=True)
class DigitalExchangeResult:
    source: SourceVi
    di_banks: tuple[tuple[bool, ...] | MissingValue, ...]
    do_banks: DigitalOutputBanks
    error_out: ErrorCluster
    calls: tuple[BoundaryCall, ...]


def exchange(
    boundary: ScriptedBoundary,
    outputs: DigitalOutputBanks,
    *,
    tasks: tuple[TaskReference, ...],
    error_in: ErrorCluster,
) -> DigitalExchangeResult:
    """Record Read C3/C4/C5 then Write C3/C4/C5, linked by returned errors.

    Supplied Read data is assigned even when its returned error status is True.
    No data-validity/freshness, authorization, debounce, retry or rollback
    rule is silently added. Task/count returns have no saved consumer.
    """
    require_boundary(boundary)
    require_error(error_in)
    if type(outputs) is not DigitalOutputBanks:
        raise TypeError("outputs require DigitalOutputBanks")
    if (
        type(tasks) is not tuple
        or len(tasks) != 6
        or any(type(t) is not TaskReference for t in tasks)
    ):
        raise TypeError("six simulation tasks required: DI C3/C4/C5 then DO C3/C4/C5")
    start, error, inputs = len(boundary.calls), error_in, []
    for card, uid, task in zip(range(3, 6), READ_UIDS, tasks[:3]):
        result = boundary.invoke(
            SOURCE,
            uid,
            "1684",
            "read_digital_1d_bool_one_channel_one_sample",
            task_in=task,
            error_in=error,
            card=card,
            polymorphic_selector="0F",
            timeout_connection="unwired",
        )
        if result.data is not UNSUPPLIED and (
            type(result.data) is not tuple
            or any(type(bit) is not bool for bit in result.data)
        ):
            raise ValueError(
                "Python-only guard: DIO Read fixture requires Boolean tuple"
            )
        inputs.append(result.data)
        error = result.error
    for card, uid, task, data in zip(
        range(3, 6), WRITE_UIDS, tasks[3:], outputs.values
    ):
        result = boundary.invoke(
            SOURCE,
            uid,
            "1684",
            "write_digital_1d_bool_one_channel_one_sample",
            task_in=task,
            error_in=error,
            card=card,
            data=data,
            polymorphic_selector="0E",
            auto_start=True,
            timeout_connection="unwired",
        )
        error = result.error
    return DigitalExchangeResult(
        SOURCE, tuple(inputs), outputs, error, boundary.calls[start:]
    )
