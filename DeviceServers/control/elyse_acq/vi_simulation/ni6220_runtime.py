"""Non-actuating NI6220 caller projection from supplied return snapshots.

No DAQmx, transport, clock, waits or hidden statistical-helper state.
True-counter default dispatch remains an explicit open bound. Typed 1D DBL
Index Array returns 0.0 beyond the supplied array's bounds, including empty.
Read errors reach the handler but do not gate the two data frames.
"""

from dataclasses import dataclass

from .boundary import UNSUPPLIED, ErrorCluster, MissingValue

REQUESTED_WAIT_MS = 15
POINT_SAMPLE_LENGTH = 20
POINT_CHANNELS = (0, 1, 2, 3, 8, 9)
POINT_NODE_UIDS = ("48830", "48930", "48951", "48972", "48993", "49014")


def _doubles(values, *, size=None):
    if (
        type(values) is not tuple
        or (size is not None and len(values) != size)
        or any(type(value) is not float for value in values)
    ):
        raise TypeError("explicit immutable DBL snapshot required")


def _index_dbl(values, index):
    """Saved scalar Index Array behavior, not a driver-return assumption."""
    return values[index] if 0 <= index < len(values) else 0.0


def _u32(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError("explicit U32 counter snapshot required")


@dataclass(frozen=True)
class CounterFrame:
    bank65_previous: tuple[float, ...]
    bank66_captured: tuple[float, ...] | MissingValue
    bank67_before_rise: tuple[float, ...]
    counter_after: int | MissingValue
    counter_written: bool | MissingValue
    captured: bool | MissingValue
    threshold_true: bool
    counter_diagram_uid: str | MissingValue


def counter_frame(
    *,
    reader_values,
    bank65,
    bank66,
    bank67,
    current_mean_return,
    previous_mean_return,
    counter_selector_snapshot,
    increment_read_snapshot,
    increment_return,
):
    """Apply proven cases only; supplied increment return retains overflow boundary.

    Counter selector and the later increment's local read are separate snapshots.
    NI Mean and U32 Increment outputs are supplied, not silently reimplemented.
    All non-0/non-3 True selectors return an unresolved result, not guessed Default.
    """
    _doubles(reader_values)
    for array in (bank65, bank66, bank67):
        # These locals are variable-length arrays, not four-element clusters.
        # The original source persists all three empty. Mean(empty) remains
        # supplied; no padding, initialization reset or native return is guessed.
        _doubles(array)
    if (
        type(current_mean_return) is not float
        or type(previous_mean_return) is not float
    ):
        raise TypeError("explicit two NI Mean DBL returns required")
    for counter in (
        counter_selector_snapshot,
        increment_read_snapshot,
        increment_return,
    ):
        _u32(counter)
    current = tuple(_index_dbl(reader_values, index) for index in (4, 5, 6, 7))
    rising = current_mean_return > previous_mean_return + 0.03
    before_rise = bank65 if rising else bank67
    selector = counter_selector_snapshot
    if rising and selector not in (0, 3):
        return CounterFrame(
            current,
            UNSUPPLIED,
            before_rise,
            UNSUPPLIED,
            UNSUPPLIED,
            UNSUPPLIED,
            True,
            UNSUPPLIED,
        )
    if selector == 3:
        return CounterFrame(
            current,
            current,
            before_rise,
            0,
            True,
            True,
            rising,
            "81868" if rising else "100569",
        )
    if not rising and selector == 0:
        return CounterFrame(
            current, bank66, before_rise, selector, False, False, False, "104729"
        )
    # False selector 1 is the saved explicit/default arm (SelectDefaultCase=01).
    # True selector 0 is explicit; no implicit default is asserted.
    return CounterFrame(
        current,
        bank66,
        before_rise,
        increment_return,
        True,
        False,
        rising,
        "81862" if rising else "100537",
    )


@dataclass(frozen=True)
class PointCall:
    node_uid: str
    channel: int
    input_value: float
    sample_length: int
    returned_mean: float


@dataclass(frozen=True)
class PointFrame:
    bank59: tuple[float, ...]
    calls: tuple[PointCall, ...]
    indicator: float


def point_frame(*, reader_values, point_mean_returns, bank63):
    """Six separately identified standard calls; no invented reset/default inputs."""
    _doubles(reader_values)
    _doubles(point_mean_returns, size=6)
    if type(bank63) is not int or not 0 <= bank63 < 2**16:
        raise ValueError("explicit U16 selected-channel snapshot required")
    calls = tuple(
        PointCall(
            uid,
            channel,
            _index_dbl(reader_values, channel),
            POINT_SAMPLE_LENGTH,
            returned,
        )
        for uid, channel, returned in zip(
            POINT_NODE_UIDS, POINT_CHANNELS, point_mean_returns
        )
    )
    indicator = _index_dbl(point_mean_returns, bank63)
    return PointFrame(point_mean_returns, calls, indicator)


@dataclass(frozen=True)
class RuntimeResult:
    counter_frame: CounterFrame
    point_frame: PointFrame
    handler_error: ErrorCluster
    keep_running: bool
    requested_wait_ms: int


def completed_iteration(
    *, read_error, stop_snapshot, point_arguments, counter_arguments
):
    """Only a returned read: no cancellation or same-iteration error stop invented."""
    if not isinstance(read_error, ErrorCluster) or type(stop_snapshot) is not bool:
        raise TypeError(
            "explicit read error and independent Boolean stop snapshots required"
        )
    first = counter_frame(**counter_arguments)
    second = point_frame(**point_arguments)
    if counter_arguments["reader_values"] != point_arguments["reader_values"]:
        raise ValueError("both ordered frames require the same reader-return snapshot")
    return RuntimeResult(
        first, second, read_error, not stop_snapshot, REQUESTED_WAIT_MS
    )
