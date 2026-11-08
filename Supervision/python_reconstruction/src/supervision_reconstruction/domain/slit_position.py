"""Pure position formula for ``0_SUP_ELYSE.vi`` event case 2.

The manual capture and LabVIEW Print ``d177`` visibly identify the two inputs
as ``AXE H`` and ``GAP H`` and the destination as ``C9NI6703``.  The saved
lvkit graph provides the node UIDs and dataflow topology but misnames those
terminals as unrelated locals.  Raster labels therefore provide names while
lvkit provides wiring.  No function in this module opens the PSP URL or sends
a command.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class SlitFieldPatch:
    field: str
    value: float


@dataclass(frozen=True)
class SlitPositionEvidence:
    event_structure_uid: int
    event_case_index: int
    manual_event_label: str
    lvkit_event_label: str
    bundle_uid: int
    shared_variable_write_uid: int
    simple_error_handler_uid: int
    source_library_path: str
    source_library_sha256: str
    evidence_source_vi_sha256: str
    reviewed_extracted_copy_path: str
    reviewed_extracted_copy_sha256: str
    extracted_copy_matches_evidence_source: bool
    lvkit_description_path: str
    lvkit_description_sha256: str
    manual_screenshot_path: str
    manual_screenshot_sha256: str
    print_png_path: str
    print_png_sha256: str
    expected_key_sha256: str
    formal_png_mapping_status: str


@dataclass(frozen=True)
class SlitPositionIntent:
    axe_h: float
    gap_h: float
    position_hg: float
    position_hd: float
    base_cluster: str
    patches: tuple[SlitFieldPatch, SlitFieldPatch]
    preserves_unmentioned_fields: bool
    local_mirror: str
    psp_url: str
    connection_refnum: int
    local_and_psp_sink_order_serialized: bool
    write_error_consumer_observed: bool
    external_effects_blocked: bool
    manual_approval_required: bool
    evidence: SlitPositionEvidence
    unresolved_boundaries: tuple[str, ...]


SLIT_POSITION_EVIDENCE = SlitPositionEvidence(
    event_structure_uid=5909,
    event_case_index=2,
    manual_event_label='[2] "AXE H", "GAP H": Value Change',
    lvkit_event_label='[2] "GAP H": Value Change',
    bundle_uid=88926,
    shared_variable_write_uid=88939,
    simple_error_handler_uid=83833,
    source_library_path="source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb",
    source_library_sha256="D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4",
    evidence_source_vi_sha256="B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
    reviewed_extracted_copy_path=(
        "extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs/0_SUP_ELYSE.vi"
    ),
    reviewed_extracted_copy_sha256="2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B",
    extracted_copy_matches_evidence_source=False,
    lvkit_description_path=(
        "analysis/lvkit_eval/batch_0_8_4_minimal_vilib/descriptions/0_SUP_ELYSE.json"
    ),
    lvkit_description_sha256="AA620AA9E6FE4312F555A4C5A096B51EE54FE5F34214EE17DDBF9CC2822B8710",
    manual_screenshot_path=(
        "analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_02_full.png"
    ),
    manual_screenshot_sha256="D41F44B09949B6D86B7E487205070B6904A06932EDA850074540ACCFDC948DC1",
    print_png_path="analysis/labview_print_hidden_frames/0__SUP__ELYSEd177.png",
    print_png_sha256="8A206614BF7540175DF318944F5E2AD9C2DCA6985A2F55A93A606F5F8CBC274B",
    expected_key_sha256="72C30DF1D79BDE38855CED4DF64370BF0C63E8C938A071F624EE989973BBDCC3",
    formal_png_mapping_status="UNMAPPED",
)


def _finite_real(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def plan_slit_position_change(axe_h: Real, gap_h: Real) -> SlitPositionIntent:
    """Calculate the two evidenced slit commands without executing either sink."""

    resolved_axe_h = _finite_real("axe_h", axe_h)
    resolved_gap_h = _finite_real("gap_h", gap_h)
    position_hg = 5.0 + 0.0979 * resolved_axe_h - 0.049 * resolved_gap_h
    position_hd = 5.0 - 0.0979 * resolved_axe_h - 0.049 * resolved_gap_h
    patches = (
        SlitFieldPatch("02 OUT02 b09 Cmd position fente HG", position_hg),
        SlitFieldPatch("03 OUT03 b13 Cmd position fente HD", position_hd),
    )
    return SlitPositionIntent(
        axe_h=resolved_axe_h,
        gap_h=resolved_gap_h,
        position_hg=position_hg,
        position_hd=position_hd,
        base_cluster="C9NI6703",
        patches=patches,
        preserves_unmentioned_fields=True,
        local_mirror="C9NI6703",
        psp_url="ni.var.psp://localhost/SUPERVISION/C9NI6703",
        connection_refnum=43,
        local_and_psp_sink_order_serialized=False,
        write_error_consumer_observed=True,
        external_effects_blocked=True,
        manual_approval_required=True,
        evidence=SLIT_POSITION_EVIDENCE,
        unresolved_boundaries=(
            "engineering units, valid input/output ranges, LabVIEW DBL coercion, and physical calibration",
            "controller ownership, acknowledgement, retry, timeout, stale-data, interlocks, and safe state",
            "the current extracted VI copy differs from the source hash bound to the saved evidence corpus",
            "the visually matching Print d177 remains formally UNMAPPED without an ordinal-to-UID sidecar",
            "lvkit terminal names contradict the raster labels; raster labels are authoritative for control identity",
        ),
    )
