"""Literal runtime frame 2..5 field copies with explicit caller snapshots.

No initial/default values, inversion, interlock or physical polarity is
invented. Separate frame snapshots are required: the source graph reads and
writes locals, not one atomic whole-cycle state transaction.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadbackFrame:
    frame_index: int
    diagram_uid: str
    source_local_index: int
    target_local_index: int
    pairs: tuple[tuple[int, int], ...]  # source field, target field


FRAMES = (
    ReadbackFrame(
        2,
        "2010",
        18,
        28,
        tuple(
            zip(
                (
                    31,
                    32,
                    28,
                    29,
                    35,
                    36,
                    37,
                    38,
                    39,
                    40,
                    41,
                    42,
                    12,
                    13,
                    14,
                    15,
                    43,
                    44,
                    45,
                    46,
                ),
                (
                    2,
                    4,
                    14,
                    16,
                    38,
                    40,
                    50,
                    52,
                    62,
                    64,
                    74,
                    76,
                    86,
                    88,
                    98,
                    100,
                    110,
                    112,
                    122,
                    124,
                ),
            )
        ),
    ),
    ReadbackFrame(
        3,
        "8695",
        18,
        33,
        tuple(
            zip(
                (
                    24,
                    25,
                    26,
                    27,
                    20,
                    21,
                    47,
                    38,
                    39,
                    48,
                    33,
                    34,
                    51,
                    52,
                    53,
                    54,
                    18,
                    19,
                ),
                (2, 4, 14, 16, 38, 40, 50, 52, 62, 64, 74, 76, 86, 88, 98, 100, 26, 28),
            )
        ),
    ),
    ReadbackFrame(
        4,
        "1283",
        19,
        28,
        tuple(
            zip(
                (28, 20, 38, 29, 22, 30, 23, 16, 24, 31, 32),
                (7, 19, 31, 43, 55, 67, 79, 91, 103, 115, 127),
            )
        ),
    ),
    ReadbackFrame(
        5,
        "18156",
        19,
        33,
        tuple(
            zip(
                (19, 27, 25, 18, 40, 33, 21, 34, 34),
                (7, 19, 31, 43, 55, 67, 79, 91, 103),
            )
        ),
    ),
)


def copy_readback_frame(
    frame_index: int,
    *,
    source_snapshot: tuple,
    target_snapshot: tuple,
) -> tuple:
    """Preserve every untargeted field; copy exact source values to targets."""
    if type(frame_index) is not int or frame_index not in (2, 3, 4, 5):
        raise ValueError("saved readback frame 2, 3, 4 or 5 required")
    frame = FRAMES[frame_index - 2]
    if (
        type(source_snapshot) is not tuple
        or type(target_snapshot) is not tuple
        or any(
            type(v) not in (bool, int, float, str)
            for v in source_snapshot + target_snapshot
        )
        or len(source_snapshot) <= max(s for s, _ in frame.pairs)
        or len(target_snapshot) <= max(t for _, t in frame.pairs)
    ):
        raise ValueError(
            "Python-only guard: immutable scalar snapshots with required fields"
        )
    updated = list(target_snapshot)
    for source, target in frame.pairs:
        updated[target] = source_snapshot[source]
    return tuple(updated)
