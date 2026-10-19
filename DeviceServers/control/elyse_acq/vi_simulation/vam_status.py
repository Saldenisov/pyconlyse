"""Pure VAM-A frame field copies from independent supplied bank snapshots.

Saved root SHA256 6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF.
No threshold, transport, permission, scheduler, clock or hardware operation.
Direct cluster fixtures require checked full sizes. Short arrays require
explicit external conversion returns; their missing entries are not guessed.
"""

import math
from dataclasses import dataclass

REQUESTED_BODY_WAIT_MS = 80


def keep_running(stop_snapshot: bool) -> bool:
    """Stop read is independent of publication; do not invent same-iteration order."""
    if type(stop_snapshot) is not bool:
        raise TypeError("explicit Boolean stop snapshot required")
    return not stop_snapshot


def _doubles(values, size):
    if (
        type(values) is not tuple
        or len(values) != size
        or any(type(v) is not float for v in values)
    ):
        raise TypeError("explicit full-size immutable DBL snapshot required")


def _i32(value):
    if type(value) is not int or not -(2**31) <= value < 2**31:
        raise ValueError("explicit I32 snapshot required")


def _check_conversion(array, cluster, size):
    """Check existing DBL values without claiming native NaN payload bits."""
    if type(array) is not tuple or any(type(v) is not float for v in array):
        raise TypeError("explicit immutable DBL array required")
    _doubles(cluster, size)
    for source, returned in zip(array[:size], cluster):
        if math.isnan(source) and math.isnan(returned):
            continue
        if source == returned and (
            source != 0.0 or math.copysign(1.0, source) == math.copysign(1.0, returned)
        ):
            continue
        raise ValueError("supplied conversion contradicts existing array elements")


@dataclass(frozen=True)
class FirstFrame:
    vam: tuple[float, ...]
    bank40_counter: int


def first_frame(vam, *, iteration, bank32, bank31, bank53, bank54, bank60, bank59):
    _doubles(vam, 64)
    _doubles(bank59, 8)
    for value in (iteration, bank32, bank31):
        _i32(value)
    if any(type(v) is not float for v in (bank53, bank54, bank60)):
        raise TypeError("explicit pressure DBL snapshots required")
    fields = list(vam)
    for index, value in (
        (0, float(iteration)),
        (1, float(bank32)),
        (2, float(bank31)),
        (10, bank53),
        (11, bank54),
        (20, bank60),
    ):
        fields[index] = value
    fields[12:19] = bank59[:7]
    return FirstFrame(tuple(fields), iteration)


def first_frame_from_conversion(vam, *, bank59, array_to_cluster_return, **arguments):
    """Accept short producer arrays only with a supplied 8-DBL NI conversion.

    The NI6220 caller produces six means. Missing two cluster entries are
    not inferred to be zero or stale. This explicitly supplied boundary
    return permits composition without misreporting eight measured channels.
    """
    _check_conversion(bank59, array_to_cluster_return, 8)
    return first_frame(vam, bank59=array_to_cluster_return, **arguments)


def second_frame(vam, *, bank62, bank66, bank67):
    """Next sequence frame reads VAM after the preceding frame's write."""
    _doubles(vam, 64)
    _doubles(bank66, 4)
    _doubles(bank67, 4)
    _i32(bank62)
    fields = list(vam)
    fields[32:36] = bank66
    fields[36:40] = bank67
    fields[63] = float(bank62)
    return tuple(fields)


def second_frame_from_conversions(
    vam,
    *,
    bank62,
    bank66,
    bank67,
    bank66_array_to_cluster_return,
    bank67_array_to_cluster_return,
):
    """Separate WCM local reads and two supplied four-DBL cluster returns.

    Empty persisted arrays are legal source fixtures. They do not establish
    zero padding, a reset, shared sampling time or coherent capture epochs.
    """
    for array, cluster in (
        (bank66, bank66_array_to_cluster_return),
        (bank67, bank67_array_to_cluster_return),
    ):
        _check_conversion(array, cluster, 4)
    return second_frame(
        vam,
        bank62=bank62,
        bank66=bank66_array_to_cluster_return,
        bank67=bank67_array_to_cluster_return,
    )
