"""Inert projections of beam-line event frames 1..3, not complete events.

Frame 0 remains outside this model. Its supplied Boolean sequence-local
value is not an interlock permission. Separate read snapshots are required
for updates and publication; no global state, PSP, driver or sleep is used.
"""

from dataclasses import dataclass
from types import MappingProxyType

# Source device position, destination local bank, destination field.
# Consigne is field5 in each eleven-field nested device cluster.
SETPOINT_COPIES = MappingProxyType(
    {
        1: (
            (3, 9, 0),
            (4, 9, 1),
            (5, 9, 2),
            (6, 9, 3),
            (9, 9, 4),
            (10, 9, 5),
            (0, 10, 8),
            (1, 10, 5),
            (7, 10, 0),
            (8, 10, 1),
            (2, 11, 5),
        ),
        2: (
            (4, 9, 6),
            (5, 9, 7),
            (8, 9, 9),
            (7, 9, 8),
            (6, 10, 9),
            (0, 10, 6),
            (1, 10, 7),
            (2, 10, 3),
            (3, 10, 4),
        ),
    }
)
UPDATE_DIAGRAMS = MappingProxyType({1: "14354", 2: "64786"})
PUBLICATION_DIAGRAMS = MappingProxyType({1: "14553", 2: "64942"})
WAIT_DIAGRAMS = MappingProxyType({1: "15917", 2: "14963"})
URI_PREFIX = "ni.var.psp://10.20.30.2/SUPERVISION/"


@dataclass(frozen=True)
class BankWrite:
    local_index: int
    value: tuple[float, ...]


@dataclass(frozen=True)
class PublicationRequest:
    local_index: int
    uri: str
    payload: tuple[float, ...]
    error_handling: str = "independent Simple Error Handler.vi"


def _event(event):
    if type(event) is not int or event not in SETPOINT_COPIES:
        raise ValueError("saved beam-line event1 or event2 required")


def _banks(snapshots, expected):
    if (
        set(snapshots) != expected
        or any(type(key) is not int for key in snapshots)
        or any(
            type(value) is not tuple
            or len(value) != 10
            or any(type(item) is not float for item in value)
            for value in snapshots.values()
        )
    ):
        raise TypeError(
            "explicit ten-DBL snapshots for exactly the read banks required"
        )


def project_setpoint_frame(event, *, apply_setpoints, cells=None, read_snapshots=None):
    """Return unordered whole-bank writes; False executes no reads or writes."""
    _event(event)
    if type(apply_setpoints) is not bool:
        raise TypeError("explicit Boolean from the frame0 sequence local required")
    if not apply_setpoints:
        return ()
    field_types = (bool,) * 5 + (float,) * 2 + (bool,) * 4
    if (
        type(cells) is not tuple
        or len(cells) != (11 if event == 1 else 9)
        or any(
            type(cell) is not tuple
            or len(cell) != 11
            or any(type(v) is not t for v, t in zip(cell, field_types))
            for cell in cells
        )
    ):
        raise TypeError("explicit complete typed beam-line device cells required")
    mapping = SETPOINT_COPIES[event]
    expected = {bank for _, bank, _ in mapping}
    if read_snapshots is None:
        raise TypeError("separate bank snapshots required at the update frame")
    _banks(read_snapshots, expected)
    updated = {bank: list(read_snapshots[bank]) for bank in expected}
    for source, bank, field in mapping:
        updated[bank][field] = cells[source][5]
    # Sorting gives stable serialization, not an execution order between banks.
    return tuple(BankWrite(bank, tuple(updated[bank])) for bank in sorted(expected))


def project_publication_frame(event, *, read_snapshots):
    """Four independent PSP request records, even after a False update arm.

    Tuple order is canonical only. Every saved error input is unwired;
    each error output has its own handler. Completion, delivery success and
    modal-handler behavior are external and are not simulated here.
    """
    _event(event)
    _banks(read_snapshots, {9, 10, 11, 12})
    return tuple(
        PublicationRequest(
            bank, URI_PREFIX + f"C{bank - 3}NI6703", read_snapshots[bank]
        )
        for bank in (9, 10, 11, 12)
    )


def terminal_wait_ms(event):
    """Requested Wait(ms) only, after publication-frame completion; never sleep."""
    _event(event)
    return 100
