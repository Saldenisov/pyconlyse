"""Record eight PSP requests in memory; never import a PSP/network client.

Caller supplies each local read snapshot. Their acquisition is not an atomic
state transaction. Returned errors are fixtures, not network observations.
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
)

SOURCE = SourceVi(
    "0_ACQ_ELYSE.vi",
    "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
)
PUBLICATIONS = (
    ("2182", 19, "C1NI6071E"),
    ("7854", 20, "C2NI6071E"),
    ("18665", 44, "EPS"),
    ("18683", 38, "EPC"),
    ("18703", 2, "VTA"),
    ("2052", 18, "C3_IN_DIO96"),
    ("4245", 16, "C4_IN_DIO96"),
    ("7486", 14, "C5_IN_DIO96"),
)
URI_PREFIX = "ni.var.psp://10.20.30.2/SUPERVISION/"


@dataclass(frozen=True)
class PublicationResult:
    final_error: ErrorCluster
    assignments: tuple[tuple[int, bool], ...]
    calls: tuple[BoundaryCall, ...]


def publish(boundary: ScriptedBoundary, *, local_snapshots: Mapping[int, tuple]):
    """Return literal local assignments, not a guaranteed observed loop exit."""
    require_boundary(boundary)
    snapshots = dict(local_snapshots)
    if set(snapshots) != {p[1] for p in PUBLICATIONS} or any(
        type(value) is not tuple
        or any(type(item) not in (bool, int, float, str) for item in value)
        for value in snapshots.values()
    ):
        raise ValueError("Python-only guard: eight explicit immutable scalar snapshots")
    start = len(boundary.calls)
    error = UNWIRED
    for uid, index, name in PUBLICATIONS:
        returned = boundary.invoke(
            SOURCE,
            uid,
            "7392",
            "PSP.Write",
            error_in=error,
            uri=URI_PREFIX + name,
            local_index=index,
            data=snapshots[index],
        )
        error = returned.error
    assignments = ((30, True), (45, True)) if error.status else ()
    return PublicationResult(error, assignments, boundary.calls[start:])
