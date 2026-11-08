"""Bounded offline change/selection intent for SuperVision main event 6.

Original 33-DBL vectors are already decoded and ordered. They are not a named
dict: duplicate labels exist. Controller payload comes from fresh local page
reads, NOT from the Event NewVal vector. Runtime property values, formatter and
loop error aggregation remain explicit unqualified boundaries.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from .fw102x_errors import ErrorCluster
from .machine_frequency import C1011_PSP_URL, SELECTION_NUMBER_FIELD
from .page_command_events import DPS_FIELDS

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/parameter_event_evidence_20261004_r2.json"
EVIDENCE_SHA256 = "30E2A65A15B880CC1D9B7B43C1D872179E83AEAD21C84C786C64B4A5E380A7F0"
SYNCHRONISATION_FIELD_COUNT = 33
SYNCHRONISATION_ERROR_PREFIX = (
    "Erreur de communication avec le SVE pendant l'envoie "
    "d'une commande de delais ou largeur des synchros: "
)


@dataclass(frozen=True)
class SynchronisationIterationIntent:
    field_index: int
    selection_number: int
    bundle_uid: int = field(default=23628, init=False)
    local_base_uid: int = field(default=19774, init=False)
    local_base: str = field(default="Page Synchronisation", init=False)
    patched_field: str = field(default=SELECTION_NUMBER_FIELD, init=False)
    local_sink_uids: tuple[int, int] = field(default=(35923, 37769), init=False)
    local_sinks: tuple[str, str] = field(
        default=("Page Synchronisation", "C10-11 NI6602"),
        init=False,
    )
    psp_write_uid: int = field(default=20132, init=False)
    psp_url: str = field(default=C1011_PSP_URL, init=False)
    connection_refnum: int = field(default=46, init=False)
    highlight_property_uid: int = field(default=41566, init=False)
    highlight_color: int = field(default=16448250, init=False)
    flash_local_write_uid: int = field(default=21948, init=False)
    psp_error_input_from_highlight_property: bool = field(default=True, init=False)
    local_sinks_conditioned_on_psp_success: bool = field(default=False, init=False)
    event_numeric_copied_into_payload: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SynchronisationEventPlan:
    active_dps_fields: tuple[str, ...]
    changed_indices: tuple[int, ...]
    iterations: tuple[SynchronisationIterationIntent, ...]
    final_flash_index: int | None
    wait_ms: int
    final_property_intent: bool
    event_index: int = field(default=6, init=False)
    guard_uid: int = field(default=19705, init=False)
    subtract_uid: int = field(default=35269, init=False)
    stacked_sequence_uid: int = field(default=35757, init=False)
    final_property_uid: int = field(default=40371, init=False)
    final_background_color: int = field(default=11776947, init=False)
    final_label_property: str = field(default="Label.Text", init=False)
    final_value_property: str = field(default="Value", init=False)
    message_prefix: str = field(default='Synchro "', init=False)
    format_pattern: str = field(default='" à %.2fµS.', init=False)
    formatter_qualified: bool = field(default=False, init=False)
    error_aggregation_qualified: bool = field(default=False, init=False)
    queued: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    establishes_physical_state: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(
        default=(
            "binary cluster decoding and duplicate-label/UI control order",
            "fresh local page read per iteration; NewVal is not the payload base",
            "selection 33 has no native clamp but exceeds advertised 1-32 range",
            "Controls[] indexing, Digital cast, property side effects and errors",
            "loop error aggregation, scheduling and concurrent local writes",
            (
                "runtime post-wait property value/label, "
                "formatter locale/rounding/encoding"
            ),
            "counter-server acceptance, actual pulse updates and physical readback",
        ),
        init=False,
    )

    @property
    def discarded_due_to_busy_dps(self) -> bool:
        return bool(self.active_dps_fields)


def _dbl_vector(values) -> tuple[float, ...]:
    if type(values) not in (tuple, list):
        raise TypeError("Explicit ordered 33-DBL vector required; no named dict")
    if len(values) != SYNCHRONISATION_FIELD_COUNT:
        raise ValueError("Original synchronisation cluster requires 33 fields")
    if any(type(v) not in (int, float) for v in values):
        raise TypeError(
            "Numeric DBL values required; Boolean/string coercion forbidden"
        )
    try:
        result = tuple(float(v) for v in values)
    except OverflowError as exc:
        raise ValueError(
            "DBL overflow is outside the finite projection contract"
        ) from exc
    if any(not math.isfinite(v) for v in result):
        raise ValueError("Non-finite DBL behavior is not qualified")
    return result


def plan_synchronisation_change(
    current_dps: Mapping[str, bool],
    ordered_oldval: tuple[float, ...],
    ordered_newval: tuple[float, ...],
    stored_flash_index: int | None = None,
) -> SynchronisationEventPlan:
    """Identify all changed indices via OldVal - NewVal != 0.0.

    Idle zero-change event still waits and reads the previously stored flash
    index: explicit index is required in that case. Last changed index is used
    otherwise. Busy event has no sequence, property, wait or deferred command.
    Loop intents are enumerated by index, not claimed accepted/acknowledged.
    """
    if not isinstance(current_dps, Mapping):
        raise TypeError("Complete named local DPS snapshot required")
    dps = dict(current_dps)
    if set(dps) != set(DPS_FIELDS):
        raise ValueError("Complete original 29-field DPS snapshot required")
    if any(type(v) is not bool for v in dps.values()):
        raise TypeError("Exact DPS Booleans required")
    active = tuple(name for name in DPS_FIELDS if dps[name])
    if active:
        return SynchronisationEventPlan(active, (), (), None, 0, False)
    old = _dbl_vector(ordered_oldval)
    new = _dbl_vector(ordered_newval)
    differences = tuple(a - b for a, b in zip(old, new, strict=True))
    if any(not math.isfinite(v) for v in differences):
        raise ValueError(
            "Subtraction overflow is outside the finite projection contract"
        )
    changed = tuple(i for i, difference in enumerate(differences) if difference != 0.0)
    last = changed[-1] if changed else stored_flash_index
    if type(last) is not int:
        raise TypeError(
            "Explicit stored flash index required for idle zero-change event"
        )
    if not 0 <= last < SYNCHRONISATION_FIELD_COUNT:
        raise ValueError("Flash index outside evidenced 33-control projection")
    return SynchronisationEventPlan(
        (),
        changed,
        tuple(SynchronisationIterationIntent(i, i + 1) for i in changed),
        last,
        300,
        True,
    )


@dataclass(frozen=True)
class SynchronisationTextProjection:
    tme: str
    ter: str


def project_synchronisation_result(
    plan: SynchronisationEventPlan,
    stored_tme: str,
    stored_ter: str,
    final_error: ErrorCluster | None,
    supplied_formatted_text: str | None = None,
) -> SynchronisationTextProjection:
    """Project explicitly supplied final Format String result, not emulate it.

    Error path writes TER and retains TME. No Error writes supplied runtime
    formatted text and retains TER. This does not infer error aggregation from
    per-iteration PSP results, nor substitute Event NewVal for a property read.
    """
    if not isinstance(plan, SynchronisationEventPlan):
        raise TypeError("Explicit SynchronisationEventPlan required")
    if type(stored_tme) is not str or type(stored_ter) is not str:
        raise TypeError("Exact stored text strings required")
    if not plan.final_property_intent:
        if final_error is not None or supplied_formatted_text is not None:
            raise ValueError("Busy event has no final property/format result")
        return SynchronisationTextProjection(stored_tme, stored_ter)
    if not isinstance(final_error, ErrorCluster):
        raise TypeError("Explicit hypothetical final formatter ErrorCluster required")
    if type(final_error.status) is not bool or type(final_error.source) is not str:
        raise TypeError("Exact final error status and source required")
    if type(final_error.code) is not int:
        raise TypeError("Exact signed I32 error code required")
    if not -(2**31) <= final_error.code < 2**31:
        raise ValueError("Final error code outside signed I32 range")
    if final_error.status:
        return SynchronisationTextProjection(
            stored_tme,
            SYNCHRONISATION_ERROR_PREFIX + final_error.source,
        )
    if type(supplied_formatted_text) is not str:
        raise TypeError("Explicit post-property formatted result required")
    return SynchronisationTextProjection(supplied_formatted_text, stored_ter)
