"""Outer retry decision and error.status replacement from supplied phase flags.

Not a Driver Core implementation: no bytes, clocks, timeouts or VISA calls.
The suppress-warning helper subsequently consumes this intermediate error.
"""

from dataclasses import dataclass

from .boundary import ErrorCluster


@dataclass(frozen=True)
class TpgRetryResult:
    keep_running: bool
    intermediate_error: ErrorCluster


def retry_postprocess(
    *,
    iteration: int,
    retry: int,
    flag_a: bool,
    flag_b: bool,
    sequence_error: ErrorCluster,
) -> TpgRetryResult:
    """Flags come from saved phase-two locals, not presumed error.status.

    Bounds/type validation is Python-only. A continuing decision implies
    another graph iteration only if the current sequence has returned.
    """
    if (
        type(iteration) is not int
        or not 0 <= iteration <= 2**31 - 1
        or type(retry) is not int
        or not -(2**31) <= retry <= 2**31 - 1
    ):
        raise ValueError("supported I32 iteration/retry snapshot required")
    if (
        type(flag_a) is not bool
        or type(flag_b) is not bool
        or type(sequence_error) is not ErrorCluster
    ):
        raise TypeError("explicit Boolean flags and error-cluster snapshot required")
    status = flag_a or flag_b
    return TpgRetryResult(
        status and retry > iteration,
        ErrorCluster(status, sequence_error.code, sequence_error.source),
    )
