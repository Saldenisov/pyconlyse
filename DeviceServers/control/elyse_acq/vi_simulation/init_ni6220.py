"""NI6220 ignores public error-in, but returns its final internal error."""

from .ai_common import AiTaskSpec, configure_task
from .boundary import (
    UNWIRED,
    ErrorCluster,
    InitializerResult,
    SampleClockInputs,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_INIT_NI6220.vi",
    "58532480F5234E0FFF36417C5A0A0513B5B7267D4451BF42D0B7A0BDE271F3CA",
)
TASK = AiTaskSpec(
    11,
    "C1_NI6220",
    "3",
    "2798",
    "2629",
    "2818",
    "2393",
    "2454",
    "2561",
    tuple(10.0 if i in (4, 5, 6, 7) else 0.2 for i in range(16)),
)


def initialize(
    boundary: ScriptedBoundary,
    *,
    clock: SampleClockInputs,
    error_in: ErrorCluster,
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)  # Input exists but is not consumed by saved dataflow.
    offset = len(boundary.calls)
    result = configure_task(
        boundary,
        SOURCE,
        TASK,
        clock=clock,
        trigger_source="/11/PFI0",
        create_error_in=UNWIRED,
    )
    return InitializerResult(
        SOURCE, (result.task,), result.error, result.error, boundary.calls[offset:]
    )
