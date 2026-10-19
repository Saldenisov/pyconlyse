"""Saved counter reconfiguration graph with supplied returns, never NI calls.

Finite DBL products round to I32 (ties to even), saturate, then preserve their
32 bits at the U32 property input. Nonfinite values need legacy evidence;
rejecting them is a Python guard, not a legacy permission check. Missing poll
values suspend the trace instead of inventing a completed physical pulse.
"""

from dataclasses import dataclass
from math import isfinite

from .boundary import (
    UNASSIGNED,
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
    "1_ACQ_WRITE_NI6602.vi",
    "4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211",
)
POLL_UID = "3202"
WAIT_UID = "3194"
LIMIT_INDEX = 20
POST_POLL_UIDS = ("2976", "309", "3083", "3032")


def exact_u32_ticks(microseconds: float) -> int:
    """Multiply by the saved 20.0; restrict to already-integral U32 values."""
    if type(microseconds) not in (int, float):
        raise ValueError("Python-only guard: finite numeric microseconds required")
    try:
        ticks = microseconds * 20.0
    except OverflowError as exc:
        raise ValueError(
            "Python-only guard: exact nonnegative U32 ticks required"
        ) from exc
    if not isfinite(ticks) or ticks < 0 or ticks > 0xFFFFFFFF or ticks != int(ticks):
        raise ValueError("Python-only guard: exact nonnegative U32 ticks required")
    return int(ticks)


def labview_u32_ticks(microseconds: float) -> int:
    """20.0 product -> U32, finite in-range domain and ties to even.

    This historical direct-U32 helper is NOT the saved NI6602 writer path.
    NI function reference and archived 321526a manual describe the same
    rounding rule. Outside that domain, no saturation/wrap behavior is guessed.
    https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/to-unsigned-long-integer.html
    """
    if type(microseconds) not in (int, float):
        raise ValueError("Python-only guard: finite numeric microseconds required")
    try:
        product = microseconds * 20.0
    except OverflowError as exc:
        raise ValueError(
            "Python-only guard: in-range nonnegative U32 product required"
        ) from exc
    if not isfinite(product) or not 0 <= product <= 0xFFFFFFFF:
        raise ValueError("Python-only guard: in-range nonnegative U32 product required")
    return round(product)


def labview_i32_to_u32_ticks(microseconds: float) -> int:
    """Saved DBL * 20.0 -> I32 conversion -> U32 timing input, finite only.

    The original VI's type descriptors identify I32 conversion outputs and
    U32 property inputs. NI 321526a, pp. 2-4 and 4-10: floating conversions
    round ties to even and saturate; integer coercions retain low-order bits.
    This models representation, not driver acceptance or hardware safety.
    https://download.ni.com/support/manuals/321526a.pdf
    """
    if type(microseconds) not in (int, float):
        raise ValueError("Python-only guard: finite numeric microseconds required")
    try:
        product = microseconds * 20.0
    except OverflowError as exc:
        raise ValueError("Python-only guard: finite DBL product required") from exc
    if not isfinite(product):
        raise ValueError("Python-only guard: finite DBL product required")
    signed = min(2147483647, max(-2147483648, round(product)))
    return signed & 0xFFFFFFFF


@dataclass(frozen=True)
class CounterWriterResult:
    source: SourceVi
    delay_ticks: int
    high_ticks: int
    poll_iterations: int
    exit_reason: str
    final_pulse_done: bool | MissingValue
    error_out: ErrorCluster | MissingValue
    calls: tuple[BoundaryCall, ...]


def write(
    boundary: ScriptedBoundary,
    *,
    task: TaskReference,
    delay_microseconds: float,
    width_microseconds: float,
    error_in: ErrorCluster,
) -> CounterWriterResult:
    """Poll Done OR i>20; Stop -> Clear Errors -> timing property -> Start.

    Every poll receives the ORIGINAL task/error through ordinary tunnels,
    not the previous poll return. Final poll returns feed Stop. Wait(1 ms)
    is independent within each iteration; this trace chooses one admissible
    serial ordering and performs no wall-clock sleep. Error status is absent
    from the exit predicate. Clear Errors is an abstract supplied-return
    boundary: explicitly supply its cleared return when testing that case;
    ScriptedBoundary's default passthrough is not its implementation.
    """
    require_boundary(boundary)
    require_error(error_in)
    if type(task) is not TaskReference:
        raise TypeError("task requires an opaque simulation TaskReference")
    delay = labview_i32_to_u32_ticks(delay_microseconds)
    high = labview_i32_to_u32_ticks(width_microseconds)
    start = len(boundary.calls)
    reason, done = "missing_poll_value", UNSUPPLIED
    for index in range(LIMIT_INDEX + 2):
        polled = boundary.invoke(
            SOURCE,
            POLL_UID,
            "3149",
            "read_co_pulse_done",
            iteration=index,
            task_in=task,
            error_in=error_in,
            property_code=6414,
            concurrent_wait_uid=WAIT_UID,
        )
        boundary.invoke(
            SOURCE,
            WAIT_UID,
            "3149",
            "wait_ms",
            iteration=index,
            milliseconds=1,
            concurrent_property_uid=POLL_UID,
        )
        if polled.data is UNSUPPLIED:
            done = UNSUPPLIED
        elif (
            type(polled.data) is tuple
            and len(polled.data) == 1
            and type(polled.data[0]) is bool
        ):
            done = polled.data[0]
        else:
            raise ValueError("Python-only guard: one Boolean pulse-Done value required")
        if done is True or index > LIMIT_INDEX:
            reason = "pulse_done" if done is True else "iteration_limit"
            break
        if done is UNSUPPLIED:
            return CounterWriterResult(
                SOURCE,
                delay,
                high,
                index + 1,
                reason,
                done,
                UNASSIGNED,
                boundary.calls[start:],
            )
    stopped = boundary.invoke(
        SOURCE,
        "2976",
        "3",
        "stop_task",
        task_in=polled.task,
        error_in=polled.error,
    )
    cleared = boundary.invoke(
        SOURCE,
        "309",
        "3",
        "clear_errors",
        error_in=stopped.error,
        connected_error_input_slot=4,
        connected_error_output_slot=0,
    )
    configured = boundary.invoke(
        SOURCE,
        "3083",
        "3",
        "write_co_timing_properties",
        task_in=stopped.task,
        error_in=cleared.error,
        property_codes=(664, 4465, 4457),
        initial_delay_ticks=delay,
        low_ticks=delay,
        high_ticks=high,
    )
    started = boundary.invoke(
        SOURCE,
        "3032",
        "3",
        "start_task",
        task_in=configured.task,
        error_in=configured.error,
    )
    return CounterWriterResult(
        SOURCE,
        delay,
        high,
        index + 1,
        reason,
        done,
        started.error,
        boundary.calls[start:],
    )
