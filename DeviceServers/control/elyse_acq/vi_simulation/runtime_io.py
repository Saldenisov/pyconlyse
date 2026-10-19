"""Root runtime frame 0 at supplied in-memory boundaries, never hardware.

Explicit snapshots do not imply atomic LabVIEW local-variable acquisition.
Unknown short-array padding stays unresolved instead of becoming False/zero.
"""

from dataclasses import dataclass

from .boundary import (
    NO_ERROR,
    UNSUPPLIED,
    BoundaryCall,
    MissingValue,
    ScriptedBoundary,
    SourceVi,
    TaskReference,
    require_boundary,
)
from .read_ni6071e import AnalogReadResult, read
from .rw_dio96 import DigitalExchangeResult, DigitalOutputBanks, exchange
from .write_ni6703 import AoWriterResult, LogicalAoBanks, write

SOURCE = SourceVi(
    "0_ACQ_ELYSE.vi",
    "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
)
AI_SIZES = (64, 64)
DI_SIZES = (56, 64, 56)
DO_SIZES = (40, 32, 40)


@dataclass(frozen=True)
class ReadbackCluster:
    """Known prefix plus saved size; no invented tail or retained prior value."""

    size: int
    known_prefix: tuple | MissingValue

    @property
    def complete(self):
        return type(self.known_prefix) is tuple and len(self.known_prefix) == self.size

    @property
    def values(self):
        return self.known_prefix if self.complete else UNSUPPLIED


def project_readback_cluster(data, size):
    if type(size) is not int or size <= 0:
        raise TypeError("positive saved cluster size required")
    if data is UNSUPPLIED:
        return ReadbackCluster(size, UNSUPPLIED)
    if type(data) is not tuple:
        raise TypeError("immutable tuple and positive saved cluster size required")
    return ReadbackCluster(size, data[:size])


@dataclass(frozen=True)
class RuntimeIoResult:
    analog: AnalogReadResult
    digital: DigitalExchangeResult
    output: AoWriterResult
    local_assignments: tuple[tuple[int, ReadbackCluster], ...]
    calls: tuple[BoundaryCall, ...]


def record_runtime_io(
    boundary: ScriptedBoundary,
    *,
    analog_tasks: tuple[TaskReference, TaskReference],
    digital_tasks: tuple[TaskReference, ...],
    output_tasks: tuple[TaskReference, ...],
    digital_outputs: DigitalOutputBanks,
    analog_outputs: LogicalAoBanks,
) -> RuntimeIoResult:
    """Read AI -> exchange DI/DO -> write AO -> abstract error-handler call.

    This is one admissible trace, not the complete runtime loop or stop logic.
    Error wires order helper calls; data assignments/conversions are not gated
    by error status. The handler's unwired mode and unused returns are explicit.
    """
    return _record_io_frame(
        boundary,
        analog_tasks=analog_tasks,
        digital_tasks=digital_tasks,
        output_tasks=output_tasks,
        digital_outputs=digital_outputs,
        analog_outputs=analog_outputs,
        frame_uid="7386",
        handler_uid="11701",
    )


def _record_io_frame(
    boundary,
    *,
    analog_tasks,
    digital_tasks,
    output_tasks,
    digital_outputs,
    analog_outputs,
    frame_uid,
    handler_uid,
):
    """Shared mechanics for three independently source-checked caller frames."""
    if (frame_uid, handler_uid) not in (
        ("7386", "11701"),
        ("25990", "16070"),
        ("41713", "55822"),
    ):
        raise ValueError("only the three saved I/O caller frames are supported")
    require_boundary(boundary)
    if (
        type(digital_outputs) is not DigitalOutputBanks
        or tuple(len(bank) for bank in digital_outputs.values) != DO_SIZES
    ):
        raise ValueError("root DO cluster sizes require C3/C4/C5 = 40/32/40")
    if type(analog_outputs) is not LogicalAoBanks:
        raise TypeError("root AO snapshots require LogicalAoBanks")
    # Validate all task snapshots before recording any requests.
    for tasks, size in ((analog_tasks, 2), (digital_tasks, 6), (output_tasks, 4)):
        if (
            type(tasks) is not tuple
            or len(tasks) != size
            or any(type(task) is not TaskReference for task in tasks)
        ):
            raise TypeError("root task snapshot shape/type changed")
    start = len(boundary.calls)
    analog = read(
        boundary, tasks=analog_tasks, samples_per_channel=1000, error_in=NO_ERROR
    )
    digital = exchange(
        boundary, digital_outputs, tasks=digital_tasks, error_in=analog.error_out
    )
    output = write(
        boundary, analog_outputs, tasks=output_tasks, error_in=digital.error_out
    )
    boundary.invoke(
        SOURCE,
        handler_uid,
        frame_uid,
        "simple_error_handler",
        error_in=output.error_out,
        mode_connection="unwired",
        outputs_connection="unused",
    )
    assignments = tuple(
        (field, project_readback_cluster(data, size))
        for fields, banks, sizes in (
            ((19, 20), analog.banks, AI_SIZES),
            ((18, 16, 14), digital.di_banks, DI_SIZES),
        )
        for field, data, size in zip(fields, banks, sizes)
    )
    return RuntimeIoResult(analog, digital, output, assignments, boundary.calls[start:])
