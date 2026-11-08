"""Pure Timeout PSP caller trace, with supplied data/errors and no transport.

Error wires order call arguments. Local data assignments have no ordering
wire relative to the next reader; the result represents a completed frame,
not an atomic state update. No freshness or interlock permission is inferred.
"""

from dataclasses import dataclass
from legacy.xp_acq_agent.elyse_agent.saved_psp_reads import route_read_values, replay_saved_psp_reads as replay_saved_psp_reads

from .boundary import UNWIRED, ErrorCluster, MissingValue

SITES = (
    ("10310", "C6NI6703", 9, 10, float),
    ("10333", "C7NI6703", 10, 10, float),
    ("10369", "C8NI6703", 11, 10, float),
    ("10449", "C9NI6703", 12, 10, float),
    ("22278", "C1011NI6602", 39, 33, float),
    ("25403", "C3_OUT_DIO96", 17, 40, bool),
    ("25426", "C4_OUT_DIO96", 15, 32, bool),
    ("25449", "C5_OUT_DIO96", 13, 40, bool),
    ("19950", "DPS", 36, 29, bool),
    ("19974", "DPC", 37, 5, bool),
    ("19997", "EPS", 44, 77, bool),
    ("22840", "EPC", 38, 12, bool),
)
URI_PREFIX = "ni.var.psp://10.20.30.2/SUPERVISION/"
BODY_WAIT_MS = 75
EVENT_TIMEOUT_MS = 20


@dataclass(frozen=True)
class PspReturn:
    data: tuple
    error: ErrorCluster


@dataclass(frozen=True)
class ReadCall:
    node_uid: str
    uri: str
    error_in: ErrorCluster | MissingValue
    default_data: tuple
    returned: PspReturn


@dataclass(frozen=True)
class ReadFrame:
    calls: tuple[ReadCall, ...]
    data_assignments: tuple[tuple[int, tuple], ...]
    fault_assignments: tuple[tuple[int, bool], ...]
    stop_after: bool
    tcp_ed_after: bool


def _cluster(value, size, element):
    if (
        type(value) is not tuple
        or len(value) != size
        or any(type(v) is not element for v in value)
    ):
        raise TypeError("explicit immutable full-size PSP cluster snapshot required")


def read_frame(*, default_snapshots, returned_snapshots, stop_before, tcp_ed_before):
    """Project saved caller writes, not NI's read-on-error/default-data semantics.

    Each default snapshot represents its own local read, not one global epoch.
    Data written on a returned fault comes from the supplied boundary return;
    it is not automatically replaced by zero or the previous local value.
    """
    if type(stop_before) is not bool or type(tcp_ed_before) is not bool:
        raise TypeError("explicit stop and TCP ED Boolean snapshots required")
    expected = {uid for uid, *_ in SITES}
    if set(default_snapshots) != expected or set(returned_snapshots) != expected:
        raise ValueError("all twelve reader-return/default snapshots required")
    defaults, returns = {}, {}
    for uid, tag, bank, size, element in SITES:
        prior, returned = default_snapshots[uid], returned_snapshots[uid]
        if not isinstance(returned, PspReturn) or not isinstance(
            returned.error, ErrorCluster
        ):
            raise TypeError("explicit PSP data and ErrorCluster return required")
        _cluster(prior, size, element)
        _cluster(returned.data, size, element)
        defaults[uid], returns[uid] = prior, returned
    result = route_read_values(defaults, returns, stop_before, tcp_ed_before, UNWIRED)
    return ReadFrame(
        tuple(ReadCall(*call) for call in result.calls),
        result.data_assignments,
        result.fault_assignments,
        result.stop_after,
        result.tcp_ed_after,
    )
