"""Pure intent model for the machine-frequency event in ``0_SUP_ELYSE.vi``.

Event Structure uid 5909, case 1, replaces two fields in the existing
``Page Synchronisation`` cluster and fans the resulting cluster out to two
local-variable mirrors plus one PSP dynamic-write boundary.  This module only
records that evidenced dataflow.  It has no LabVIEW, PSP, network, hardware,
acknowledgement, retry, or error-handling executor.

The manual capture and LabVIEW Print ``d176`` visibly agree on the graph.  The
formal selector-frame ledger nevertheless remains ``UNMAPPED`` because the
saved Print artifact has no deterministic ordinal-to-structure join key.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


MACHINE_FREQUENCY_FIELD = "Fréquence ELYSE"
SELECTION_NUMBER_FIELD = "N° de la sélection (1 à 32): "
SELECTION_NUMBER_VALUE = 4.0
PAGE_SYNCHRONISATION = "Page Synchronisation"
C1011_LOCAL_MIRROR = "C10-11 NI6602"
C1011_PSP_URL = "ni.var.psp://localhost/SUPERVISION/C1011NI6602"


class FrequencySinkKind(str, Enum):
    LOCAL_VARIABLE = "local_variable"
    PSP_DYNAMIC_WRITE = "psp_dynamic_write"


@dataclass(frozen=True)
class SynchronisationClusterReplacement:
    """Named-field replacement applied to the existing page cluster.

    The remaining cluster fields are intentionally opaque: the diagram proves
    that Bundle By Name preserves them, but this event does not expose their
    values or types.
    """

    base_cluster: str
    replacements: tuple[tuple[str, int | float], ...]
    replacement_labview_types: tuple[tuple[str, str], ...]
    preserves_unmentioned_fields: bool


@dataclass(frozen=True)
class MachineFrequencySink:
    kind: FrequencySinkKind
    endpoint: str


@dataclass(frozen=True)
class MachineFrequencyEvidence:
    vi_name: str
    source_library_path: str
    source_library_sha256: str
    source_vi_sha256: str
    reviewed_extracted_copy_path: str
    reviewed_extracted_copy_sha256: str
    extracted_copy_matches_evidence_source: bool
    lvkit_description_path: str
    lvkit_description_sha256: str
    event_structure_uid: int
    event_case_index: int
    event_label: str
    event_data_node_uid: int
    base_cluster_read_uid: int
    bundle_by_name_uid: int
    shared_variable_write_uid: int
    local_variable_uids: tuple[int, int]
    expected_key_sha256: str
    manual_screenshot_path: str
    manual_screenshot_sha256: str
    print_png_path: str
    print_png_sha256: str
    formal_png_mapping_status: str


@dataclass(frozen=True)
class MachineFrequencyIntent:
    """Immutable, non-executable representation of one Value Change event."""

    event_new_value: int
    updated_cluster: SynchronisationClusterReplacement
    sinks: frozenset[MachineFrequencySink]
    sink_order_serialized: bool
    acknowledgement_observed: bool
    retry_observed: bool
    error_consumer_observed: bool
    external_effects_blocked: bool
    manual_approval_required: bool
    evidence: MachineFrequencyEvidence
    unresolved_boundaries: tuple[str, ...]


MACHINE_FREQUENCY_EVIDENCE = MachineFrequencyEvidence(
    vi_name="0_SUP_ELYSE.vi",
    source_library_path="source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb",
    source_library_sha256="D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4",
    source_vi_sha256="B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
    reviewed_extracted_copy_path=(
        "extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs/0_SUP_ELYSE.vi"
    ),
    reviewed_extracted_copy_sha256="2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B",
    extracted_copy_matches_evidence_source=False,
    lvkit_description_path=(
        "analysis/lvkit_eval/batch_0_8_4_minimal_vilib/descriptions/0_SUP_ELYSE.json"
    ),
    lvkit_description_sha256="AA620AA9E6FE4312F555A4C5A096B51EE54FE5F34214EE17DDBF9CC2822B8710",
    event_structure_uid=5909,
    event_case_index=1,
    event_label='[1] "Fréquence machine": Value Change',
    event_data_node_uid=70885,
    base_cluster_read_uid=60452,
    bundle_by_name_uid=61621,
    shared_variable_write_uid=70253,
    local_variable_uids=(59714, 70290),
    expected_key_sha256="A46933AE0F6F763AB08CB55B459955F0E8204E889CB3517564E3E368BC8DC22C",
    manual_screenshot_path=(
        "analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_01_full.png"
    ),
    manual_screenshot_sha256="5FB11586CD9FCDE17DA9EF73171F3EEF9E9E6E0BAFC5EDA61363F306CE774393",
    print_png_path="analysis/labview_print_hidden_frames/0__SUP__ELYSEd176.png",
    print_png_sha256="DE1712B91AAE2A8D49BBE4E4F71C228382156321A13BF11F24BD9A3DC05A835C",
    formal_png_mapping_status="UNMAPPED",
)


MACHINE_FREQUENCY_SINKS = frozenset(
    (
        MachineFrequencySink(FrequencySinkKind.LOCAL_VARIABLE, PAGE_SYNCHRONISATION),
        MachineFrequencySink(FrequencySinkKind.LOCAL_VARIABLE, C1011_LOCAL_MIRROR),
        MachineFrequencySink(FrequencySinkKind.PSP_DYNAMIC_WRITE, C1011_PSP_URL),
    )
)


def plan_machine_frequency_change(new_value: int) -> MachineFrequencyIntent:
    """Return the exact evidenced routing intent without performing any sink write.

    The blue ``NewVal`` wire proves an integer value, but the saved evidence used
    here does not establish its signedness, width, engineering unit, or allowed
    range.  Consequently this function accepts any Python ``int`` without adding
    an invented range policy and rejects ``bool`` explicitly.
    """

    if type(new_value) is not int:
        raise TypeError("new_value must be int; LabVIEW width and signedness remain unresolved")

    replacement = SynchronisationClusterReplacement(
        base_cluster=PAGE_SYNCHRONISATION,
        replacements=(
            (MACHINE_FREQUENCY_FIELD, new_value),
            (SELECTION_NUMBER_FIELD, SELECTION_NUMBER_VALUE),
        ),
        replacement_labview_types=(
            (MACHINE_FREQUENCY_FIELD, "INTEGER_WIDTH_SIGNEDNESS_UNRESOLVED"),
            (SELECTION_NUMBER_FIELD, "DBL"),
        ),
        preserves_unmentioned_fields=True,
    )
    return MachineFrequencyIntent(
        event_new_value=new_value,
        updated_cluster=replacement,
        sinks=MACHINE_FREQUENCY_SINKS,
        sink_order_serialized=False,
        acknowledgement_observed=False,
        retry_observed=False,
        error_consumer_observed=False,
        external_effects_blocked=True,
        manual_approval_required=True,
        evidence=MACHINE_FREQUENCY_EVIDENCE,
        unresolved_boundaries=(
            "NewVal integer width, signedness, engineering unit, and allowed range",
            "runtime PSP acknowledgement, retry, timeout, stale-data, and error policy",
            "relative scheduling of the three unwired fan-out sinks",
            "the current extracted VI copy differs from the source hash bound to the saved evidence corpus",
        ),
    )
