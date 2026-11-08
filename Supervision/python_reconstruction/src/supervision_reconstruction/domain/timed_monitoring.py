"""Pure projections for main-VI monitoring sequence 16409, frames 0..8.

The actual original owner is timeLoop 17671; its wrapper is omitted by the
frozen parser export. These functions therefore are not a scheduler, history
store, refresh timer, interlock or complete loop replacement. Current and
previous readings, mean outputs and graph state must be supplied explicitly.
No local, PSP, NI PtByPt, camera, controller or hardware operation is executed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .radioprotection import EpcState, RadioprotectionGraph

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/non_event_logic_evidence_20261004.json"
EVIDENCE_SHA256 = "A93291A2988B13C704AAAC2C5602666578CF645543F842940FDB0E00F61F863E"
TIME_CONTROL_MEAN_NODE_ORDER = (73237, 37113, 37657, 36751, 38336, 45229, 36936)
VACUUM_CHART_SOURCE_ORDER = (
    "Lec Vide ch. prép.",
    "Lec Vide CANON",
    "Lec Vide HF",
    "Lec TPG300 Section",
    "Lec Vide DIP1",
    "Lec Vide MIROIR",
    "Lec Ecran 1",
)
FRAME_INDICES = tuple(range(9))
EMPTY_FRAME_INDEX = 6


@dataclass(frozen=True)
class MonitoringEvidenceBlock:
    vi_name: str
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


MONITORING_BLOCKED = MonitoringEvidenceBlock(
    vi_name="0_SUP_ELYSE.vi",
    implementation_allowed=False,
    unresolved_contracts=(
        "timed-loop scheduling, stop/error propagation and first-iteration state",
        "independent local reads, freshness and coherent cross-host snapshots",
        "NI Mean PtByPt startup/reset/state isolation and numeric edge behavior",
        "chart history/display properties and helper retained output state",
        "runtime local/PSP/UI effects and physical interlock meaning",
    ),
)


@dataclass(frozen=True)
class MonitoringCounters:
    acq_auxiliary: float
    acq_variables: float
    acq_events: float
    sup_video: float
    sup_variables: float
    sup_events: float


def _dbl(value, name):
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be an explicit numeric DBL value")
    return float(value)


def _boolean(value, name):
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


def project_counter_deltas(
    current: MonitoringCounters, previous: MonitoringCounters
) -> MonitoringCounters:
    """Subtract six supplied baselines; no clamp, wrap correction or Hz scaling.

    Original frame 0 reads three VAM-A counters; frame 1 reads BVID/BVAR/BEVE.
    Neither subtraction adds an elapsed-time divisor. Baseline initialization
    and atomicity of these separate reads remain caller/external contracts.
    """

    if not all(isinstance(value, MonitoringCounters) for value in (current, previous)):
        raise TypeError("current and previous must be MonitoringCounters")
    return MonitoringCounters(
        **{
            name: _dbl(getattr(current, name), name)
            - _dbl(getattr(previous, name), name)
            for name in MonitoringCounters.__dataclass_fields__
        }
    )


def project_late_numeric(finished_late_previous: bool) -> float:
    """Frame 2 Select is True→0, False→1, despite its alarm comment."""

    return 0.0 if _boolean(finished_late_previous, "finished_late_previous") else 1.0


@dataclass(frozen=True)
class MeanRequest:
    node_uid: int
    supplied_sample: float
    sample_length: int = field(default=5, init=False)
    external_effects_blocked: bool = field(default=True, init=False)


def plan_mean_requests(
    deltas: MonitoringCounters, *, finished_late_previous: bool
) -> tuple[MeanRequest, ...]:
    """Frame 3's seven independent calls, in downstream Time Control slot order.

    This order is bundle-field order, not a claimed order of mean-call execution.
    No moving average or hidden mean history is synthesized.
    """

    if not isinstance(deltas, MonitoringCounters):
        raise TypeError("deltas must be MonitoringCounters")
    samples = (
        project_late_numeric(finished_late_previous),
        deltas.sup_events,
        deltas.sup_variables,
        deltas.sup_video,
        deltas.acq_variables,
        deltas.acq_events,
        deltas.acq_auxiliary,
    )
    return tuple(
        MeanRequest(uid, _dbl(sample, str(uid)))
        for uid, sample in zip(TIME_CONTROL_MEAN_NODE_ORDER, samples, strict=True)
    )


def project_time_control(mean_outputs: Mapping[int, float]) -> tuple[float, ...]:
    """Bundle seven explicitly supplied mean outputs; does not compute means."""

    if not isinstance(mean_outputs, Mapping):
        raise TypeError("mean_outputs must be a mapping keyed by mean node UID")
    if set(mean_outputs) != set(TIME_CONTROL_MEAN_NODE_ORDER):
        raise ValueError("all seven mean node outputs must be explicitly supplied")
    return tuple(
        _dbl(mean_outputs[uid], str(uid)) for uid in TIME_CONTROL_MEAN_NODE_ORDER
    )


@dataclass(frozen=True)
class MonitoringStatus:
    checks: tuple[tuple[str, bool], ...]
    somme_monitoring: bool
    is_physical_interlock: bool = field(default=False, init=False)


def project_monitoring_status(
    deltas: MonitoringCounters, *, finished_late_previous: bool
) -> MonitoringStatus:
    """Frame 4's strict comparisons and inverted late input, without repairs.

    The video check is literal 2>1. Measured sup_video and acq_events deltas do
    not contribute to this AND. The source does not compare averaged values.
    True is the wired Somme Monitoring Boolean, not a safety authorization.
    """

    if not isinstance(deltas, MonitoringCounters):
        raise TypeError("deltas must be MonitoringCounters")
    checks = (
        ("not_finished_late_previous", not _boolean(finished_late_previous, "late")),
        ("sup_events_gt_4", _dbl(deltas.sup_events, "sup_events") > 4.0),
        ("sup_variables_gt_8", _dbl(deltas.sup_variables, "sup_variables") > 8.0),
        ("literal_video_2_gt_1", 2.0 > 1.0),
        ("acq_variables_gt_8", _dbl(deltas.acq_variables, "acq_variables") > 8.0),
        ("acq_auxiliary_gt_8", _dbl(deltas.acq_auxiliary, "acq_auxiliary") > 8.0),
    )
    return MonitoringStatus(checks, all(value for _, value in checks))


@dataclass(frozen=True)
class RadioprotectionRefreshInputs:
    btim: float
    graph_input: RadioprotectionGraph
    somme_radioprotection: bool
    epc: EpcState
    section_pressure: float
    external_effects_blocked: bool = field(default=True, init=False)
    helper_stored_output_supplied: bool = field(default=False, init=False)


def plan_radioprotection_refresh(
    *,
    btim: float,
    graph_input: RadioprotectionGraph,
    somme_radioprotection: bool,
    epc: EpcState,
    section_pressure: float,
) -> RadioprotectionRefreshInputs:
    """Frame 5 caller values; not a graph write or helper-state assumption.

    The helper's retained output is distinct from the caller's graph input and
    must still be explicitly supplied for an unsampled helper projection.
    """

    if not isinstance(graph_input, RadioprotectionGraph) or not isinstance(
        epc, EpcState
    ):
        raise TypeError("graph_input and epc must be explicit graph/EPC records")
    return RadioprotectionRefreshInputs(
        _dbl(btim, "btim"),
        graph_input,
        _boolean(somme_radioprotection, "somme_radioprotection"),
        epc,
        _dbl(section_pressure, "section_pressure"),
    )


def project_vacuum_chart(readings: Mapping[str, float]) -> tuple[float, ...]:
    """Frame 7 overwrites all seven graph slots in wired pressure/screen order.

    Existing cluster labels include temperature/setpoint names: they are not
    used to reinterpret these wired sources. No chart history is appended.
    """

    if not isinstance(readings, Mapping):
        raise TypeError("readings must be a mapping of explicitly decoded page fields")
    if any(name not in readings for name in VACUUM_CHART_SOURCE_ORDER):
        raise ValueError("all seven vacuum-chart sources must be supplied")
    return tuple(_dbl(readings[name], name) for name in VACUUM_CHART_SOURCE_ORDER)


@dataclass(frozen=True)
class GuideHfChartSample:
    supplied_value: float
    control: str = field(default="Graphe déroulant", init=False)
    source_field: str = field(default="12 ACQ Vide PI Guide HF", init=False)
    external_effects_blocked: bool = field(default=True, init=False)


def plan_guide_hf_chart_sample(supplied_value: float) -> GuideHfChartSample:
    """Frame 8's scalar sample intent; no chart history or device read occurs."""

    return GuideHfChartSample(_dbl(supplied_value, "supplied_value"))
