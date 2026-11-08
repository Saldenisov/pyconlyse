"""Pure plans for main-VI events 7/12/13 (T1/T2/T3) and 26 (centroid reset).

Frozen LabVIEW Print/manual evidence supplies visible names and the 0, Default
case marker. Both saved lvkit contexts agree on values/wiring but corrupt local
variable names and omit the default marker. Their agreement is not behavioral
verification. The source-hash drift remains explicit; this module does not parse
the modified working VI or claim a complete reconstruction of the original.

Legacy analog values and display values have no commissioned engineering units.
All results are immutable descriptions: no local writes, PSP, driver, sleep,
motor motion, scheduler, or physical-state observation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class ArtifactIdentity:
    path: str
    sha256: str


SOURCE_LIBRARY = ArtifactIdentity(
    "source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb",
    "D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4",
)
EVIDENCE_SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
REVIEWED_WORKING_COPY = ArtifactIdentity(
    "extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs/0_SUP_ELYSE.vi",
    "2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B",
)
LVKIT_CONTEXTS = (
    ArtifactIdentity("analysis/lvkit_eval/batch_0_8_4/descriptions/0_SUP_ELYSE.json",
        "6BB753AD37A83A258E765FA875552E8F6864681020C6ADF9B5ED76F58BD51632"),
    ArtifactIdentity("analysis/lvkit_eval/batch_0_8_4_minimal_vilib/descriptions/0_SUP_ELYSE.json",
        "AA620AA9E6FE4312F555A4C5A096B51EE54FE5F34214EE17DDBF9CC2822B8710"),
)


def _print(number: int, sha256: str) -> ArtifactIdentity:
    return ArtifactIdentity(f"analysis/labview_print_hidden_frames/0__SUP__ELYSEd{number}.png", sha256)


class DiagnosticStation(str, Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


@dataclass(frozen=True)
class LocalNameMismatch:
    node_uid: int
    parsed_name: str
    visible_name: str


@dataclass(frozen=True)
class DiagnosticEventEvidence:
    event_case_index: int
    selector_uid: int
    bundle_uid: int
    write_uid: int
    display_multiply_uid: int
    expected_event_key_sha256: str
    manual: ArtifactIdentity
    prints: tuple[ArtifactIdentity, ...]
    name_mismatches: tuple[LocalNameMismatch, ...]
    visible_default_label: str = "0, Default"
    parsed_default_detected: bool = False
    formal_png_mapping_status: str = "UNMAPPED"
    working_copy_matches_evidence_source: bool = False


@dataclass(frozen=True)
class DiagnosticPositionRule:
    station: DiagnosticStation
    field: str
    display_local: str
    evidence: DiagnosticEventEvidence


DIAGNOSTIC_POSITION_RULES = (
    DiagnosticPositionRule(DiagnosticStation.T1,
        "04 OUT04 b17 Cmd position translateur Ecran 1", "Cmd pos T1",
        DiagnosticEventEvidence(7, 67856, 57317, 57358, 54988,
            "95D771FCCAC1EE3B38D784090D694FCFC0AD378E55572371F87952B4EFBD89CD",
            ArtifactIdentity("analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_07_full.png",
                "9D5E7D1DF4B99F4A960D82B5243D1BE847466321C81EA178EEAC842284E02EC5"),
            (_print(221, "6A1AEB6AB036537D94B061A50E49B4AB660F27B9E92A9BDD3E2EDD92569E3A27"),
             _print(222, "9FC12D7897A49D8F06B7A1C0D4C12B7BF755D8BE4BF57F186FC644C3FDBEB0A6"),
             _print(223, "DB62589D736F550CF333278E51D737A93E9A07BD577277E5DBFCB4904E14BFE3"),
             _print(224, "A0C17F24A9F26C7FAAE931F4F65F2C63E23F5224D0F96F17D06462A57E323A6A")),
            (LocalNameMismatch(53628, "SAVE", "Cmd pos T1"),
             LocalNameMismatch(57296, "WCM5D:", "C9NI6703"),
             LocalNameMismatch(57311, "WCM5D:", "C9NI6703")))),
    DiagnosticPositionRule(DiagnosticStation.T2,
        "05 OUT05 b21 Cmd position translateur Ecran 2", "Cmd pos T2",
        DiagnosticEventEvidence(12, 77739, 71448, 71458, 66556,
            "A1447F9D989E83965C9A1C61397DBE64E989DDF09FABAF81FA1335F5D7A7745A",
            ArtifactIdentity("analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_12_full.png",
                "3B27BF3979ED9A99BD00EBFAA62FCD397A9E590234052EAB636A7E1675DA80E1"),
            (_print(252, "0742AA50791E9087539BD77798786A0664B8A96289D4B8C119A12EBE8ACDD084"),
             _print(253, "1AA37500E908C2BDD0FD2CC465B932099C6BF320B38BC0E0C59A03475994C7CD"),
             _print(254, "4FA166A8008D8327598471F8649D34F9A28D1BA556ED05B44D8FD1F643AB8237"),
             _print(255, "7608D46CB9955C3F6CABBF349099CE5E445A58A207D987EAD79BA7715B3E54C3")),
            (LocalNameMismatch(57843, "ANNULER SAVE", "Cmd pos T2"),
             LocalNameMismatch(71434, "WCM5D:", "C9NI6703"),
             LocalNameMismatch(71442, "WCM5D:", "C9NI6703")))),
    DiagnosticPositionRule(DiagnosticStation.T3,
        "06 OUT06 b25 Cmd position translateur Ecran 3", "Cmd pos T3",
        DiagnosticEventEvidence(13, 82079, 73359, 73369, 72261,
            "D97B68EFABDB9C1B09E9AA3051D5C5D3E1266951ABE960CED2E4C7D8D0787EBC",
            ArtifactIdentity("analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_13_full.png",
                "5DBA80543CBBC5B8216E1096CAC1F8FC8AAF9958AE663DEDA1C8877366547CFA"),
            (_print(256, "3926ACE5266E43CB7C44C2686F3B9BF92ACF597CC289B0D12B06497C0A474690"),
             _print(257, "2918B151F7A17E6900A5D8DFEA6511502BBCDBC9C9B42E3F2485582CF8B840B1"),
             _print(258, "F5D337118CB9C0F80819B156498EDD572C3528FA19D3C4A80FF403F0509C2A2A"),
             _print(259, "2A5AD9FB9CC90217BA0E18E5488FCACE8027DDDA83B937A7FAD359CBDEA19F93")),
            (LocalNameMismatch(13401, "Somme Radioprotection", "Cmd pos T3"),
             LocalNameMismatch(73345, "WCM5D:", "C9NI6703"),
             LocalNameMismatch(73353, "WCM5D:", "C9NI6703")))),
)

# These are legacy constants, not commissioned volts, millimetres, or travel limits.
DIAGNOSTIC_SELECTOR_VALUES = ((0, 2.126), (1, 8.98), (2, 5.553))
DISPLAY_MULTIPLIER = 10.0


@dataclass(frozen=True)
class DiagnosticPositionIntent:
    station: DiagnosticStation
    event_new_value: int
    legacy_command_value: float
    display_value: float
    display_local: str
    patch: tuple[str, float]
    evidence: DiagnosticEventEvidence
    base_cluster: str = field(default="C9NI6703", init=False)
    local_mirror: str = field(default="C9NI6703", init=False)
    psp_url: str = field(default="ni.var.psp://localhost/SUPERVISION/C9NI6703", init=False)
    connection_refnum: int = field(default=43, init=False)
    preserves_unmentioned_fields: bool = field(default=True, init=False)
    sink_order_serialized: bool = field(default=False, init=False)
    write_error_consumer_observed: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    establishes_physical_position: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(default=(
        "selector labels/in-out meanings, actual device ownership, engineering units, calibration, and travel limits",
        "readback, collision/beam interlocks, acknowledgement, error recovery, and safe state",
        "native 0, Default branch is observed; out-of-contract selectors are rejected, not emulated",
        "Print-to-UID formal join remains UNMAPPED and the working source hash differs from archived evidence",
    ), init=False)


def plan_diagnostic_position_change(station: DiagnosticStation, event_new_value: int) -> DiagnosticPositionIntent:
    """Model the three evidenced selector values only; never actuate a translator.

    The raster proves a native 0, Default branch. Unknown inputs deliberately
    fail closed instead of silently producing its potentially motion-inducing
    value. This bounded API does not claim complete native selector emulation.
    """
    if not isinstance(station, DiagnosticStation):
        raise TypeError("Explicit DiagnosticStation required")
    if type(event_new_value) is not int:
        raise TypeError("Integer selector required; Boolean is not a selector")
    if event_new_value not in (0, 1, 2):
        raise ValueError("Only evidenced selector values 0, 1, 2 are supported")
    rule = next(rule for rule in DIAGNOSTIC_POSITION_RULES if rule.station is station)
    value = dict(DIAGNOSTIC_SELECTOR_VALUES)[event_new_value]
    return DiagnosticPositionIntent(station, event_new_value, value, value * DISPLAY_MULTIPLIER,
                                    rule.display_local, (rule.field, value), rule.evidence)


class ResetStepKind(str, Enum):
    LOCAL_VARIABLE_WRITE = "LOCAL_VARIABLE_WRITE"
    WAIT_BOUNDARY = "WAIT_BOUNDARY"


@dataclass(frozen=True)
class CentroidResetStep:
    frame_index: int
    node_uid: int
    kind: ResetStepKind
    target: str | None
    value: bool | None
    observed_wait_ms: int | None


@dataclass(frozen=True)
class CentroidResetEvidence:
    event_case_index: int = 26
    event_structure_uid: int = 5909
    sequence_uid: int = 20194
    expected_event_key_sha256: str = "EEF8636F670632D923A8DF408B5A9FEEFACDB1C1B806C8150345F9DB19C6B21E"
    manual: ArtifactIdentity = ArtifactIdentity(
        "analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_26_full.png",
        "5B605D33F8A9105921E66F445FDAE93E48455171B9345FDA2FEEFF52C12412A3")
    print_artifact: ArtifactIdentity = _print(406,
        "93FA3AF5ACFE00742E9FFDDA523C2F270592C961D43E13EB07E32C3D23A8DDE3")
    name_mismatches: tuple[LocalNameMismatch, ...] = (
        LocalNameMismatch(19732, "ID_NI6602_DAQmx", "Init moy CxCy"),
        LocalNameMismatch(21619, "ID_NI6602_DAQmx", "Init moy CxCy"),
    )
    formal_png_mapping_status: str = "UNMAPPED"
    working_copy_matches_evidence_source: bool = False


CENTROID_RESET_EVIDENCE = CentroidResetEvidence()


@dataclass(frozen=True)
class CentroidAverageResetPlan:
    steps: tuple[CentroidResetStep, ...]
    evidence: CentroidResetEvidence = field(default=CENTROID_RESET_EVIDENCE, init=False)
    event_new_value_consumed: bool = field(default=False, init=False)
    frame_order_serialized: bool = field(default=True, init=False)
    establishes_consumer_reset: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(default=(
        "centroid reader polling, concurrent local-variable access, buffer reset/resize, and actual averaging count",
        "200 ms wait is not acknowledgement that another loop observed either flag transition",
        "native scheduling and failure/cancellation semantics; no Python sleep or local mutation is performed",
        "Print-to-UID formal join remains UNMAPPED and the working source hash differs from archived evidence",
    ), init=False)


def plan_centroid_average_reset() -> CentroidAverageResetPlan:
    """Describe True -> wait(200 ms) -> False; do not reset a buffer or wait."""
    return CentroidAverageResetPlan((
        CentroidResetStep(0, 19732, ResetStepKind.LOCAL_VARIABLE_WRITE, "Init moy CxCy", True, None),
        CentroidResetStep(1, 22081, ResetStepKind.WAIT_BOUNDARY, None, None, 200),
        CentroidResetStep(2, 21619, ResetStepKind.LOCAL_VARIABLE_WRITE, "Init moy CxCy", False, None),
    ))
