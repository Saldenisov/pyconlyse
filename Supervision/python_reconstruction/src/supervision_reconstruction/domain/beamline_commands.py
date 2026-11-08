"""Pure command-intent model for ``0_SUP_ELYSE.vi`` events 19 and 20.

The legacy events edit one channel inside the ``Voie directe`` or
``Voie déviée`` front-panel cluster, copy the resulting setpoint into one
field of a controller cluster, write the four analog-command cluster
boundaries, and wait for the Shared Variable Engine to refresh.  This module
models only the evidenced arithmetic and routing intent.  It cannot write a
PSP variable, acknowledge a controller, or command accelerator hardware.

Evidence identities retained by the model:

* main Event Structure uid 5909, cases 19 and 20;
* four-frame sequences uids 14098 and 33504;
* action selectors uids 8243 and 34080; this model covers their evidenced
  setpoint branches 128/256/512/1024 and deliberately excludes 0/1/16;
* 70 ms momentary-button reset dependencies uids 9278 and 46451;
* controller-copy gates uids 11830 and 46564;
* final 100 ms waits uids 26814 and 27840.

The named manual screenshots prove the visible frame-0 wiring.  The saved
LabVIEW Print and lvkit description provide the remaining structure and field
names.  Runtime acknowledgement, stale-data behavior, simultaneous-change
arbitration, and the association of all four refnums with deployed PSP URLs
remain outside this model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
import math


class BeamLine(str, Enum):
    DIRECT = "direct"
    DEVIATED = "deviated"


class AdjustmentAction(IntEnum):
    """Observed selector values for the four momentary adjustment buttons."""

    LARGE_DECREASE = 128
    SMALL_DECREASE = 256
    SMALL_INCREASE = 512
    LARGE_INCREASE = 1024


@dataclass(frozen=True)
class ControllerField:
    observed_variable: str
    legacy_field: str


@dataclass(frozen=True)
class ChannelAdjustmentRule:
    index: int
    legacy_name: str
    minimum: float
    maximum: float
    small_step: tuple[float, float]
    large_step: tuple[float, float]
    destination: ControllerField
    crosswalk_status: str = "STATIC_FIELD_MATCH"
    crosswalk_label_match: bool = True


@dataclass(frozen=True)
class BeamLineEvidenceIdentity:
    event_case_index: int
    sequence_uid: int
    action_selector_uid: int
    momentary_reset_uid: int
    controller_copy_gate_uid: int
    final_wait_uid: int
    screenshot: str
    screenshot_sha256: str
    source_library_path: str
    source_library_sha256: str
    source_vi_sha256: str
    reviewed_extracted_copy_sha256: str
    extracted_copy_matches_evidence_source: bool
    expected_key_sha256: str
    formal_png_mapping_status: str
    crosswalk_path: str
    crosswalk_sha256: str
    print_assets: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BeamLineAdjustmentPlan:
    """Non-executable intent produced after one legacy button is resolved."""

    beam_line: BeamLine
    channel_index: int
    channel_name: str
    action: AdjustmentAction
    x10_selected: bool
    original_setpoint: float
    step: float
    requested_setpoint: float
    coerced_setpoint: float
    was_coerced: bool
    controller_patch: ControllerField
    crosswalk_status: str
    crosswalk_label_match: bool
    adapter_use_allowed: bool
    momentary_button_reset_after_ms: int
    sve_refresh_wait_ms: int
    observed_full_cluster_write_boundary: tuple[str, ...]
    ordering_within_write_boundary_proven: bool
    external_effects_blocked: bool
    manual_approval_required: bool
    implementation_allowed: bool
    evidence: BeamLineEvidenceIdentity
    unresolved_boundaries: tuple[str, ...]


DIRECT_EVIDENCE = BeamLineEvidenceIdentity(
    event_case_index=19,
    sequence_uid=14098,
    action_selector_uid=8243,
    momentary_reset_uid=9278,
    controller_copy_gate_uid=11830,
    final_wait_uid=26814,
    screenshot="analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_19_full.png",
    screenshot_sha256="283FDDED972B1768313CF83A688D47DC06175C88E2F19F4345711EE5992BFC93",
    source_library_path="source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb",
    source_library_sha256="D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4",
    source_vi_sha256="B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
    reviewed_extracted_copy_sha256="2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B",
    extracted_copy_matches_evidence_source=False,
    expected_key_sha256="B7E552504D4F7A8E84BE44A38469D1AA725D19E89F1859669CA9C877F5126423",
    formal_png_mapping_status="UNMAPPED",
    crosswalk_path="integration_analysis/BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv",
    crosswalk_sha256="BC9209FA7BB6A16702A84A95C0805EBCF815CB267457D9DA356B9A902754C400",
    print_assets=(
        (
            "analysis/labview_print_hidden_frames/0__SUP__ELYSEd347.png",
            "3EA87F99F64A02A248D6DC8CA7C4411E050E8683B54C85342A8F6B1F415987AC",
        ),
        (
            "analysis/labview_print_hidden_frames/0__SUP__ELYSEd350.png",
            "08B206C74FEE6B4773A24E4FCEDCF0FBC4A2FDB897A7921DCA7B1939B0DDA9B3",
        ),
    ),
)

DEVIATED_EVIDENCE = BeamLineEvidenceIdentity(
    event_case_index=20,
    sequence_uid=33504,
    action_selector_uid=34080,
    momentary_reset_uid=46451,
    controller_copy_gate_uid=46564,
    final_wait_uid=27840,
    screenshot="analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_20_full.png",
    screenshot_sha256="C3D7C409E3BD3C4B2183731A67B9B575F94BDACF66CF25A28A6211B54E6B6A87",
    source_library_path="source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb",
    source_library_sha256="D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4",
    source_vi_sha256="B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
    reviewed_extracted_copy_sha256="2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B",
    extracted_copy_matches_evidence_source=False,
    expected_key_sha256="5F1DA21851A1DB07D7FC260EE2471AF80A9A2ABBD8A6027DD3E53F19E0CA07D8",
    formal_png_mapping_status="UNMAPPED",
    crosswalk_path="integration_analysis/BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv",
    crosswalk_sha256="BC9209FA7BB6A16702A84A95C0805EBCF815CB267457D9DA356B9A902754C400",
    print_assets=(
        (
            "analysis/labview_print_hidden_frames/0__SUP__ELYSEd375.png",
            "B94AEEA53BC59D1609BC0B44C2D1C8B40DACA14D76E2CEF5CEC74EE8A400CA54",
        ),
        (
            "analysis/labview_print_hidden_frames/0__SUP__ELYSEd378.png",
            "A379F4917FEB613AA86F1AF5AFB8367E47C708D99D59361AE9FE248234DE9DD4",
        ),
    ),
)


def _field(variable: str, legacy_field: str) -> ControllerField:
    return ControllerField(variable, legacy_field)


DIRECT_CHANNEL_RULES: tuple[ChannelAdjustmentRule, ...] = (
    ChannelAdjustmentRule(0, "Dipôle 1", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "08 OUT08 b33 Cmd I Dipôle 1")),
    ChannelAdjustmentRule(
        1,
        "Focale",
        0.0,
        120.0,
        (0.1, 1.0),
        (1.0, 10.0),
        _field("C7NI6703", "05 OUT05 b21 Cmd I Solénoïde"),
        "LABEL_MISMATCH_VERIFY_MEANING",
        False,
    ),
    ChannelAdjustmentRule(2, "Phase HF / Laser", 0.0, 360.0, (1.0, 5.0), (5.0, 50.0), _field("C8NI6703", "05 OUT05 b21 Cmd déphasage HF/LASER")),
    ChannelAdjustmentRule(3, "Correcteur H1", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "00 OUT00 b01 Cmd Guidage H1")),
    ChannelAdjustmentRule(4, "Correcteur V1", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "01 OUT01 b05 Cmd Guidage V1")),
    ChannelAdjustmentRule(5, "Correcteur H2", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "02 OUT02 b09 Cmd Guidage H2")),
    ChannelAdjustmentRule(6, "Correcteur V2", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "03 OUT03 b13 Cmd Guidage V2")),
    ChannelAdjustmentRule(7, "Triplet 1-1", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "00 OUT00 b01 Cmd I Triplet 1-1")),
    ChannelAdjustmentRule(8, "Triplet 1-2", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "01 OUT01 b05 Cmd I Triplet 1-2")),
    ChannelAdjustmentRule(9, "Correcteur H3", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "04 OUT04 b17 Cmd Guidage H3")),
    ChannelAdjustmentRule(10, "Correcteur V3", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "05 OUT05 b21 Cmd Guidage V3")),
)


DEVIATED_CHANNEL_RULES: tuple[ChannelAdjustmentRule, ...] = (
    ChannelAdjustmentRule(0, "Quadrupôle 1", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "06 OUT06 b25 Cmd I Quad 1")),
    ChannelAdjustmentRule(1, "Quadrupôle 2", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "07 OUT07 b29 Cmd I Quad 2")),
    ChannelAdjustmentRule(2, "Triplet 2-1", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "03 OUT03 b13 Cmd I Triplet 2-1")),
    ChannelAdjustmentRule(3, "Triplet 2-2", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "04 OUT04 b17 Cmd I Triplet 2-2")),
    ChannelAdjustmentRule(4, "Correcteur H4", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "06 OUT06 b25 Cmd Guidage H4")),
    ChannelAdjustmentRule(5, "Correcteur V4", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "07 OUT07 b29 Cmd Guidage V4")),
    ChannelAdjustmentRule(6, "Dipôle 2", -16.0, 16.0, (0.01, 0.1), (0.1, 1.0), _field("C7NI6703", "09 OUT09 b37 Cmd I Dipôle 2")),
    ChannelAdjustmentRule(
        7,
        "Correcteur H5",
        -5.0,
        5.0,
        (0.01, 0.1),
        (0.1, 1.0),
        _field("C6NI6703", "08 OUT08 b33 Réserve"),
        "SCHEMA_RESERVE_UNVERIFIED_ACTUATOR",
        False,
    ),
    ChannelAdjustmentRule(8, "Correcteur V5", -5.0, 5.0, (0.01, 0.1), (0.1, 1.0), _field("C6NI6703", "09 OUT09 b37 Cmd Guidage V5")),
)


OBSERVED_ANALOG_WRITE_BOUNDARY = ("C6NI6703", "C7NI6703", "C8NI6703", "C9NI6703")
NON_SETPOINT_SELECTOR_VALUES = (0, 1, 16)


def _rules_and_evidence(
    beam_line: BeamLine,
) -> tuple[tuple[ChannelAdjustmentRule, ...], BeamLineEvidenceIdentity]:
    if not isinstance(beam_line, BeamLine):
        raise TypeError("beam_line must be BeamLine")
    if beam_line is BeamLine.DIRECT:
        return DIRECT_CHANNEL_RULES, DIRECT_EVIDENCE
    return DEVIATED_CHANNEL_RULES, DEVIATED_EVIDENCE


def plan_beamline_adjustment(
    beam_line: BeamLine,
    channel_index: int,
    action: AdjustmentAction,
    x10_selected: bool,
    current_setpoint: float,
) -> BeamLineAdjustmentPlan:
    """Return the evidenced clamped setpoint and one controller-field intent.

    The caller must already have resolved the legacy old/new-value comparison
    to exactly one channel and one of the four adjustment buttons.  The legacy
    behavior when multiple controls change in one event is not reproduced.
    """

    rules, evidence = _rules_and_evidence(beam_line)
    if isinstance(channel_index, bool) or not isinstance(channel_index, int):
        raise TypeError("channel_index must be int")
    if not 0 <= channel_index < len(rules):
        raise IndexError("channel_index is outside the evidenced beam-line cluster")
    if not isinstance(action, AdjustmentAction):
        raise TypeError("action must be AdjustmentAction")
    if not isinstance(x10_selected, bool):
        raise TypeError("x10_selected must be bool")
    if isinstance(current_setpoint, bool) or not isinstance(current_setpoint, (int, float)):
        raise TypeError("current_setpoint must be a real number")
    current = float(current_setpoint)
    if not math.isfinite(current):
        raise ValueError("current_setpoint must be finite")

    rule = rules[channel_index]
    step_pair = (
        rule.large_step
        if action in (AdjustmentAction.LARGE_DECREASE, AdjustmentAction.LARGE_INCREASE)
        else rule.small_step
    )
    step = step_pair[1 if x10_selected else 0]
    direction = -1.0 if action in (AdjustmentAction.LARGE_DECREASE, AdjustmentAction.SMALL_DECREASE) else 1.0
    requested = current + direction * step
    coerced = min(rule.maximum, max(rule.minimum, requested))

    route_boundaries: tuple[str, ...] = ()
    if rule.crosswalk_status == "LABEL_MISMATCH_VERIFY_MEANING":
        route_boundaries = (
            "Focale is visibly routed to legacy C7 field 05 labelled Cmd I Solénoïde; semantic identity is unresolved",
        )
    elif rule.crosswalk_status == "SCHEMA_RESERVE_UNVERIFIED_ACTUATOR":
        route_boundaries = (
            "Correcteur H5 is visibly routed to legacy C6 field 08 labelled Réserve; physical intent is unresolved",
        )

    return BeamLineAdjustmentPlan(
        beam_line=beam_line,
        channel_index=channel_index,
        channel_name=rule.legacy_name,
        action=action,
        x10_selected=x10_selected,
        original_setpoint=current,
        step=step,
        requested_setpoint=requested,
        coerced_setpoint=coerced,
        was_coerced=coerced != requested,
        controller_patch=rule.destination,
        crosswalk_status=rule.crosswalk_status,
        crosswalk_label_match=rule.crosswalk_label_match,
        adapter_use_allowed=False,
        momentary_button_reset_after_ms=70,
        sve_refresh_wait_ms=100,
        observed_full_cluster_write_boundary=OBSERVED_ANALOG_WRITE_BOUNDARY,
        ordering_within_write_boundary_proven=False,
        external_effects_blocked=True,
        manual_approval_required=True,
        implementation_allowed=False,
        evidence=evidence,
        unresolved_boundaries=(
            "old/new cluster arbitration when multiple fields change in one event",
            "the current extracted VI copy differs from the source hash bound to the saved evidence corpus",
            "full PSP payload construction, deployed refnum identity, acknowledgement, retry, timeout, and stale-data policy",
            "engineering-unit confirmation, polarity, interlocks, and hardware safe-state behavior",
            "formal selector-frame PNG mapping remains UNMAPPED",
        )
        + route_boundaries,
    )


def validate_beamline_adjustment_plan(plan: BeamLineAdjustmentPlan) -> None:
    """Fail closed if any evidenced value, route, or safety gate was altered."""

    if not isinstance(plan, BeamLineAdjustmentPlan):
        raise TypeError("plan must be BeamLineAdjustmentPlan")
    expected = plan_beamline_adjustment(
        plan.beam_line,
        plan.channel_index,
        plan.action,
        plan.x10_selected,
        plan.original_setpoint,
    )
    if plan != expected:
        raise ValueError("beam-line adjustment plan differs from the evidenced canonical intent")
    if (
        not plan.external_effects_blocked
        or not plan.manual_approval_required
        or plan.implementation_allowed
        or plan.adapter_use_allowed
    ):
        raise ValueError("beam-line adjustment plan must remain blocked and approval-gated")
