"""Static, non-executable topology record for ``0_SUP_ELYSE.vi``.

This module deliberately models *evidence*, not a replacement control system.
It does not schedule loops, service UI events, dereference PSP URLs, communicate
with controllers, or issue a shutdown/abort command.  Every operational
boundary remains explicit so a caller cannot accidentally treat this inventory
as an approved runtime orchestration layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class LifecycleStage(IntEnum):
    """Visible frame indices of outer sequence structure uid 988."""

    LOCAL_UI_SETUP = 0
    INITIALIZATION = 1
    RUN_CONCURRENT_LOOPS = 2
    RELEASE_RESOURCES = 3
    POST_LOOP_DERIVED_VALUES = 4


@dataclass(frozen=True)
class OrchestrationEvidenceBlock:
    vi_name: str
    conversion_state: str
    implementation_allowed: bool
    unresolved_boundaries: tuple[str, ...]


@dataclass(frozen=True)
class LifecyclePlan:
    stage: LifecycleStage
    observed_topology: str
    external_effects_blocked: bool


@dataclass(frozen=True)
class EventCasePlan:
    index: int
    selector_label: str
    boundary: str
    bounded_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimedLoopFramePlan:
    index: int
    observed_topology: str


@dataclass(frozen=True)
class StopDependencyPlan:
    signal: str
    observed_dependents: tuple[str, ...]
    release_order: tuple[str, ...]
    guarantee_not_proven: str


@dataclass(frozen=True)
class ControllerBoundaryPlan:
    logical_group: str
    observed_variable: str
    observed_meaning: str
    transport_or_hardware_contract: str


@dataclass(frozen=True)
class DirectCalleeInventory:
    hierarchy_or_text_candidates: tuple[str, ...]
    minimum_proven_direct_names: tuple[str, ...]
    known_instance_counts: tuple[tuple[str, int], ...]
    completeness_proven: bool


@dataclass(frozen=True)
class SupervisionOrchestrationPlan:
    """Immutable top-level topology; no member is an executable operation."""

    outer_sequence_uid: int
    lifecycle: tuple[LifecyclePlan, ...]
    parallel_loop_topology: tuple[str, ...]
    event_structure_uid: int
    event_cases: tuple[EventCasePlan, ...]
    timed_sequence_uid: int
    timed_loop_frames: tuple[TimedLoopFramePlan, ...]
    timing_labels: tuple[str, ...]
    command_state_boundaries: tuple[str, ...]
    stop_dependency: StopDependencyPlan
    controller_boundaries: tuple[ControllerBoundaryPlan, ...]
    direct_callees: DirectCalleeInventory
    blocked: OrchestrationEvidenceBlock


ORCHESTRATION_BLOCKED = OrchestrationEvidenceBlock(
    vi_name="0_SUP_ELYSE.vi",
    conversion_state="failed",
    implementation_allowed=False,
    unresolved_boundaries=(
        "all 34 event indices have bounded pure models; complete frame "
        "reconciliation, binary event/property semantics and concurrent runtime "
        "remain unqualified",
        "PSP ownership, field layout, acknowledgement, stale-data, retry, "
        "and timeout contracts",
        "Tango, DAQ, NI-DAQmx, VISA, CmdLib/Picomotor, camera/IMAQ, "
        "filesystem, and System Exec effects",
        "controller addresses, engineering units, scaling, polarity, limits, "
        "interlocks, and safe states",
        "TIR/PRE-TIR/VEILLE/ARRET command transition ownership "
        "and acquisition-host behavior",
        "global-stop reachability, failure propagation, "
        "and hardware-safe-state equivalence",
    ),
)


LIFECYCLE: tuple[LifecyclePlan, ...] = (
    LifecyclePlan(
        LifecycleStage.LOCAL_UI_SETUP,
        "outer frame 0: local/front-panel state and command-display topology",
        True,
    ),
    LifecyclePlan(
        LifecycleStage.INITIALIZATION,
        "outer frame 1: initialization sequence, including local setup "
        "and external-resource preparation branches",
        True,
    ),
    LifecyclePlan(
        LifecycleStage.RUN_CONCURRENT_LOOPS,
        "outer frame 2: main event, timed-monitoring, "
        "and NI1409/camera loop topology coexist",
        True,
    ),
    LifecyclePlan(
        LifecycleStage.RELEASE_RESOURCES,
        "outer frame 3: independent PSP/IMAQ/CmdLib resource chains and stop=False; "
        "13 PSP references, nine image buffers, one addressed AbortMotion→Shutdown; "
        "PSP error shift register uninitialized; see lifecycle_tail",
        True,
    ),
    LifecyclePlan(
        LifecycleStage.POST_LOOP_DERIVED_VALUES,
        "outer frame 4 POUBELLE: 15 retired formulas, all inputs zero-wired and "
        "no output consumers; not live calibration/PSP reads; see lifecycle_tail",
        True,
    ),
)


_EVENT_LABELS = (
    "Timeout",
    "Fréquence machine: value change",
    "AXE H, GAP H: value change",
    "Translateurs: value change",
    "Faraday: value change",
    "Fentes: value change",
    "Page Synchronisation: value change",
    "Position diagnostique T1: value change",
    "Position Miroir Laser: value change",
    "Position Faraday 1: value change",
    "Position Faraday 2: value change",
    "Position Faraday 3: value change",
    "Position diagnostique T2: value change",
    "Position diagnostique T3: value change",
    "Page Fluides: value change",
    "Page HT: value change",
    "Page HF: value change",
    "Page Alimentations: value change",
    "Page Modulateur: value change",
    "Voie directe: value change",
    "Voie déviée: value change",
    "Outils vidéo: value change",
    "LOAD: value change",
    "VALIDER LOAD: value change",
    "Seuil BLANC (V), Seuil NOIR (V): mouse up",
    "Voies NI1409: value change",
    "Moyenne CxCy: value change",
    "Initialisation: value change",
    "Move forward X, Move forward Y: value change",
    "Move reverse X, Move reverse Y: value change",
    "autotune: value change",
    "Tree: value change",
    "Densité optique: value change",
    "Save img0: value change",
)


def _event_boundary(index: int) -> str:
    if index == 0:
        return (
            "14 PSP read intents, counter selection/reset/publish, 66 UI patches "
            "and ROI/date/motor selector modeled in timeout_events; scheduling, "
            "freshness, coercions/defaults and all external effects blocked"
        )
    if index == 1:
        return (
            "machine-frequency cluster replacement and fan-out intent modeled "
            "in machine_frequency; PSP execution blocked"
        )
    if index == 2:
        return (
            "AXE H/GAP H arithmetic and C9NI6703 patch modeled in slit_position; "
            "PSP execution blocked"
        )
    if index == 3:
        return (
            "Arrêt topology/neutral loop expression modeled in translator_stop; "
            "Laser/T1/T2/T3 C5 true-only patches/color/2000 ms intents modeled "
            "in translator_selection; native stop-loop direction unresolved, "
            "all PSP/timing/hardware effects blocked"
        )
    if index in (4, 5, 8, 9, 10, 11):
        return (
            "Faraday/slit-supply/laser digital patches, empty branches, frame "
            "order/color/reset modeled in digital_command_events; waits are "
            "intents only, all PSP/hardware effects blocked, states unproven"
        )
    if index == 6:
        return (
            "33-DBL OldVal-minus-NewVal selection, fresh-local fan-out, busy "
            "discard/300 ms/property/result modeled in synchronisation_events; "
            "binary decoding, error aggregation/formatting and all "
            "counter/PSP/UI effects blocked"
        )
    if index in (14, 15, 16):
        return (
            "Fluides/HT/HF 20 arrow rules, limits, 9 DPS flags, busy-bypassing "
            "arrow guard, quirks, UI base/reset and timing intents modeled "
            "in parameter_page_events; multi-bit no-op, unordered sinks, "
            "binary/PSP/hardware effects and modern safety policy blocked"
        )
    if index in (17, 18):
        return (
            "Alimentations/modulator NewVal fields, whole-DPS busy discard, "
            "unordered fan-out, TER and outside-guard Wait(200/0) modeled "
            "in page_command_events; binary decoding, acknowledgements, "
            "current ownership and all runtime effects blocked"
        )
    if index in (19, 20):
        return (
            "four-frame direct/diverted setpoint arithmetic/controller intent "
            "modeled in beamline_commands; all PSP/hardware effects blocked"
        )
    if index in (7, 12, 13):
        return (
            "T1/T2/T3 constants, C9NI6703 patch/x10 display modeled in "
            "diagnostic_events; native default corrected from Print, "
            "unsupported selectors and all PSP/motion effects blocked"
        )
    if index == 26:
        return (
            "Init moy CxCy True -> 200 ms -> False modeled in diagnostic_events; "
            "no mutation/sleep, reader observation/buffer reset unproven"
        )
    if index in (22, 23, 31):
        return (
            "load/cache/dialog/tree/display modeled in load_events; event 23 "
            "discards ten file-read outputs, applies no equipment preset; "
            "file format, conversions and all filesystem/UI effects blocked"
        )
    if index in (21, 24, 25, 32, 33):
        return (
            "mask/zoom/ROI, camera sequences, dead density branch and "
            "cancellation-aware TIFF intents modeled in video_events; image "
            "identity, camera/property results and external effects blocked"
        )
    if index in (27, 28, 29):
        return (
            "motor/camera discovery, four-axis zeroing, signed jog/poll/abort "
            "and error-journal intents modeled in motion_events; no NewVal "
            "guard/timeout invented; units, limits/protocol/drivers blocked"
        )
    if index == 30:
        return (
            "motor/camera eight-frame switches, four centroid stages, 249..251 "
            "decisions/asymmetric connectors/Y-only stop modeled in "
            "autotune_events; freshness, defaults, error/unlimited convergence "
            "semantics and all runtime effects blocked"
        )
    raise ValueError("unknown main Event Structure index")


EVENT_MODEL_MODULES: tuple[tuple[str, ...], ...] = (
    ("timeout_events",),
    ("machine_frequency",),
    ("slit_position",),
    ("translator_stop", "translator_selection"),
    ("digital_command_events",),
    ("digital_command_events",),
    ("synchronisation_events",),
    ("diagnostic_events",),
    ("digital_command_events",),
    ("digital_command_events",),
    ("digital_command_events",),
    ("digital_command_events",),
    ("diagnostic_events",),
    ("diagnostic_events",),
    ("parameter_page_events",),
    ("parameter_page_events",),
    ("parameter_page_events",),
    ("page_command_events",),
    ("page_command_events",),
    ("beamline_commands",),
    ("beamline_commands",),
    ("video_events",),
    ("load_events",),
    ("load_events",),
    ("video_events",),
    ("video_events",),
    ("diagnostic_events",),
    ("motion_events",),
    ("motion_events",),
    ("motion_events",),
    ("autotune_events",),
    ("load_events",),
    ("video_events",),
    ("video_events",),
)


EVENT_CASES: tuple[EventCasePlan, ...] = tuple(
    EventCasePlan(index, label, _event_boundary(index), EVENT_MODEL_MODULES[index])
    for index, label in enumerate(_EVENT_LABELS)
)


TIMED_LOOP_FRAMES: tuple[TimedLoopFramePlan, ...] = (
    TimedLoopFramePlan(
        0,
        "acquisition-loop frequency/counter values for auxiliary, variables, "
        "event, and vacuum/video paths",
    ),
    TimedLoopFramePlan(1, "supervision-loop frequency values from BVID, BVAR, and BEV"),
    TimedLoopFramePlan(
        2, "Boolean/0-1 path writes label Alarme de la boucle cadencée à 2 Hz"
    ),
    TimedLoopFramePlan(
        3, "mean calculations with visible window constant 5; Time Control write"
    ),
    TimedLoopFramePlan(
        4,
        "strict delta thresholds/inverted Finished Late AND; literal video 2>1, "
        "not measured video rate; see timed_monitoring",
    ),
    TimedLoopFramePlan(
        5, "radioprotection graph assembly from BTIM/EPC/Page Vide/Lec Vide SECTION"
    ),
    TimedLoopFramePlan(6, "empty frame"),
    TimedLoopFramePlan(7, "Graphe VIDE assembly from named vacuum/screen readings"),
    TimedLoopFramePlan(
        8, "VAM-A channel 12 ACQ Vide P1 Guide HF routed to Graphe déroulant"
    ),
)


STOP_DEPENDENCY = StopDependencyPlan(
    signal="lowercase stop (distinct from stop motor)",
    observed_dependents=(
        "main Event Structure loop termination condition",
        "timed monitoring loop termination condition",
        "NI1409 camera loop termination condition",
    ),
    release_order=("addressed CmdLib8742.AbortMotion", "CmdLib8742.Shutdown"),
    guarantee_not_proven=(
        "all global-stop paths reach release region; upstream abort-error "
        "behavior; all motor/axis coverage; "
        "controller or hardware safe state"
    ),
)


CONTROLLER_BOUNDARIES: tuple[ControllerBoundaryPlan, ...] = (
    ControllerBoundaryPlan(
        "digital commands",
        "C5_OUT_DIO96",
        "screens, cameras, lighting, Faraday cups, laser mirror, slit supply",
        "PSP only; downstream transport and physical endpoint unresolved",
    ),
    ControllerBoundaryPlan(
        "direct-line analog commands",
        "C6NI6703",
        "H1/V1, H2/V2, H3/V3 correctors",
        "PSP only; unit/scaling/polarity/range unresolved",
    ),
    ControllerBoundaryPlan(
        "direct/diverted magnets",
        "C7NI6703",
        "dipoles, solenoid/focal element, quadrupoles, triplets",
        "PSP only; unit/scaling/polarity/range unresolved",
    ),
    ControllerBoundaryPlan(
        "RF/temperature commands",
        "C8NI6703",
        "HF phase/attenuator and gun/section temperature commands",
        "PSP only; unit/scaling/polarity/range unresolved",
    ),
    ControllerBoundaryPlan(
        "position commands",
        "C9NI6703",
        "slits and diagnostic-screen translator positions",
        "PSP only; controller/axis limits and interlocks unresolved",
    ),
    ControllerBoundaryPlan(
        "synchronization",
        "C10-11NI6602",
        "machine-frequency/counter selection and delay/width data",
        "PSP only; DAQ timing and hardware semantics unresolved",
    ),
    ControllerBoundaryPlan(
        "command/status bank",
        "DPS",
        "cooling, magnet supplies, HT, HF, and modulator command/status fields",
        "PSP only; ownership/acknowledgement/interlock semantics unresolved",
    ),
    ControllerBoundaryPlan(
        "analog measurements",
        "C1NI6071E",
        "magnetic measurements for direct and diverted beam lines",
        "PSP only; acquisition/scaling/staleness semantics unresolved",
    ),
)


DIRECT_CALLEES = DirectCalleeInventory(
    hierarchy_or_text_candidates=(
        "Shutdown.vi",
        "sous vi LigneCentroide2.vi",
        "Error Cluster From Error Code.vi",
        "2_SUP_Ecart_lu_ecr_VDéviée.vi",
        "2_SUP_Ecart_lu_ecr_VDirecte.vi",
        "2_SUP_marche_default_VIDE.vi",
        "2_SUP_Graph_Radioprot.vi",
        "Boîte de dialogue de fichier",
        "SetZeroPosition.vi",
        "GetIdentification.vi",
        "InitSingleDevice.vi",
        "System Exec.vi",
        "3_SUP_en_défaut_alims.vi",
        "AbortMotion.vi",
        "Moteurs SdC GoTo.vi",
    ),
    minimum_proven_direct_names=(
        "Shutdown.vi",
        "AbortMotion.vi",
        "Moteurs SdC GoTo.vi",
        "sous vi LigneCentroide2.vi",
    ),
    known_instance_counts=(
        ("AbortMotion.vi", 3),
        ("Moteurs SdC GoTo.vi", 8),
        ("sous vi LigneCentroide2.vi", 1),
    ),
    completeness_proven=False,
)


def build_supervision_orchestration_plan() -> SupervisionOrchestrationPlan:
    """Return the static reconstruction record without observing any runtime state."""

    return SupervisionOrchestrationPlan(
        outer_sequence_uid=988,
        lifecycle=LIFECYCLE,
        parallel_loop_topology=(
            "main Event Structure loop (event structure uid 5909)",
            "timed monitoring loop (timed sequence uid 16409)",
            "NI1409/camera loop",
        ),
        event_structure_uid=5909,
        event_cases=EVENT_CASES,
        timed_sequence_uid=16409,
        timed_loop_frames=TIMED_LOOP_FRAMES,
        timing_labels=(
            "1 kHz timing base",
            "dt 1000",
            "Alarme de la boucle cadencée à 2 Hz",
        ),
        command_state_boundaries=(
            "TIR, PRE-TIR, VEILLE, ARRET, and STOP are not selector labels "
            "of the 34-case main Event Structure",
            "named state-transition ownership may be enum/generic/dynamic/"
            "controller-side; no top-level transition is claimed",
            "cases 19/20 are command-boundary topology only, "
            "not approved direct/diverted control",
        ),
        stop_dependency=STOP_DEPENDENCY,
        controller_boundaries=CONTROLLER_BOUNDARIES,
        direct_callees=DIRECT_CALLEES,
        blocked=ORCHESTRATION_BLOCKED,
    )


def validate_supervision_orchestration_plan(plan: SupervisionOrchestrationPlan) -> None:
    """Reject altered evidence identities; this validates inventory consistency only."""

    if not isinstance(plan, SupervisionOrchestrationPlan):
        raise TypeError("plan must be SupervisionOrchestrationPlan")
    if plan.outer_sequence_uid != 988 or tuple(
        item.stage.value for item in plan.lifecycle
    ) != tuple(range(5)):
        raise ValueError(
            "outer lifecycle evidence must be exactly sequence 988 frames 0..4"
        )
    if plan.event_structure_uid != 5909 or tuple(
        item.index for item in plan.event_cases
    ) != tuple(range(34)):
        raise ValueError(
            "main event evidence must be exactly event structure 5909 cases 0..33"
        )
    if plan.timed_sequence_uid != 16409 or tuple(
        item.index for item in plan.timed_loop_frames
    ) != tuple(range(9)):
        raise ValueError("timed evidence must be exactly sequence 16409 frames 0..8")
    if plan.stop_dependency.release_order != (
        "addressed CmdLib8742.AbortMotion",
        "CmdLib8742.Shutdown",
    ):
        raise ValueError(
            "release-order evidence must retain AbortMotion before Shutdown"
        )
    if plan.blocked.implementation_allowed or plan.blocked.conversion_state != "failed":
        raise ValueError(
            "the orchestration inventory must remain non-executable and failed"
        )
