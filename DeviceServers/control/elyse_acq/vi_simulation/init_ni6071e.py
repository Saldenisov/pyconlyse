"""NI6071E's public error connectors are not its internal error chain.

No value is invented for the unwritten public indicator. A caller may supply
its initial value explicitly; otherwise the result remains UNASSIGNED.
The Simple Error Handler is a recorded external boundary, never a dialog.
"""

from .ai_common import AiTaskSpec, configure_task
from .boundary import (
    UNASSIGNED,
    UNWIRED,
    ErrorCluster,
    InitializerResult,
    MissingValue,
    SampleClockInputs,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_INIT_NI6071E.vi",
    "FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C",
)
TASKS = (
    AiTaskSpec(
        1,
        "C1_NI6071E",
        "2383",
        "2798",
        "2629",
        "2818",
        "2393",
        "2454",
        "2561",
        tuple(0.05 if i == 2 else 1.0 if i in (3, 4) else 10.0 for i in range(64)),
    ),
    AiTaskSpec(
        2,
        "C2_NI6071E",
        "944",
        "2948",
        "2462",
        "2959",
        "998",
        "2212",
        "2380",
        (10.0,) * 64,
    ),
)


def initialize(
    boundary: ScriptedBoundary,
    *,
    clock: SampleClockInputs,
    trigger_c1: str,
    trigger_c2: str,
    error_in: ErrorCluster,
    public_error_out_seed: ErrorCluster | MissingValue = UNASSIGNED,
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)  # Saved public error-in is unwired.
    if (
        type(public_error_out_seed) is not ErrorCluster
        and public_error_out_seed is not UNASSIGNED
    ):
        raise TypeError("public_error_out_seed requires ErrorCluster or UNASSIGNED")
    if type(trigger_c1) is not str or type(trigger_c2) is not str:
        raise TypeError("trigger inputs require strings")
    offset = len(boundary.calls)
    # Sequence frame 0 (UID 1144) has no external call. C1 begins in frame 1.
    c1 = configure_task(
        boundary,
        SOURCE,
        TASKS[0],
        clock=clock,
        trigger_source=trigger_c1,
        create_error_in=UNWIRED,
    )
    c2 = configure_task(
        boundary,
        SOURCE,
        TASKS[1],
        clock=clock,
        trigger_source=trigger_c2,
        create_error_in=c1.error,
    )
    boundary.invoke(SOURCE, "134", "944", "simple_error_handler", error_in=c2.error)
    return InitializerResult(
        SOURCE,
        (c1.task, c2.task),
        public_error_out_seed,
        c2.error,
        boundary.calls[offset:],
    )
