"""Pure legacy digital/UI plans for main-VI events 4, 5, 8, 9, 10, 11.

Native Print, original XML wires and corrected stored local identities define
these rules. No plan runs a wait, local-variable assignment, property write or
PSP operation. A digital command and a UI button are not physical readback.
Frame order is retained; operations within a frame are not linearized.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/digital_event_evidence_20261003.json"
EVIDENCE_SHA256 = "43D347C72308B044E5AEAF5CE8F54C1507855DEE615F91DCC5BB34E045165146"
BASE_CLUSTER = "C5_OUT_DIO96"
PSP_URL = "ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96"
FARADAY_FIELDS = (
    "23 DPA7 b84 Cmd Faraday 1 EN",
    "24 DPB0 b82 Cmd Faraday 2 EN",
    "25 DPB1 b80 Cmd Faraday 3 EN",
)
FARADAY_EN_INPUTS = tuple(f"Etat Faraday {i} EN" for i in (1, 2, 3))
FARADAY_UI_RESETS = tuple((f"Position Faraday {i}", False) for i in (1, 2, 3))
MIRROR_FIELDS = (
    "22 DPA6 b86 Cmd Miroir LASER EN",
    "26 DPB2 b78 Cmd Miroir LASER HORS",
)
SLIT_SUPPLY_FIELD = "27 DPB3 b76 M/A alimentation Fente H"


class FaradayStation(IntEnum):
    ONE = 1
    TWO = 2
    THREE = 3


@dataclass(frozen=True)
class ClusterWriteEvidence:
    bundle_uid: int
    local_read_uid: int
    local_write_uid: int
    psp_write_uid: int
    error_handler_uid: int


@dataclass(frozen=True)
class UiColorAssignment:
    control: str
    # Two observed legacy color integers; no CSS/RGB interpretation is assumed.
    values: tuple[int, int]


@dataclass(frozen=True)
class DigitalEventFrame:
    index: int
    patches: tuple[tuple[str, bool], ...] = ()
    write_evidence: ClusterWriteEvidence | None = None
    waits_ms: tuple[int, ...] = ()
    ui_assignments: tuple[tuple[str, bool], ...] = ()
    ui_colors: tuple[UiColorAssignment, ...] = ()
    source_state_reads: tuple[str, ...] = ()
    # In particular, a wait in this frame is NOT ordered after the PSP write.
    operations_within_frame_serialized: bool = field(default=False, init=False)

    @property
    def fresh_local_cluster_read_required(self) -> bool:
        return self.write_evidence is not None


@dataclass(frozen=True)
class DigitalCommandEventPlan:
    event_case_index: int
    event_new_value: int | bool
    selector_uid: int
    sequence_uid: int | None
    frames: tuple[DigitalEventFrame, ...]
    dedicated_pulse_wait_frame: bool
    base_cluster: str = field(default=BASE_CLUSTER, init=False)
    psp_url: str = field(default=PSP_URL, init=False)
    connection_refnum: int = field(default=47, init=False)
    preserves_unmentioned_fields: bool = field(default=True, init=False)
    frame_order_serialized: bool = field(default=True, init=False)
    later_frames_conditioned_on_success: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    exact_physical_pulse_width_proven: bool = field(default=False, init=False)
    establishes_physical_state: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(
        default=(
            "endpoint ownership, polarity, limits, permissives and safe states",
            "PSP acknowledgement, acquisition sampling and downstream pulse semantics",
            "freshness and coherent sampling of separately supplied EN status inputs",
            "non-atomic local-cluster read/modify/write races with other writers",
            "same-frame local/PSP/UI sink order and modal error-handler behavior",
            "scheduler timing and exact physical pulse duration",
            "native defaults beyond the explicitly supported selector contract",
            "global Print-to-UID reconciliation remains UNMAPPED",
        ),
        init=False,
    )

    @property
    def write_error_handlers_observed(self) -> bool:
        return any(frame.write_evidence is not None for frame in self.frames)


@dataclass(frozen=True)
class FaradayPulseRule:
    station: FaradayStation
    event_index: int
    selector_uid: int
    sequence_uid: int
    writes: tuple[ClusterWriteEvidence, ClusterWriteEvidence]


FARADAY_PULSE_RULES = (
    FaradayPulseRule(
        FaradayStation.ONE,
        9,
        53995,
        54575,
        (
            ClusterWriteEvidence(54659, 54644, 54637, 54669, 54688),
            ClusterWriteEvidence(55231, 55216, 55203, 55252, 55317),
        ),
    ),
    FaradayPulseRule(
        FaradayStation.TWO,
        10,
        77922,
        78242,
        (
            ClusterWriteEvidence(78292, 78286, 78280, 78302, 78398),
            ClusterWriteEvidence(78521, 78515, 78509, 78531, 78548),
        ),
    ),
    FaradayPulseRule(
        FaradayStation.THREE,
        11,
        57006,
        62574,
        (
            ClusterWriteEvidence(62637, 62631, 62619, 62647, 62674),
            ClusterWriteEvidence(62945, 62938, 62931, 62956, 62975),
        ),
    ),
)
_MIRROR_WRITES = (
    (
        ClusterWriteEvidence(53898, 53890, 53881, 53908, 54213),
        ClusterWriteEvidence(86018, 86012, 86004, 86028, 86045),
    ),
    (
        ClusterWriteEvidence(56574, 56568, 56560, 56584, 56650),
        ClusterWriteEvidence(56839, 56833, 56827, 56849, 56870),
    ),
)


def _selector(value: int, allowed: tuple[int, ...]) -> None:
    if type(value) is not int:
        raise TypeError("Exact integer selector required; Boolean is not a selector")
    if value not in allowed:
        raise ValueError("Selector outside the explicitly evidenced contract")


def _pulse_frames(
    field_name: str,
    writes: tuple[ClusterWriteEvidence, ClusterWriteEvidence],
    wait_ms: int,
    resets: tuple[tuple[str, bool], ...] = (),
) -> tuple[DigitalEventFrame, ...]:
    return (
        DigitalEventFrame(0, ((field_name, True),), writes[0]),
        DigitalEventFrame(1, waits_ms=(wait_ms,)),
        DigitalEventFrame(2, ((field_name, False),), writes[1], ui_assignments=resets),
    )


def plan_faraday_position_change(
    station: FaradayStation, event_new_value: bool
) -> DigitalCommandEventPlan:
    """False is an empty branch; True pulses one field and resets all 3 buttons."""
    if not isinstance(station, FaradayStation):
        raise TypeError("Explicit FaradayStation required")
    if type(event_new_value) is not bool:
        raise TypeError("Exact Boolean event NewVal required")
    rule = next(r for r in FARADAY_PULSE_RULES if r.station is station)
    frames = (
        _pulse_frames(FARADAY_FIELDS[station - 1], rule.writes, 500, FARADAY_UI_RESETS)
        if event_new_value
        else ()
    )
    return DigitalCommandEventPlan(
        rule.event_index,
        event_new_value,
        rule.selector_uid,
        rule.sequence_uid if event_new_value else None,
        frames,
        bool(frames),
    )


def plan_laser_mirror_change(event_new_value: int) -> DigitalCommandEventPlan:
    """0 selects EN; 1 selects HORS. Other native-default values fail closed."""
    _selector(event_new_value, (0, 1))
    return DigitalCommandEventPlan(
        8,
        event_new_value,
        76431,
        (77973, 56518)[event_new_value],
        _pulse_frames(
            MIRROR_FIELDS[event_new_value], _MIRROR_WRITES[event_new_value], 1000
        ),
        True,
    )


def plan_slit_supply_change(event_new_value: int) -> DigitalCommandEventPlan:
    """Fentes tab: 0 -> False, 1 -> True, with two unordered color/wait frames."""
    _selector(event_new_value, (0, 1))
    write = (
        ClusterWriteEvidence(61014, 61008, 60997, 61030, 61084),
        ClusterWriteEvidence(82989, 82983, 82975, 82999, 83041),
    )[event_new_value]
    return DigitalCommandEventPlan(
        5,
        event_new_value,
        60524,
        (60554, 82881)[event_new_value],
        (
            DigitalEventFrame(
                0,
                ((SLIT_SUPPLY_FIELD, bool(event_new_value)),),
                write,
                (500,),
                ui_colors=(UiColorAssignment("Fentes", (7171459, 7171459)),),
            ),
            DigitalEventFrame(
                1,
                waits_ms=(500,),
                ui_colors=(UiColorAssignment("Fentes", (12171705, 12171705)),),
            ),
        ),
        False,
    )


def plan_faraday_tab_change(
    event_new_value: int,
    *,
    en_states: tuple[bool, bool, bool] | None = None,
) -> DigitalCommandEventPlan:
    """Tabs 1/2/3 do nothing; Arrêt(0) requests NOT each incoming EN state.

    Arrêt is a historical tab label, not a proven hardware stop/interlock.
    Both observed 500-ms waits share frames with other operations. They cannot
    be replaced by the dedicated-wait pulse model used for events 9/10/11.
    """
    _selector(event_new_value, (0, 1, 2, 3))
    if event_new_value:
        return DigitalCommandEventPlan(4, event_new_value, 18778, None, (), False)
    if en_states is None:
        raise ValueError("Arrêt requires explicit incoming EN states for all 3 cups")
    if type(en_states) is not tuple or len(en_states) != 3:
        raise TypeError("Three Boolean EN states in station order required")
    if any(type(state) is not bool for state in en_states):
        raise TypeError("Unknown/non-Boolean EN state cannot be treated as False")
    writes = (
        ClusterWriteEvidence(25219, 25207, 24917, 25971, 27103),
        ClusterWriteEvidence(21248, 20987, 20818, 77310, 77353),
    )
    return DigitalCommandEventPlan(
        4,
        event_new_value,
        18778,
        19355,
        (
            DigitalEventFrame(
                0,
                tuple(zip(FARADAY_FIELDS, (not state for state in en_states))),
                writes[0],
                (500,),
                ui_colors=(UiColorAssignment("Faraday", (7171459, 7171459)),),
                source_state_reads=FARADAY_EN_INPUTS,
            ),
            DigitalEventFrame(
                1,
                tuple((name, False) for name in FARADAY_FIELDS),
                writes[1],
            ),
            DigitalEventFrame(
                2,
                waits_ms=(500,),
                ui_assignments=FARADAY_UI_RESETS,
                ui_colors=(UiColorAssignment("Faraday", (12171705, 12171705)),),
            ),
        ),
        False,
    )


def project_digital_frame(
    frame: DigitalEventFrame, current_cluster: Mapping[str, bool]
) -> dict[str, bool]:
    """Project an explicit snapshot; never read/write a live variable.

    Each writing frame must receive its own snapshot. Reusing the first frame's
    copy after a wait can overwrite intervening changes to unrelated fields.
    """
    if not isinstance(frame, DigitalEventFrame):
        raise TypeError("DigitalEventFrame required")
    if not isinstance(current_cluster, Mapping):
        raise TypeError("Explicit cluster mapping required")
    projected = dict(current_cluster)
    if any(type(k) is not str or type(v) is not bool for k, v in projected.items()):
        raise TypeError("Explicit string-keyed Boolean cluster snapshot required")
    for name, value in frame.patches:
        if name not in projected:
            raise ValueError(f"Missing legacy field in cluster snapshot: {name}")
        if type(value) is not bool:
            raise TypeError("Boolean patch required")
        projected[name] = value
    return projected
