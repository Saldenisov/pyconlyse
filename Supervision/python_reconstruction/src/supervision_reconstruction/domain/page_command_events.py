"""Pure DPS intent plans for SuperVision main-VI events 17 and 18.

Named Boolean fields already extracted from Event NewVal are the input, not a
binary LabVIEW cluster. Entire 29-field local DPS snapshot supplies the guard.
No PSP/local/UI assignment, wait, acquisition procedure or hardware call runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from .fw102x_errors import ErrorCluster

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/page_command_evidence_20261003.json"
EVIDENCE_SHA256 = "D64CF9D85D6DF67DE9C8D8D8ACCCB527E219B8728B390339E3CD7BB34A142E2D"
PSP_URL = "ni.var.psp://localhost/SUPERVISION/DPS"
DPS_FIELDS = (
    "Marche refroidissement X",
    "Arret refroidissement X",
    " X Marche GENERAL Mod.",
    "X Arrêt GENERAL Mod.",
    "X Marche CHAUFFAGE Mod.",
    "X Arrêt CHAUFFAGE Mod.",
    "X Marche PREMA Mod. ",
    "X Arrêt PREMA Mod.",
    " X Marche RELAIS HT Mod.",
    "X Arrêt RELAIS HT Mod.",
    "X Marche FOCALE Mod.",
    "X Arrêt FOCALE Mod.",
    "X RESET Mod.",
    "X Marche Att Déph",
    "X Arret Att Déph",
    "X Marche alimentation HT",
    "X Reset alimentation HT",
    "X Arrêt alimentation HT",
    "X Marche impulsion mod",
    "X Arret impulsion mod",
    "X Marche alimentation aimant",
    "X Alimentation aimant = 0V",
    "X Alimentation aimant = PT",
    "X Arrêt alimentation aimant",
    "X Tempo 1s",
    "X Tempo 5s",
    "X Tempo 30s",
    "X FREQ. ELYSE",
    "Libre X",
)
# Exact whitespace/spelling is part of the archived named-field contract.
ALIMENTATIONS_FIELD_MAP = (
    ("Marche Aimants.", "X Marche alimentation aimant"),
    ("Arrêt Aimants", "X Arrêt alimentation aimant"),
    ("Aimant 0V", "X Alimentation aimant = 0V"),
)
MODULATOR_FIELD_MAP = (
    ("Marche MOD", " X Marche GENERAL Mod."),
    ("Arrêt MOD", "X Arrêt GENERAL Mod."),
    ("Marche CHAUFFAGE MOD", "X Marche CHAUFFAGE Mod."),
    ("Arrêt CHAUFFAGE MOD", "X Arrêt CHAUFFAGE Mod."),
    ("Marche PREMA MOD", "X Marche PREMA Mod. "),
    ("Arrêt PREMA MOD", "X Arrêt PREMA Mod."),
    ("Marche RELAIS HT MOD", " X Marche RELAIS HT Mod."),
    ("Arrêt RELAIS HT MOD", "X Arrêt RELAIS HT Mod."),
    ("Marche FOCALES MOD", "X Marche FOCALE Mod."),
    ("Arrêt FOCALES MOD", "X Arrêt FOCALE Mod."),
    ("Reset MOD", "X RESET Mod."),
)


class CommandPage(Enum):
    ALIMENTATIONS = "Page Alimentations"
    MODULATOR = "Page Modulateur"


@dataclass(frozen=True)
class PageCommandEvidence:
    event_index: int
    event_data_uid: int
    dps_read_uid: int
    cluster_array_uid: int
    or_array_uid: int
    guard_uid: int
    unbundle_uid: int
    bundle_uid: int
    psp_write_uid: int
    dps_write_uid: int
    error_case_uid: int
    error_source_uid: int
    concatenate_uid: int
    ter_write_uid: int
    wait_uid: int
    error_prefix: str


ALIMENTATIONS_EVIDENCE = PageCommandEvidence(
    17,
    47104,
    47137,
    38462,
    40386,
    47154,
    47174,
    47198,
    32048,
    47186,
    19594,
    19523,
    37324,
    40558,
    28270,
    (
        "Erreur de communication avec le SVE pendant l'envoie "
        "d'une commande de M/A ou cyclage des alimentations: "
    ),
)
MODULATOR_EVIDENCE = PageCommandEvidence(
    18,
    30855,
    30929,
    43109,
    43129,
    30946,
    32126,
    33466,
    33792,
    33453,
    33976,
    34555,
    37074,
    37686,
    43942,
    (
        "Erreur de communication avec le SVE pendant l'envoie "
        "d'une commande de M/A du modulateur."
    ),
)


@dataclass(frozen=True)
class PageCommandPlan:
    page: CommandPage
    evidence: PageCommandEvidence
    incoming_dps: tuple[tuple[str, bool], ...]
    extracted_newval: tuple[tuple[str, bool], ...]
    # None means guard True: no bundle/local/PSP write, no deferred request.
    projected_dps: tuple[tuple[str, bool], ...] | None
    patches: tuple[tuple[str, bool], ...]
    active_guard_fields: tuple[str, ...]
    wait_ms: int
    base_cluster: str = field(default="DPS", init=False)
    psp_url: str = field(default=PSP_URL, init=False)
    connection_refnum: int = field(default=38, init=False)
    wait_after_guard_completion: bool = field(default=True, init=False)
    local_and_psp_writes_serialized: bool = field(default=False, init=False)
    local_write_conditioned_on_psp_success: bool = field(default=False, init=False)
    queued: bool = field(default=False, init=False)
    ui_reset_observed: bool = field(default=False, init=False)
    one_hot_arbitration_observed: bool = field(default=False, init=False)
    establishes_physical_state: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(
        default=(
            "NewVal binary decoding and original Alimentations field-index metadata",
            "local DPS snapshot coherence/freshness and concurrent read-modify-write",
            "local/PSP sink ordering and reconciliation after communication failure",
            "server acceptance, arbitration, procedure progress and physical readback",
            "scheduler behavior of Wait(0)/Wait(200), neither an acknowledgement",
            "per-equipment Device Server/legacy ownership; no retired-DAQ fallback",
            (
                "commissioned polarity, units, limits, permissives "
                "and safe-state semantics"
            ),
            "global Print-to-UID reconciliation remains UNMAPPED",
        ),
        init=False,
    )

    @property
    def discarded_due_to_busy_dps(self) -> bool:
        return bool(self.active_guard_fields)

    @property
    def write_intent_observed(self) -> bool:
        return self.projected_dps is not None


def _boolean_snapshot(
    value: Mapping[str, bool], names: tuple[str, ...], description: str
) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{description} must be a named Boolean mapping")
    snapshot = dict(value)
    if set(snapshot) != set(names):
        raise ValueError(f"{description} requires exactly the evidenced field set")
    if any(type(v) is not bool for v in snapshot.values()):
        raise TypeError(f"{description} cannot coerce unknown/non-Boolean values")
    return snapshot


def plan_page_command_change(
    page: CommandPage,
    current_dps: Mapping[str, bool],
    extracted_newval: Mapping[str, bool],
) -> PageCommandPlan:
    """Describe both sinks from one snapshot; never decode or dispatch a cluster.

    NewVal includes only the 3/11 selected command fields, not the entire UI
    page and not a changed-field delta. Opposing/simultaneous True flags are
    retained as native intent, not accepted as a safe modern command.
    """
    if not isinstance(page, CommandPage):
        raise TypeError("Explicit CommandPage required")
    fields, evidence = (
        (ALIMENTATIONS_FIELD_MAP, ALIMENTATIONS_EVIDENCE)
        if page is CommandPage.ALIMENTATIONS
        else (MODULATOR_FIELD_MAP, MODULATOR_EVIDENCE)
    )
    snapshot = _boolean_snapshot(current_dps, DPS_FIELDS, "Whole local DPS snapshot")
    values = _boolean_snapshot(
        extracted_newval,
        tuple(source for source, _ in fields),
        "Selected Event NewVal fields",
    )
    active = tuple(name for name in DPS_FIELDS if snapshot[name])
    patches = (
        tuple((target, values[source]) for source, target in fields)
        if not active
        else ()
    )
    projected = dict(snapshot)
    projected.update(patches)
    return PageCommandPlan(
        page,
        evidence,
        tuple((name, snapshot[name]) for name in DPS_FIELDS),
        tuple((source, values[source]) for source, _ in fields),
        tuple((name, projected[name]) for name in DPS_FIELDS) if not active else None,
        patches,
        active,
        0 if active else 200,
    )


def project_page_command_error(
    plan: PageCommandPlan,
    stored_ter: str,
    write_error: ErrorCluster | None,
) -> str:
    """Project one hypothetical PSP result onto separately stored TER.

    Busy branch has no PSP result. No Error is empty and retains stored TER,
    even with a nonzero warning code. Error appends source without whitespace
    normalization. Nothing rolls back the independently intended local write.
    """
    if not isinstance(plan, PageCommandPlan) or type(stored_ter) is not str:
        raise TypeError("PageCommandPlan and exact stored TER string required")
    if not plan.write_intent_observed:
        if write_error is not None:
            raise ValueError("Busy branch has no PSP write result")
        return stored_ter
    if not isinstance(write_error, ErrorCluster):
        raise TypeError("Explicit hypothetical PSP ErrorCluster required")
    if type(write_error.status) is not bool or type(write_error.source) is not str:
        raise TypeError("Exact error status Boolean and source string required")
    if type(write_error.code) is not int:
        raise TypeError("Exact signed I32 error code required")
    if not -(2**31) <= write_error.code < 2**31:
        raise ValueError("Error code outside signed I32 range")
    return (
        plan.evidence.error_prefix + write_error.source
        if write_error.status
        else stored_ter
    )
