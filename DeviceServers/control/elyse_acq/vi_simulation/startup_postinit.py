"""One allowed frame-33052 schedule, with independent software resets.

No serial client exists here. TPG Initialize is a supplied external boundary,
not a reconstructed protocol yet. Returned opaque session tokens are fixtures.
"""

from dataclasses import dataclass

from .boundary import (
    NO_ERROR,
    UNSUPPLIED,
    UNWIRED,
    BoundaryCall,
    ErrorCluster,
    MissingValue,
    SampleClockInputs,
    ScriptedBoundary,
    TaskReference,
    require_boundary,
)
from .init_ni6220 import initialize
from .runtime_io import SOURCE

RESETS = ((46, False), (45, False), (44, (False,) * 77), (36, (False,) * 29))
DISABLED_UI = ("79089", "40722", "70708", "8957", "11783")
TPG_BRANCHES = (("126853", "COM1", 52, "10951"), ("123241", "COM2", 51, "73977"))


@dataclass(frozen=True)
class PostInitResult:
    local_assignments: tuple[tuple[int, object], ...]
    ui_assignments: tuple[tuple[str, str, int], ...]
    branch_errors: tuple[ErrorCluster, ...]
    calls: tuple[BoundaryCall, ...]


def record_postinit(
    boundary: ScriptedBoundary, *, clock: SampleClockInputs
) -> PostInitResult:
    """NI6220 then COM1 then COM2 is a fixture schedule, not a source total order.

    Every branch has an unwired error input and its own handler. Reset/UI
    assignments are independent of returned errors. Handler outputs are unused.
    Missing serial sessions remain unknown; no successful initialization or
    hardware acknowledgment is inferred from the software reset values.
    """
    require_boundary(boundary)
    if type(clock) is not SampleClockInputs:
        raise TypeError("explicit NI6220 rate/count snapshot required")
    start = len(boundary.calls)
    ni = initialize(boundary, clock=clock, error_in=NO_ERROR)
    assignments = [(56, ni.tasks[0])]
    errors = [ni.internal_error]
    boundary.invoke(
        SOURCE,
        "49978",
        "33052",
        "simple_error_handler",
        error_in=ni.internal_error,
        mode_connection="unwired",
        outputs_connection="unused",
    )
    for uid, resource, index, handler in TPG_BRANCHES:
        returned = boundary.invoke(
            SOURCE,
            uid,
            "33052",
            "TPG300.Initialize",
            resource=resource,
            baud_selector=4,
            error_in=UNWIRED,
        )
        session: TaskReference | MissingValue = (
            UNSUPPLIED if returned.task is UNWIRED else returned.task
        )
        assignments.append((index, session))
        errors.append(returned.error)
        boundary.invoke(
            SOURCE,
            handler,
            "33052",
            "simple_error_handler",
            error_in=returned.error,
            mode_connection="unwired",
            outputs_connection="unused",
        )
    return PostInitResult(
        tuple(assignments) + RESETS,
        tuple((uid, "DisabledEnum", 2) for uid in DISABLED_UI),
        tuple(errors),
        boundary.calls[start:],
    )
