"""Saved startup command/status facets, in-memory only, not full initialization.

PSP/error-handler results are supplied fixtures. No socket, driver, hardware
adapter or original executable startup procedure is imported or invoked.
"""

from dataclasses import dataclass
from typing import Mapping

from .boundary import (
    UNWIRED,
    BoundaryCall,
    ErrorCluster,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)
from .runtime_publication import URI_PREFIX

SOURCE = SourceVi(
    "0_ACQ_ELYSE.vi",
    "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
)
STARTUP_COMMANDS = (
    (9, (0.0,) * 10),
    (10, (0.0,) * 10),
    (11, (0.0, 21.0, 27.9, 0.0, 0.0, 0.0, 360.0, 0.0, 0.0, 0.0)),
    (12, (6.5, 0.0, 4.755, 4.755, 2.126, 2.126, 2.126, 0.0, 0.0, 0.0)),
    (17, tuple(i in (1, 4) for i in range(40))),
    (15, tuple(i in (1, 4, 6, 8, 17, 19) for i in range(32))),
    (13, tuple(i == 33 for i in range(40))),
)
COMMAND_PUBLICATIONS = (
    ("16580", 9, "C6NI6703"),
    ("16609", 10, "C7NI6703"),
    ("16616", 11, "C8NI6703"),
    ("16615", 12, "C9NI6703"),
    ("426", 17, "C3_OUT_DIO96"),
    ("20071", 15, "C4_OUT_DIO96"),
    ("15613", 13, "C5_OUT_DIO96"),
)
STATUS_PUBLICATIONS = (
    ("34463", 36, "DPS"),
    ("34480", 44, "EPS"),
    ("27194", 7, "VDM-A"),
)


@dataclass(frozen=True)
class StartupPublicationResult:
    local_assignments: tuple[tuple[int, tuple], ...]
    final_error: ErrorCluster
    calls: tuple[BoundaryCall, ...]
    independent_wait_ms: int | None = None


def publish_commands(boundary: ScriptedBoundary) -> StartupPublicationResult:
    """One trace with no concurrent local modifications and returning handler.

    Local writes in frame 14803 are independent, not a serial/atomic bank commit.
    Frame 24611 reads those locals; external mutations are not modeled here.
    Final PSP error reaches the handler, not the raw pilot-status tunnel.
    """
    require_boundary(boundary)
    start = len(boundary.calls)
    snapshots = dict(STARTUP_COMMANDS)
    error = UNWIRED
    for uid, index, name in COMMAND_PUBLICATIONS:
        error = boundary.invoke(
            SOURCE,
            uid,
            "24611",
            "PSP.Write",
            error_in=error,
            uri=URI_PREFIX + name,
            local_index=index,
            data=snapshots[index],
        ).error
    boundary.invoke(
        SOURCE,
        "26161",
        "24611",
        "simple_error_handler",
        error_in=error,
        mode_connection="unwired",
        outputs_connection="unused",
    )
    return StartupPublicationResult(STARTUP_COMMANDS, error, boundary.calls[start:])


def publish_status(
    boundary: ScriptedBoundary,
    *,
    raw_pilot_error: ErrorCluster,
    local_snapshots: Mapping[int, tuple],
) -> StartupPublicationResult:
    """VDM-A[0] = NOT raw read.status, even if a later fallback clears error.

    Caller supplies frame-4 snapshots; this does not execute prior startup
    frames. Warning code/source do not enter the Boolean calculation. Final
    PSP error output is unused; no stop/TCP local assignment occurs here.
    The independent Wait is metadata, not a sleep or a sequencing deadline.
    """
    require_boundary(boundary)
    require_error(raw_pilot_error)
    snapshots = dict(local_snapshots)
    sizes = {36: 29, 44: 77, 7: 80}
    if set(snapshots) != set(sizes) or any(
        type(values) is not tuple
        or len(values) != sizes[index]
        or any(type(v) is not bool for v in values)
        for index, values in snapshots.items()
    ):
        raise ValueError("Python-only guard: DPS/EPS/VDM-A bool tuples of 29/77/80")
    updated_vdm = (not raw_pilot_error.status,) + snapshots[7][1:]
    snapshots[7] = updated_vdm
    start = len(boundary.calls)
    error = UNWIRED
    for uid, index, name in STATUS_PUBLICATIONS:
        error = boundary.invoke(
            SOURCE,
            uid,
            "17881",
            "PSP.Write",
            error_in=error,
            uri=URI_PREFIX + name,
            local_index=index,
            data=snapshots[index],
        ).error
    return StartupPublicationResult(
        ((7, updated_vdm),),
        error,
        boundary.calls[start:],
        independent_wait_ms=100,
    )
