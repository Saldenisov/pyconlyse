"""Static, non-executable reconstruction of the Translateurs ``Arrêt`` branch.

The record below describes only ``0_SUP_ELYSE.vi`` event structure uid 5909,
case 3 (``\"Translateurs\": Value Change``), selector uid 56667, case value
0 (``Arrêt``), and sequence uid 71948.  It is an evidence model, not an
equipment command API: it cannot open a PSP connection, send a write, sleep,
read a controller, alter a UI, or invoke an error handler.

Sequence-frame order is evidenced.  Dataflow order *inside* a frame is not
invented: the tab ``Colors`` property write and the dynamic shared-variable
write in frames 0 and 3 have no proven dependency, and the 100 ms wait has no
proven dependency on the three comparisons in the polling loop.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


SOURCE_VI_SHA256 = (
    "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
)
SOURCE_LIBRARY_PATH = "Supervision/source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb"
SOURCE_LIBRARY_SHA256 = (
    "D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4"
)
REVIEWED_EXTRACTED_COPY_SHA256 = (
    "2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B"
)

LVKIT_DESCRIPTION_PATH = (
    "Supervision/analysis/lvkit_eval/batch_0_8_4_minimal_vilib/descriptions/"
    "0_SUP_ELYSE.json"
)
LVKIT_DESCRIPTION_SHA256 = (
    "AA620AA9E6FE4312F555A4C5A096B51EE54FE5F34214EE17DDBF9CC2822B8710"
)
STATIC_AUDIT_PATH = "Supervision/analysis/all_frame_static_audit.csv"
EVENT_FRAME_PATHS_PATH = "Supervision/analysis/event_frame_paths.csv"
LOOP_LEDGER_PATH = "Supervision/analysis/expected_loop_body_ledger.csv"
NAMED_CAPTURE_PATH = (
    "Supervision/analysis/screenshots/"
    "0_SUP_ELYSE_outer_frame_2_event_case_03_full.png"
)
NAMED_CAPTURE_SHA256 = (
    "313355BF2DF0701B4BC3DA60DE09A040335D3067BC9B2D1F18D86EC0BC80B838"
)


@dataclass(frozen=True)
class DigitalAssignment:
    """One named field assignment in the WCM5G digital cluster."""

    field: str
    value: bool


@dataclass(frozen=True)
class ScreenPositionAssignment:
    """One evidenced numerical command field in the WCM5D cluster."""

    field: str
    value: float


@dataclass(frozen=True)
class TabColorWrite:
    """Raw LabVIEW ``Colors`` property value; color interpretation is unproved."""

    control_name: str
    property_name: str
    raw_value: int


@dataclass(frozen=True)
class SharedVariableWriteBoundary:
    """A write-shaped graph boundary, retained without a transport implementation."""

    logical_variable: str
    connection_refnum: int
    psp_url: str | None
    assignments: tuple[DigitalAssignment | ScreenPositionAssignment, ...]
    simple_error_handler_follows_write: bool
    external_effects_blocked: bool
    manual_approval_required: bool
    target_limit: str


@dataclass(frozen=True)
class PollingSelectorExpression:
    """Observed Boolean selector topology for while-loop uid 80242.

    The native loop-terminal direction is not decoded.  A ``True`` expression
    must not be interpreted as either stop or continue.
    """

    wait_ms: int
    iteration_comparison_threshold: int
    measurement_comparison_threshold: float
    measurement_names: tuple[str, str, str]
    expression: str
    termination_semantics: str
    within_iteration_order_not_proven: str


@dataclass(frozen=True)
class SequenceFramePlan:
    """One sequential frame; actions within ``topology`` are not an executor."""

    index: int
    topology: tuple[str, ...]
    tab_color_write: TabColorWrite | None = None
    shared_variable_write: SharedVariableWriteBoundary | None = None
    polling_selector: PollingSelectorExpression | None = None


@dataclass(frozen=True)
class TranslatorStopPlan:
    """Immutable description of the selected ``Arrêt`` event branch."""

    vi_name: str
    source_vi_sha256: str
    source_library_path: str
    source_library_sha256: str
    event_structure_uid: int
    event_case_index: int
    event_label: str
    selector_uid: int
    selector_case_index: int
    selector_case_label: str
    sequence_uid: int
    frames: tuple[SequenceFramePlan, ...]
    visual_frame_mapping_status: str
    manual_capture_shows_default: bool
    lvkit_reports_default: bool
    reviewed_extracted_copy_sha256: str
    extracted_copy_matches_evidence_source: bool
    implementation_allowed: bool
    unresolved_semantics: tuple[str, ...]


_DIGITAL_START_ASSIGNMENTS: tuple[DigitalAssignment, ...] = (
    DigitalAssignment("01 CPB1 b79 Alimentation moteur", True),
    DigitalAssignment("03 CPB3 b75 M/A Caméra chambre de préparation", False),
    DigitalAssignment("05 CPB5 b71 M/A Caméra Miroir", False),
    DigitalAssignment("07 CPB7 b67 M/A Eclairage Ecran 1", False),
    DigitalAssignment("09 CPC1 b63 M/A Caméra Ecran 1", False),
    DigitalAssignment("13 CPC5 b55 M/A Eclairage Ecran 2", False),
    DigitalAssignment("15 CPC7 b51 M/A Caméra Ecran 2", False),
    DigitalAssignment("19 DPA3 b92 M/A Eclairage Ecran 3", False),
    DigitalAssignment("21 DPA5 b88 M/A Caméra Ecran 3", False),
    DigitalAssignment("31 DPB7 b68 M/A Alimentation Ecrans", True),
    DigitalAssignment("26 DPB2 b78 Cmd Miroir LASER HORS", True),
)

_DIGITAL_STOP_ASSIGNMENTS: tuple[DigitalAssignment, ...] = tuple(
    DigitalAssignment(assignment.field, False) for assignment in _DIGITAL_START_ASSIGNMENTS
)

_SCREEN_STOP_ASSIGNMENTS: tuple[ScreenPositionAssignment, ...] = (
    ScreenPositionAssignment("04 OUT04 b17 Cmd position translateur Ecran 1", 2.126),
    ScreenPositionAssignment("05 OUT05 b21 Cmd position translateur Ecran 2", 2.126),
    ScreenPositionAssignment("06 OUT06 b25 Cmd position translateur Ecran 3", 2.126),
)

POLLING_SELECTOR_EXPRESSION = PollingSelectorExpression(
    wait_ms=100,
    iteration_comparison_threshold=1200,
    measurement_comparison_threshold=22.7,
    measurement_names=("Position Miroir Laser", "Etat T1", "Etat MLaser EN"),
    expression=(
        "(While Loop iteration > 1200) OR "
        "((Position Miroir Laser < 22.7) AND (Etat T1 < 22.7) "
        "AND (Etat MLaser EN < 22.7))"
    ),
    termination_semantics="NATIVE_UNVERIFIED",
    within_iteration_order_not_proven=(
        "Wait (ms)=100 and the comparison nodes are both present in loop uid 80242, "
        "but no dataflow edge serializes the wait before the comparisons."
    ),
)


EXPECTED_TRANSLATOR_STOP_FRAMES: tuple[SequenceFramePlan, ...] = (
    SequenceFramePlan(
        index=0,
        topology=(
            "Translateurs.Colors raw property write; no dependency to the cluster write proven",
            "bundle WCM5G fields then sharedVariableDynamicWrite; Simple Error Handler follows its error output",
            "set Somme Vide=0, Somme Synchro=1, VALIDER LOAD=0, and Somme Fluide=0",
        ),
        tab_color_write=TabColorWrite("Translateurs", "Colors", 7171459),
        shared_variable_write=SharedVariableWriteBoundary(
            logical_variable="WCM5G:",
            connection_refnum=47,
            psp_url="ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96",
            assignments=_DIGITAL_START_ASSIGNMENTS,
            simple_error_handler_follows_write=True,
            external_effects_blocked=True,
            manual_approval_required=True,
            target_limit=(
                "The named capture exposes C5_OUT_DIO96 for this frame; controller ownership, "
                "physical endpoints, acknowledgement, and safe-state semantics are not proven."
            ),
        ),
    ),
    SequenceFramePlan(
        index=1,
        topology=(
            "bundle three screen-translator fields at literal 2.126",
            "sharedVariableDynamicWrite then Simple Error Handler on its error output",
        ),
        shared_variable_write=SharedVariableWriteBoundary(
            logical_variable="WCM5D:",
            connection_refnum=43,
            psp_url=None,
            assignments=_SCREEN_STOP_ASSIGNMENTS,
            simple_error_handler_follows_write=True,
            external_effects_blocked=True,
            manual_approval_required=True,
            target_limit=(
                "The initialization graph associates Refnum(43) with WCM5D:, but its PSP URL is not "
                "captured in this branch; no destination or actuator semantics are asserted."
            ),
        ),
    ),
    SequenceFramePlan(
        index=2,
        topology=(
            "while loop uid 80242 with a Wait (ms) literal 100 and an OR selector expression",
            "native loop-terminal direction is unverified",
            "no serial ordering between the wait and comparison nodes is proven",
        ),
        polling_selector=POLLING_SELECTOR_EXPRESSION,
    ),
    SequenceFramePlan(
        index=3,
        topology=(
            "Translateurs.Colors raw property write; no dependency to the cluster write proven",
            "bundle WCM5G fields false then sharedVariableDynamicWrite; Simple Error Handler follows its error output",
        ),
        tab_color_write=TabColorWrite("Translateurs", "Colors", 12171705),
        shared_variable_write=SharedVariableWriteBoundary(
            logical_variable="WCM5G:",
            connection_refnum=47,
            psp_url="ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96",
            assignments=_DIGITAL_STOP_ASSIGNMENTS,
            simple_error_handler_follows_write=True,
            external_effects_blocked=True,
            manual_approval_required=True,
            target_limit=(
                "The named capture identifies C5_OUT_DIO96 only for frame 0; the Refnum(47)/WCM5G: "
                "topology is static evidence, not a permitted or behaviorally verified write."
            ),
        ),
    ),
)


def evaluate_translator_loop_selector(
    *,
    iteration: int,
    position_miroir_laser: Real,
    etat_t1: Real,
    etat_mlaser_en: Real,
) -> bool:
    """Evaluate only the evidenced Boolean selector expression.

    This helper neither waits nor reads a process value.  Its return value is
    not a stop decision because the native loop-terminal direction remains
    unverified.  Callers must not use it as an approval to control hardware.
    """

    if isinstance(iteration, bool) or not isinstance(iteration, int):
        raise TypeError("iteration must be an already-resolved integer loop index")
    values = (position_miroir_laser, etat_t1, etat_mlaser_en)
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise TypeError("measurement values must be already-resolved real numbers")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("measurement values must be finite")
    return iteration > POLLING_SELECTOR_EXPRESSION.iteration_comparison_threshold or all(
        value < POLLING_SELECTOR_EXPRESSION.measurement_comparison_threshold
        for value in values
    )


def build_translator_stop_plan() -> TranslatorStopPlan:
    """Return the static ``Translateurs`` stop plan without performing any effect."""

    return TranslatorStopPlan(
        vi_name="0_SUP_ELYSE.vi",
        source_vi_sha256=SOURCE_VI_SHA256,
        source_library_path=SOURCE_LIBRARY_PATH,
        source_library_sha256=SOURCE_LIBRARY_SHA256,
        event_structure_uid=5909,
        event_case_index=3,
        event_label='[3] "Translateurs": Value Change',
        selector_uid=56667,
        selector_case_index=0,
        selector_case_label="      Arrêt ",
        sequence_uid=71948,
        frames=EXPECTED_TRANSLATOR_STOP_FRAMES,
        visual_frame_mapping_status="UNMAPPED",
        manual_capture_shows_default=True,
        lvkit_reports_default=False,
        reviewed_extracted_copy_sha256=REVIEWED_EXTRACTED_COPY_SHA256,
        extracted_copy_matches_evidence_source=False,
        implementation_allowed=False,
        unresolved_semantics=(
            "Print PNG order cannot be joined deterministically to lvkit UIDs; this branch is STATIC_EXTRACTED_VISUAL_UNCONFIRMED, not visually frame-verified.",
            "The current extracted VI copy differs from the source hash bound to the saved evidence corpus.",
            "The manual capture visually shows Arrêt as Default while lvkit reports is_default=False; neither observation resolves selector-default semantics because the capture provenance is not bound to the evidence-source hash and the PNG ledger remains UNMAPPED.",
            "The WCM5D: PSP URL, controller ownership, units and physical meaning of 2.126 are not captured.",
            "LabVIEW numeric coercion, NaN behavior, loop initial iteration, elapsed-time guarantee, and process-value freshness are unresolved.",
            "The 22.7 threshold units and whether the three values are safe/complete state indications are unresolved.",
            "Simple Error Handler display, propagation, and recovery semantics are not reconstructed.",
            "No assignment establishes a hardware-safe state without an approved controller and interlock contract.",
        ),
    )


def validate_translator_stop_plan(plan: TranslatorStopPlan) -> None:
    """Validate evidence identities and fail closed on an altered immutable plan."""

    if not isinstance(plan, TranslatorStopPlan):
        raise TypeError("plan must be TranslatorStopPlan")
    if plan != build_translator_stop_plan():
        raise ValueError("translator stop plan differs from the complete canonical evidence model")
    if (
        plan.vi_name != "0_SUP_ELYSE.vi"
        or plan.source_vi_sha256 != SOURCE_VI_SHA256
        or plan.source_library_path != SOURCE_LIBRARY_PATH
        or plan.source_library_sha256 != SOURCE_LIBRARY_SHA256
        or (plan.event_structure_uid, plan.event_case_index) != (5909, 3)
        or (plan.selector_uid, plan.selector_case_index) != (56667, 0)
        or plan.sequence_uid != 71948
    ):
        raise ValueError("translator stop evidence identities must remain unchanged")
    if plan.frames != EXPECTED_TRANSLATOR_STOP_FRAMES:
        raise ValueError("sequence uid 71948 must retain every evidenced frame field exactly")
    start, positions, poll, release = plan.frames
    if plan.visual_frame_mapping_status != "UNMAPPED" or plan.implementation_allowed:
        raise ValueError("the reconstructed branch must remain non-executable and visually unmapped")
    if not plan.manual_capture_shows_default or plan.lvkit_reports_default:
        raise ValueError("manual/lvkit selector-default conflict must remain explicit")
    if plan.extracted_copy_matches_evidence_source or plan.reviewed_extracted_copy_sha256 != REVIEWED_EXTRACTED_COPY_SHA256:
        raise ValueError("extracted-copy hash mismatch must remain explicit")
    for frame in (start, positions, release):
        write = frame.shared_variable_write
        if write is None or not write.external_effects_blocked or not write.manual_approval_required:
            raise ValueError("every shared-variable write boundary must remain blocked and approval-gated")
