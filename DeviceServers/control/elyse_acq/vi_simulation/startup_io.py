"""Initial card exchange from saved frame 25990, never a hardware initializer."""

from .boundary import ScriptedBoundary, TaskReference
from .runtime_io import RuntimeIoResult, _record_io_frame
from .rw_dio96 import DigitalOutputBanks
from .write_ni6703 import LogicalAoBanks


def record_initial_io(
    boundary: ScriptedBoundary,
    *,
    analog_tasks: tuple[TaskReference, TaskReference],
    digital_tasks: tuple[TaskReference, ...],
    output_tasks: tuple[TaskReference, ...],
    digital_outputs: DigitalOutputBanks,
    analog_outputs: LogicalAoBanks,
) -> RuntimeIoResult:
    """AI -> DIO -> AO -> handler, with explicitly supplied task/bank snapshots.

    Public AI error input is unwired in this frame. NO_ERROR is the fixture
    assumption already used by the reader model, not a hardware observation.
    The original pilot error is not a selector or error input here. No external
    state, earlier initializer success, rollback or full startup is implied.
    """
    return _record_io_frame(
        boundary,
        analog_tasks=analog_tasks,
        digital_tasks=digital_tasks,
        output_tasks=output_tasks,
        digital_outputs=digital_outputs,
        analog_outputs=analog_outputs,
        frame_uid="25990",
        handler_uid="16070",
    )
