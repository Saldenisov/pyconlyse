"""Inert seven-frame cooling-trip projection, with explicitly supplied arm state.

Snapshots are separate local reads. Ordered frames do not impose an order
between independent nodes inside a frame or guarantee that another loop
samples a command before restoration. No sleeps, PSP, NI or device calls.
"""

from dataclasses import dataclass

from .boundary import UNSUPPLIED, UNWIRED, MissingValue


@dataclass(frozen=True)
class LocalWrite:
    bank: int
    data: tuple[bool, ...] | bool


@dataclass(frozen=True)
class PublicationIntent:
    node_uid: str
    uri: str
    data: tuple[bool, ...]
    error_in: MissingValue = UNWIRED
    error_handler_node: str = "39603"


@dataclass(frozen=True)
class FrameEffects:
    diagram_uid: str
    writes: tuple[LocalWrite, ...]
    requested_wait_ms: int | None = None
    publication: PublicationIntent | None = None


def _bool_cluster(snapshot, size):
    if (
        type(snapshot) is not tuple
        or len(snapshot) != size
        or any(type(x) is not bool for x in snapshot)
    ):
        raise TypeError("explicit immutable full-size Boolean local snapshot required")


def cooling_guard(*, enabled_arm, c4_snapshot, c3_snapshot):
    """Return unknown if enabled-arm selection has not been independently proven.

    Labels do not establish electrical polarity. This is the raw expression,
    not a radioprotection model or a standalone permission to run equipment.
    """
    if enabled_arm is UNSUPPLIED:
        return UNSUPPLIED
    if type(enabled_arm) is not bool:
        raise TypeError("explicit enabled-arm Boolean or UNSUPPLIED required")
    if not enabled_arm:
        return UNWIRED
    _bool_cluster(c4_snapshot, 64)
    _bool_cluster(c3_snapshot, 56)
    return (c4_snapshot[19] or c4_snapshot[38]) and (
        not c3_snapshot[0] or not c3_snapshot[6]
    )


def trip_frame(index, *, snapshots):
    """Project one reached True frame, never assume all its local reads coincide.

    Frame0 ACTION and C3 writes have no relative ordering wire. Requested
    Wait is also independent within the frame. All nodes must complete
    before the next sequence frame; no duration bound is implied.
    """
    if type(index) is not int or not 0 <= index <= 6:
        raise ValueError("one explicit trip frame0..6 required")
    expected = {
        0: {"10431"},
        1: {"13466"},
        2: set(),
        3: {"22661"},
        4: {"30986"},
        5: {"39289", "39313"},
        6: {"39444"},
    }[index]
    if set(snapshots) != expected:
        raise ValueError("all and only the selected frame's local snapshots required")
    if index in (0, 1, 3, 4):
        uid = {0: "10431", 1: "13466", 3: "22661", 4: "30986"}[index]
        bank = snapshots[uid]
        _bool_cluster(bank, 40)
        field = 1 if index in (0, 1) else 4
        value = index in (1, 4)
        after = bank[:field] + (value,) + bank[field + 1 :]
        # Tuple is an effect set for this frame, not a schedule between writes.
        writes = (LocalWrite(17, after),)
        if index == 0:
            writes += (LocalWrite(35, True),)
        return FrameEffects(
            {0: "10221", 1: "13119", 3: "20056", 4: "30644"}[index],
            writes,
            150 if index in (0, 3) else None,
        )
    if index == 2:
        return FrameEffects("14187", (), 400)
    if index == 5:
        eps, dps = snapshots["39289"], snapshots["39313"]
        _bool_cluster(eps, 77)
        _bool_cluster(dps, 29)
        changes = {1: True, 2: False, 3: False, 5: True}
        eps_after = tuple(changes.get(i, v) for i, v in enumerate(eps))
        dps_after = dps[:1] + (False,) + dps[2:]
        return FrameEffects(
            "31857", (LocalWrite(44, eps_after), LocalWrite(36, dps_after))
        )
    dps = snapshots["39444"]
    _bool_cluster(dps, 29)
    publication = PublicationIntent(
        "39450", "ni.var.psp://10.20.30.2/SUPERVISION/DPS", dps
    )
    return FrameEffects("39347", (), 100, publication)
