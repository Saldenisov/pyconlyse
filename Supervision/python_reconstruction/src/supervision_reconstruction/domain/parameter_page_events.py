"""Offline named-field intent projections for main events 14, 15 and 16.

Native Print plus original wires define branch choice, arithmetic and patches.
This is not binary NewVal decoding, PSP execution or a safe modern actuator.
Busy DPS blocks procedure requests but DOES NOT block setpoint arrows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from .fw102x_errors import ErrorCluster
from .page_command_events import DPS_FIELDS

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/parameter_event_evidence_20261004_r2.json"
EVIDENCE_SHA256 = "30E2A65A15B880CC1D9B7B43C1D872179E83AEAD21C84C786C64B4A5E380A7F0"
ERROR_LEAD = "Erreur de communication avec le SVE pendant l'envoie d'une commande "
DPS_URL = "ni.var.psp://localhost/SUPERVISION/DPS"


class ParameterPage(Enum):
    FLUIDES = "Page Fluides"
    HT = "Page HT"
    HF = "Page HF"


class ParameterBranch(Enum):
    PROCEDURE = "outer False: procedure flags"
    ADJUSTMENT = "outer True / arrow OR True / one-bit mask"
    BUSY_PROCEDURE_DISCARDED = "outer True / arrow OR False"
    DEFAULT_NO_OP = "outer True / arrow OR True / unmatched mask"


class ParameterUiBase(Enum):
    LOCAL_PAGE = "fresh local page read"
    EVENT_NEWVAL = "whole Event NewVal"


@dataclass(frozen=True)
class ParameterRule:
    page: ParameterPage
    mask: int
    arrow: str
    numeric_field: str
    delta: float
    limits: tuple[float, float] | None
    controller: str
    controller_field: str
    error_prefix: str
    # arithmetic, clamp (None if absent), bundle, PSP, read/write local,
    # UI bundle/write, wait sequence/wait; all original main-BD UIDs.
    node_uids: tuple[int | None, ...]


def _rule(page, mask, arrow, name, delta, limits, controller, target, suffix, uids):
    return ParameterRule(
        page,
        mask,
        arrow,
        name,
        delta,
        limits,
        controller,
        target,
        ERROR_LEAD + suffix,
        uids,
    )


PARAMETER_RULES = (
    _rule(
        ParameterPage.FLUIDES,
        1,
        "< Canon",
        "T° CANON:",
        -0.1,
        None,
        "C8NI6703",
        "01 OUT01 b05 Cmd Temp. Canon",
        "de < le la consigne de T° canon: ",
        (39304, None, 38656, 36455, 38705, 26383, 13496, 10163, 9718, 38508),
    ),
    _rule(
        ParameterPage.FLUIDES,
        2,
        "> Canon",
        "T° CANON:",
        0.1,
        None,
        "C8NI6703",
        "01 OUT01 b05 Cmd Temp. Canon",
        "de > le la consigne de T° canon: ",
        (13520, None, 43054, 42992, 43064, 42984, 43043, 43029, 57421, 57473),
    ),
    _rule(
        ParameterPage.FLUIDES,
        4,
        "< Section",
        "T° SECTION:",
        -0.1,
        None,
        "C8NI6703",
        "02 OUT02 b09 Cmd Temp. Section",
        "de < le la consigne de T° de la section: ",
        (10570, None, 45113, 44982, 45134, 44959, 45095, 45062, 56752, 61892),
    ),
    _rule(
        ParameterPage.FLUIDES,
        8,
        "> Section",
        "T° SECTION:",
        0.1,
        None,
        "C8NI6703",
        "02 OUT02 b09 Cmd Temp. Section",
        "de > le la consigne de T° de la section: ",
        (19403, None, 48887, 48837, 48897, 48829, 48877, 48863, 56693, 56723),
    ),
    _rule(
        ParameterPage.HT,
        1,
        "<< HT",
        "Consigne HT",
        -1.0,
        (6.0, 20.0),
        "C9NI6703",
        "00 OUT00 b01 Cmd alimentation HT",
        "<< de la consigne de HT: ",
        (39719, 32648, 39764, 39649, 39775, 39641, 41291, 41414, 41495, 41480),
    ),
    _rule(
        ParameterPage.HT,
        2,
        "< HT",
        "Consigne HT",
        -0.1,
        (6.0, 20.0),
        "C9NI6703",
        "00 OUT00 b01 Cmd alimentation HT",
        "< de la consigne de HT: ",
        (70835, 70862, 70846, 70809, 70856, 70801, 70941, 70975, 70984, 70927),
    ),
    _rule(
        ParameterPage.HT,
        4,
        "> HT",
        "Consigne HT",
        0.1,
        (6.0, 20.0),
        "C9NI6703",
        "00 OUT00 b01 Cmd alimentation HT",
        "> de la consigne de HT: ",
        (61317, 60670, 60645, 60592, 60664, 60583, 60742, 60776, 60785, 60722),
    ),
    _rule(
        ParameterPage.HT,
        8,
        ">> HT",
        "Consigne HT",
        1.0,
        (6.0, 20.0),
        "C9NI6703",
        "00 OUT00 b01 Cmd alimentation HT",
        ">> de la consigne de HT: ",
        (75581, 75477, 75461, 75435, 75471, 75427, 75536, 75573, 75592, 75522),
    ),
    _rule(
        ParameterPage.HT,
        16,
        "<< Préampli",
        "Consigne préampli",
        -5.0,
        (200.0, 400.0),
        "C8NI6703",
        "06 OUT06 b25 Cmd amplitude HF préampli",
        "<< de la consigne du Préamplificateur: ",
        (49298, 49344, 49328, 49259, 49338, 49251, 78605, 78639, 78560, 78590),
    ),
    _rule(
        ParameterPage.HT,
        32,
        "< Préampli",
        "Consigne préampli",
        -1.0,
        (200.0, 400.0),
        "C8NI6703",
        "06 OUT06 b25 Cmd amplitude HF préampli",
        "< de la consigne du Préamplificateur: ",
        (69206, 69233, 69217, 69180, 69227, 69172, 69293, 69327, 69335, 69278),
    ),
    _rule(
        ParameterPage.HT,
        64,
        "> Préampli",
        "Consigne préampli",
        1.0,
        (200.0, 400.0),
        "C8NI6703",
        "06 OUT06 b25 Cmd amplitude HF préampli",
        "> de la consigne du Préamplificateur: ",
        (15553, 72065, 72049, 72012, 72059, 72004, 72124, 72158, 72166, 72110),
    ),
    _rule(
        ParameterPage.HT,
        128,
        ">> Préampli",
        "Consigne préampli",
        5.0,
        (200.0, 400.0),
        "C8NI6703",
        "06 OUT06 b25 Cmd amplitude HF préampli",
        ">> de la consigne du Préamplificateur: ",
        (73668, 73562, 73545, 73519, 73555, 72042, 73626, 73660, 73679, 73612),
    ),
    _rule(
        ParameterPage.HF,
        1,
        "<< Att HF",
        "Cons Atténuateur HF",
        -5.0,
        (0.0, 20.0),
        "C8NI6703",
        "04 OUT04 b17 Cmd Pos. Atténuateur",
        "<< de la consigne de l'atténuateur HF: ",
        (56367, 56435, 56397, 56337, 56421, 56325, 58290, 58321, 58433, 58355),
    ),
    _rule(
        ParameterPage.HF,
        2,
        "< Att HF",
        "Cons Atténuateur HF",
        -1.0,
        (0.0, 20.0),
        "C8NI6703",
        "04 OUT04 b17 Cmd Pos. Atténuateur",
        "< de la consigne de l'atténuateur HF: ",
        (74075, 74102, 74086, 74049, 74096, 74041, 74167, 74207, 74216, 74147),
    ),
    _rule(
        ParameterPage.HF,
        4,
        "> Att HF",
        "Cons Atténuateur HF",
        1.0,
        (0.0, 20.0),
        "C8NI6703",
        "04 OUT04 b17 Cmd Pos. Atténuateur",
        "> de la consigne de l'atténuateur HF: ",
        (51397, 52918, 52896, 52858, 52907, 52850, 52981, 53024, 53036, 52966),
    ),
    # Native d301 and original Add input are 1, not 5. Do not symmetrize.
    _rule(
        ParameterPage.HF,
        8,
        ">> Att HF",
        "Cons Atténuateur HF",
        1.0,
        (0.0, 20.0),
        "C8NI6703",
        "04 OUT04 b17 Cmd Pos. Atténuateur",
        ">> de la consigne de l'atténuateur HF: ",
        (68795, 68568, 68552, 68526, 68562, 57063, 68679, 68787, 68807, 68627),
    ),
    _rule(
        ParameterPage.HF,
        16,
        "<< déphaseur HF",
        "Consigne déphaseur HF",
        -10.0,
        (-180.0, 180.0),
        "C8NI6703",
        "03 OUT03 b13 Cmd Pos. Déphaseur",
        "<< de la consigne du déphaseur HF: ",
        (26839, 58641, 58624, 58597, 58635, 58078, 58707, 58742, 58768, 58692),
    ),
    _rule(
        ParameterPage.HF,
        32,
        "< déphaseur HF",
        "Consigne déphaseur HF",
        -1.0,
        (-180.0, 180.0),
        "C8NI6703",
        "03 OUT03 b13 Cmd Pos. Déphaseur",
        "< de la consigne du déphaseur HF: ",
        (59269, 59005, 58982, 58956, 58995, 58947, 59175, 59254, 59301, 59151),
    ),
    _rule(
        ParameterPage.HF,
        64,
        "> déphaseur HF",
        "Consigne déphaseur HF",
        1.0,
        (-180.0, 180.0),
        "C8NI6703",
        "03 OUT03 b13 Cmd Pos. Déphaseur",
        "> de la consigne du déphaseur HF: ",
        (58370, 63106, 63088, 63059, 63099, 63050, 63176, 63225, 63249, 63159),
    ),
    _rule(
        ParameterPage.HF,
        128,
        ">> déphaseur HF",
        "Consigne déphaseur HF",
        10.0,
        (-180.0, 180.0),
        "C8NI6703",
        "03 OUT03 b13 Cmd Pos. Déphaseur",
        ">> de la consigne du déphaseur HF: ",
        (71649, 71544, 71528, 71502, 71538, 71494, 71606, 71641, 71661, 71591),
    ),
)

PROCEDURE_FIELD_MAPS = {
    ParameterPage.FLUIDES: (
        ("Marche régulation", "Marche refroidissement X"),
        ("Arrêt régulation", "Arret refroidissement X"),
    ),
    ParameterPage.HT: (
        ("Marche HT", "X Marche alimentation HT"),
        ("Arrêt HT", "X Arrêt alimentation HT"),
        ("Reset HT", "X Reset alimentation HT"),
        ("Marche pulse MOD", "X Marche impulsion mod"),
        ("Arrêt pulse MOD", "X Arret impulsion mod"),
    ),
    ParameterPage.HF: (
        ("Marche att./déph.", "X Marche Att Déph"),
        ("Arrêt att./déph.", "X Arret Att Déph"),
    ),
}
PROCEDURE_ERROR_PREFIXES = {
    ParameterPage.FLUIDES: ERROR_LEAD + "de M/A du groupe de régulation: ",
    ParameterPage.HT: ERROR_LEAD + "de M/A/R du groupe de HT: ",
    ParameterPage.HF: ERROR_LEAD + "de M/A du groupe HF: ",
}
TIMING_CONTROLS = (
    "Délais Modulateur:",
    "Largeur Modulateur:",
    "Délais HF:",
    "Largeur HF:",
)


@dataclass(frozen=True)
class TimingControlIntent:
    trigger: str
    control: str
    disabled_enum: int
    property_uid: int


@dataclass(frozen=True)
class ParameterPagePlan:
    page: ParameterPage
    event_index: int
    branch: ParameterBranch
    mask: int
    active_dps_fields: tuple[str, ...]
    rule: ParameterRule | None
    incoming_numeric: float | None
    projected_numeric: float | None
    dps_patches: tuple[tuple[str, bool], ...]
    projected_dps: tuple[tuple[str, bool], ...] | None
    controller_patch: tuple[str, float] | None
    psp_url: str | None
    ui_base: ParameterUiBase | None
    ui_patches: tuple[tuple[str, bool | float], ...]
    timing_control_intents: tuple[TimingControlIntent, ...]
    error_prefix: str | None
    wait_ms: int
    ui_reset_after_wait: bool
    # A wait gates UI reset only, not the parallel controller/PSP sinks.
    wait_orders_controller_writes: bool = field(default=False, init=False)
    local_write_conditioned_on_psp_success: bool = field(default=False, init=False)
    local_and_psp_writes_serialized: bool = field(default=False, init=False)
    queued: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    establishes_physical_state: bool = field(default=False, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)
    unresolved_boundaries: tuple[str, ...] = field(
        default=(
            "binary NewVal order/decoding and original byte-string encoding",
            "fresh local/controller/page snapshots and concurrent overwrite",
            "same-frame sink ordering, scheduler and conflicting property writes",
            "server acceptance, procedure completion and physical readback",
            "current endpoint ownership, units, limits, polarity and permissives",
            "retired DAQ routes must not become modern fallback routes",
            "native quirks are observations, not approved web safety policy",
        ),
        init=False,
    )

    @property
    def write_intent_observed(self) -> bool:
        return self.psp_url is not None

    @property
    def conflicting_timing_intents(self) -> bool:
        return len({p.disabled_enum for p in self.timing_control_intents}) > 1


def _booleans(value, names, label) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} requires a named Boolean mapping")
    result = dict(value)
    if set(result) != set(names):
        raise ValueError(f"{label} requires exactly the evidenced fields")
    if any(type(v) is not bool for v in result.values()):
        raise TypeError(f"{label} cannot coerce unknown/non-Boolean values")
    return result


def _finite_dbl(value) -> float:
    if type(value) not in (int, float):
        raise TypeError("Explicit finite numeric DBL projection required")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("Numeric value cannot be represented as finite DBL") from exc
    if not math.isfinite(number):
        raise ValueError("Non-finite DBL behavior is outside this contract")
    return number


def plan_parameter_page_change(
    page: ParameterPage,
    current_dps: Mapping[str, bool],
    arrows: Mapping[str, bool],
    procedures: Mapping[str, bool],
    numeric_newval: Mapping[str, float],
) -> ParameterPagePlan:
    """Project selected named inputs. No full cluster or hardware state inferred.

    All arrow/procedure flags are required, even opposing True flags. Only the
    selected numeric field is required; native no-op paths do not inspect it.
    Procedure flags are ignored whenever any arrow is True. Original busy DPS
    suppresses procedures, not arrows. Multiple arrows reach native Default.
    """
    if not isinstance(page, ParameterPage):
        raise TypeError("Explicit ParameterPage required")
    rules = tuple(r for r in PARAMETER_RULES if r.page is page)
    dps = _booleans(current_dps, DPS_FIELDS, "Whole local DPS snapshot")
    buttons = _booleans(arrows, tuple(r.arrow for r in rules), "NewVal arrows")
    field_map = PROCEDURE_FIELD_MAPS[page]
    commands = _booleans(
        procedures, tuple(s for s, _ in field_map), "NewVal procedures"
    )
    if not isinstance(numeric_newval, Mapping):
        raise TypeError("Named Event NewVal numeric projection required")
    allowed_numeric = {r.numeric_field for r in rules}
    if set(numeric_newval) - allowed_numeric:
        raise ValueError("Unrecognized Event NewVal numeric field")
    active = tuple(name for name in DPS_FIELDS if dps[name])
    mask = sum(r.mask for r in rules if buttons[r.arrow])
    rule = next((r for r in rules if r.mask == mask), None)
    patches = ()
    projected_dps = None
    numeric = projected_numeric = None
    controller_patch = None
    ui_base = None
    ui_patches = ()
    properties = ()
    prefix = url = None
    wait = 0
    if mask == 0 and not active:
        branch = ParameterBranch.PROCEDURE
        patches = tuple((target, commands[source]) for source, target in field_map)
        dps.update(patches)
        projected_dps = tuple((name, dps[name]) for name in DPS_FIELDS)
        url = DPS_URL
        prefix = PROCEDURE_ERROR_PREFIXES[page]
        wait = 200 if page is ParameterPage.FLUIDES else 0
        if page is ParameterPage.HT:
            # Start ENABLES (0), stop DISABLES (1). No dependency between cases.
            properties = tuple(
                TimingControlIntent(trigger, name, value, uid)
                for trigger, value, uids in (
                    ("Marche pulse MOD", 0, (7002, 67505, 68962, 70250)),
                    ("Arrêt pulse MOD", 1, (67577, 67619, 67657, 67698)),
                )
                if commands[trigger]
                for name, uid in zip(TIMING_CONTROLS, uids, strict=True)
            )
    elif mask == 0:
        branch = ParameterBranch.BUSY_PROCEDURE_DISCARDED
    elif rule is None:
        branch = ParameterBranch.DEFAULT_NO_OP
    else:
        branch = ParameterBranch.ADJUSTMENT
        if rule.numeric_field not in numeric_newval:
            raise ValueError("Selected Event NewVal numeric field is missing")
        numeric = _finite_dbl(numeric_newval[rule.numeric_field])
        projected_numeric = _finite_dbl(numeric + rule.delta)
        if rule.limits is not None:
            low, high = rule.limits
            projected_numeric = max(low, min(high, projected_numeric))
        controller_patch = (rule.controller_field, projected_numeric)
        url = f"ni.var.psp://localhost/SUPERVISION/{rule.controller}"
        prefix = rule.error_prefix
        wait = 200
        ui_base = (
            ParameterUiBase.LOCAL_PAGE
            if page is ParameterPage.FLUIDES
            else ParameterUiBase.EVENT_NEWVAL
        )
        reset = tuple(r.arrow for r in rules)
        if page is ParameterPage.FLUIDES:
            reset = (
                ("> Canon", "> Canon", "> Section", "< Section")
                if mask == 4
                else ("> Canon", "< Canon", "> Section", "< Section")
            )
        elif page is ParameterPage.HF:
            reset = (
                ">> Att HF",
                "<< Att HF",
                "> Att HF",
                "< Att HF",
                ">> déphaseur HF",
                "<< déphaseur HF",
                "> déphaseur HF",
                "< déphaseur HF",
            )
        ui_patches = ((rule.numeric_field, projected_numeric),) + tuple(
            (name, False) for name in reset
        )
    return ParameterPagePlan(
        page,
        {ParameterPage.FLUIDES: 14, ParameterPage.HT: 15, ParameterPage.HF: 16}[page],
        branch,
        mask,
        active,
        rule,
        numeric,
        projected_numeric,
        patches,
        projected_dps,
        controller_patch,
        url,
        ui_base,
        ui_patches,
        properties,
        prefix,
        wait,
        branch is ParameterBranch.ADJUSTMENT,
    )


def project_parameter_ui(
    plan: ParameterPagePlan,
    base_source: ParameterUiBase,
    supplied_base: Mapping[str, object],
) -> dict[str, object]:
    """Apply evidenced patches to explicitly supplied appropriate page snapshot.

    Unrelated fields are retained. Missing/incorrect base fields fail closed.
    Duplicate Fluides reset is deliberately retained in the plan; < Canon
    stays unchanged in mask 4. No UI, wait or local assignment is performed.
    """
    if not isinstance(plan, ParameterPagePlan) or plan.ui_base is None:
        raise ValueError("Adjustment plan with a UI write intent required")
    if base_source is not plan.ui_base:
        raise ValueError("Wrong source snapshot for native UI replacement")
    if not isinstance(supplied_base, Mapping):
        raise TypeError("Explicit page snapshot required")
    result = dict(supplied_base)
    for name, value in plan.ui_patches:
        if name not in result:
            raise ValueError(f"Missing UI base field: {name}")
        if type(value) is bool:
            if type(result[name]) is not bool:
                raise TypeError("UI arrow base must be Boolean")
        else:
            _finite_dbl(result[name])
        result[name] = value
    return result


def project_parameter_error(
    plan: ParameterPagePlan,
    stored_ter: str,
    write_error: ErrorCluster | None,
) -> str:
    """Hypothetical PSP result only; No Error retains TER and nothing rolls back.

    Prefixes are native-readable text, not a qualified original byte encoding.
    Busy/default paths produce no-error constants, not a PSP result.
    """
    if not isinstance(plan, ParameterPagePlan) or type(stored_ter) is not str:
        raise TypeError("ParameterPagePlan and exact stored TER required")
    if not plan.write_intent_observed:
        if write_error is not None:
            raise ValueError("No-op path has no PSP result")
        return stored_ter
    if not isinstance(write_error, ErrorCluster):
        raise TypeError("Explicit hypothetical PSP ErrorCluster required")
    if type(write_error.status) is not bool or type(write_error.source) is not str:
        raise TypeError("Exact error status Boolean and source string required")
    if type(write_error.code) is not int:
        raise TypeError("Exact signed I32 error code required")
    if not -(2**31) <= write_error.code < 2**31:
        raise ValueError("Error code outside signed I32 range")
    return plan.error_prefix + write_error.source if write_error.status else stored_ter
