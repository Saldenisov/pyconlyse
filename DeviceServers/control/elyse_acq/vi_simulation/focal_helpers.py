"""Three independent CHROMA command chains, with in-memory returns only.

Branch order is an admissible supplied schedule, not a saved total ordering.
ON and OFF both reset/configure before Set Output. No emergency override,
serial session, vendor DLL call or guaranteed cleanup is implemented.
"""

from dataclasses import dataclass

from .boundary import (
    NO_ERROR,
    UNWIRED,
    BoundaryCall,
    ErrorCluster,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
)

SOURCES = {
    True: SourceVi(
        "1_Focales ON.vi",
        "009BC77EB5075E26E4F5903F66FA9663EFBCDA6F4B2B5E570232CA12034DEAD1",
    ),
    False: SourceVi(
        "1_Focales OFF.vi",
        "6D7E94E55D7B6BC5B5CFE3855D9E27B17C3A0DCADE5F261794194E9FB86301DF",
    ),
}
NODES = {
    True: {
        3: ("738", "839", "1050", "902", "963", "585"),
        2: ("567", "2188", "2789", "2246", "2497", "2288"),
        1: ("659", "2788", "3857", "3731", "3770", "2560"),
    },
    False: {
        3: ("670", "712", "909", "751", "790", "594"),
        2: ("567", "2188", "2789", "2246", "2497", "2288"),
        1: ("659", "2788", "3857", "3731", "3770", "2560"),
    },
}
STEPS = (
    "Initialize",
    "Set Voltage",
    "Set Current Slew",
    "Set Current",
    "Set Output",
    "Close",
)
VALUES = {3: (70.0, 0.02, 15.1), 2: (80.0, 0.02, 20.9), 1: (80.0, 0.02, 13.73)}


@dataclass(frozen=True)
class FocalResult:
    source: SourceVi
    error_out: ErrorCluster
    branch_errors: tuple[tuple[int, ErrorCluster], ...]
    calls: tuple[BoundaryCall, ...]


def record_focal_commands(
    boundary: ScriptedBoundary,
    *,
    enabled: bool,
    resources: tuple[str, str, str],
    branch_order: tuple[int, int, int] = (3, 2, 1),
) -> FocalResult:
    """Resources are explicit F3/F2/F1 control snapshots, not connector inputs."""
    require_boundary(boundary)
    if (
        type(enabled) is not bool
        or type(resources) is not tuple
        or len(resources) != 3
        or any(type(resource) is not str or not resource for resource in resources)
        or type(branch_order) is not tuple
        or any(type(f) is not int for f in branch_order)
        or sorted(branch_order) != [1, 2, 3]
    ):
        raise ValueError(
            "Python-only guard: bool, three explicit resources and branch permutation"
        )
    source = SOURCES[enabled]
    start = len(boundary.calls)
    errors = {}
    for focal in branch_order:
        task, error = UNWIRED, UNWIRED
        voltage, slew, current = VALUES[focal]
        arguments = (
            {"resource": resources[3 - focal], "id_query": False, "reset": True},
            {"voltage": voltage},
            {"current_slew": slew},
            {"current": current},
            {"enabled": enabled},
            {},
        )
        for uid, step, args in zip(NODES[enabled][focal], STEPS, arguments):
            returned = boundary.invoke(
                source,
                uid,
                "3",
                "CHROMA." + step,
                task_in=task,
                error_in=error,
                **args,
            )
            task, error = returned.task, returned.error
        errors[focal] = error
    ordered = tuple(errors[focal] for focal in (3, 2, 1))
    merged = next(
        (e for e in ordered if e.status),
        next((e for e in ordered if e.code != 0), NO_ERROR),
    )
    return FocalResult(
        source, merged, tuple(zip((3, 2, 1), ordered)), boundary.calls[start:]
    )
