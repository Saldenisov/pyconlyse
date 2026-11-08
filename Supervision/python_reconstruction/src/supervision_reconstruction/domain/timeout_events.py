"""Event 0: historical PSP/readback and local-counter projection, offline only.

Historical NI6703 magnet fields do not establish current Device Server ownership.
No stale-data policy, driver success, acknowledgement or GUI schedule is invented.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from .event_effects import EffectIntent, SequenceFrameIntent, UiPatch


@dataclass(frozen=True)
class SharedReadIntent:
    node_uid: int
    local_cluster: str
    previous_error_node_uid: int | None
    observed_url: str | None
    frame_index: int
    local_result_write_error_gated: bool = False
    external_effects_blocked: bool = field(default=True, init=False)


def timeout_read_chain() -> tuple[SharedReadIntent, ...]:
    groups = (
        (35960, "DPC"),
        (36097, "DPS"),
        (36228, "VDD"),
        (36360, "VAD"),
        (12682, "C3_OUT_DIO96"),
        (12956, "C4_OUT_DIO96"),
        (19970, "C5_OUT_DIO96"),
        (27617, "C10-11 NI6602"),
        (12699, "C6NI6703"),
        (13185, "C7NI6703"),
        (13825, "C8NI6703"),
        (17409, "C9NI6703"),
        (8475, "VTA"),
    )
    explicit = {
        "DPC": "DPC",
        "DPS": "DPS",
        "VDD": "VDD",
        "VAD": "VAD",
        "C3_OUT_DIO96": "C3_OUT_DIO96",
        "C4_OUT_DIO96": "C4_OUT_DIO96",
        "C5_OUT_DIO96": "C5_OUT_DIO96",
        "C10-11 NI6602": "C1011NI6602",
        "C6NI6703": "C6NI6703",
        "C7NI6703": "C7NI6703",
        "C8NI6703": "C8NI6703",
        "C9NI6703": "C9NI6703",
        "VTA": "VTS",
    }
    chain = tuple(
        SharedReadIntent(
            uid,
            name,
            groups[i - 1][0] if i else None,
            "ni.var.psp://localhost/SUPERVISION/" + explicit[name]
            if name in explicit
            else None,
            1 if name == "VTA" else 0,
        )
        for i, (uid, name) in enumerate(groups)
    )
    # This second NI6602 read in frame 2 starts an independent error chain.
    return chain + (
        SharedReadIntent(
            51964,
            "C10-11 NI6602",
            None,
            "ni.var.psp://localhost/SUPERVISION/C1011NI6602",
            2,
        ),
    )


def timeout_motor_numbers(channel: int) -> tuple[int, ...]:
    if type(channel) is not int or not 0 <= channel <= 65535:
        raise ValueError("channel requires an externally decoded U16")
    if channel in (0, 3):
        return ()
    return (3, 4) if channel == 1 else (1, 2)  # native 2/Default


def plan_timeout_visual_refresh(channel: int) -> SequenceFrameIntent:
    """Frame 3 uses property results, not image buffers or camera driver reads."""
    return SequenceFrameIntent(
        3,
        (
            EffectIntent(
                "SOURCE property read",
                13299,
                (("properties", ("Image Center Position", "Current ROI Tool", "ROI")),),
            ),
            EffectIntent(
                "CALCULS property write",
                3135,
                (("values", "SOURCE property results"), ("after", 13299)),
            ),
            EffectIntent("Get Date/Time In Seconds", 22261),
            EffectIntent(
                "Format Date/Time String",
                22342,
                (("after", 22261), ("format", "Le %d/%m/%y   %H:%M:%S")),
            ),
        ),
        (
            UiPatch("Motor numbers", "Value", timeout_motor_numbers(channel), 22389),
            UiPatch(
                "Date et heure",
                "Value",
                "external Format Date/Time String result",
                22330,
            ),
        ),
        note=(
            "ROI copy, date formatting and motor selection are independent "
            "same-frame paths"
        ),
    )


@dataclass(frozen=True)
class CounterRequestPlan:
    legacy_guard: bool
    task_index: int | None
    page_field_indices: tuple[int, int] | None
    frames: tuple[SequenceFrameIntent, ...]
    helper_error_controls_reset: bool = False
    concurrent_local_write: str = (
        "received cluster also writes local in the guard frame"
    )
    external_effects_blocked: bool = field(default=True, init=False)


def plan_timeout_counter_request(
    number: float,
    *,
    counter_task_identities: tuple[str, ...],
    local_page_sync: tuple[float, ...],
) -> CounterRequestPlan:
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise ValueError("number requires a DBL counter-selection result")
    if not math.isfinite(number):
        raise ValueError("nonfinite counter selection is unqualified")
    if number <= 16.0:
        return CounterRequestPlan(False, None, None, ())
    index = math.floor((number - 17.0) / 2.0)
    if not 0 <= index < 8 or len(counter_task_identities) <= index:
        raise ValueError(
            "legacy Index Array fallback cannot select an unqualified task"
        )
    if len(local_page_sync) != 33:
        raise ValueError("Page Synchronisation requires 33 ordered DBL fields")
    a, b = 16 + 2 * index, 17 + 2 * index
    values = (local_page_sync[a], local_page_sync[b])
    if any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
        for x in values
    ):
        raise ValueError("delay and width require finite externally decoded DBL values")
    task = counter_task_identities[index]
    if not isinstance(task, str):
        raise ValueError("task identity is an external symbolic refnum, not a driver")
    frames = (
        SequenceFrameIntent(
            0,
            (
                EffectIntent(
                    "1_SUP_WRITE_NI6602.vi",
                    67590,
                    (("task", task), ("delay", values[0]), ("width", values[1])),
                ),
            ),
        ),
        SequenceFrameIntent(
            1,
            (),
            (UiPatch("C10-11 NI6602", "N° du compteur", -1.0, 58233),),
            note="patch a FRESH local cluster; not received PSP payload",
        ),
        SequenceFrameIntent(
            2,
            (
                EffectIntent(
                    "sharedVariableDynamicWrite",
                    49916,
                    (
                        ("data", "fresh local C10-11 NI6602"),
                        ("url", "ni.var.psp://localhost/SUPERVISION/C1011NI6602"),
                    ),
                ),
            ),
        ),
    )
    return CounterRequestPlan(True, index, (a, b), frames)


@dataclass(frozen=True)
class RefreshRule:
    source_cluster: str
    source_field: str
    target_cluster: str
    target_path: str
    bundle_uid: int


def _rules(source, fields, target, paths, uid):
    return tuple(
        RefreshRule(source, a, target, b, uid)
        for a, b in zip(fields, paths, strict=True)
    )


REFRESH_RULES = (
    *_rules(
        "C1NI6071E",
        (
            "28 ACH28 b60 Mes I Dipôle 1",
            "20 ACH20 b59 Mes I Solénoïde",
            "45 ACH45 b80 Mesure phase HF1",
            "29 ACH29 b62 Mes I Guidage H1",
            "22 ACH22 b63 Mes I Guidage V1",
            "30 ACH30 b64 Mes I Guidage H2",
            "23 ACH23 b65 Mes I Guidage V2",
            "16 ACH16 b51 Mes I Triplet 1-1",
            "24 ACH24 b52 Mes I Triplet 1-2",
            "31 ACH31 b66 Mes I correcte Dipôle 1 (H3)",
            "32 ACH32 b67 Mes I Guidage V3",
        ),
        "Voie directe",
        tuple(
            x + ".Lecture"
            for x in (
                "Dipôle 1",
                "Focale",
                "Phase HF / Laser",
                "Correcteur H1",
                "Correcteur V1",
                "Correcteur H2",
                "Correcteur V2",
                "Triplet 1-1",
                "Triplet 1-2",
                "Correcteur H3",
                "Correcteur V3",
            )
        ),
        12099,
    ),
    *_rules(
        "C6NI6703",
        (
            "00 OUT00 b01 Cmd Guidage H1",
            "01 OUT01 b05 Cmd Guidage V1",
            "02 OUT02 b09 Cmd Guidage H2",
            "03 OUT03 b13 Cmd Guidage V2",
            "04 OUT04 b17 Cmd Guidage H3",
            "05 OUT05 b21 Cmd Guidage V3",
        ),
        "Voie directe",
        tuple(
            x + ".Consigne"
            for x in (
                "Correcteur H1",
                "Correcteur V1",
                "Correcteur H2",
                "Correcteur V2",
                "Correcteur H3",
                "Correcteur V3",
            )
        ),
        11207,
    ),
    *_rules(
        "C7NI6703",
        (
            "08 OUT08 b33 Cmd I Dipôle 1",
            "05 OUT05 b21 Cmd I Solénoïde",
            "00 OUT00 b01 Cmd I Triplet 1-1",
            "01 OUT01 b05 Cmd I Triplet 1-2",
        ),
        "Voie directe",
        tuple(
            x + ".Consigne"
            for x in ("Dipôle 1", "Focale", "Triplet 1-1", "Triplet 1-2")
        ),
        11207,
    ),
    *_rules(
        "C8NI6703",
        ("05 OUT05 b21 Cmd déphasage HF/LASER",),
        "Voie directe",
        ("Phase HF / Laser.Consigne",),
        11207,
    ),
    *_rules(
        "C6NI6703",
        (
            "06 OUT06 b25 Cmd Guidage H4",
            "07 OUT07 b29 Cmd Guidage V4",
            "09 OUT09 b37 Cmd Guidage V5",
            "08 OUT08 b33 Réserve",
        ),
        "Voie déviée",
        tuple(
            x + ".Consigne"
            for x in (
                "Correcteur H4",
                "Correcteur V4",
                "Correcteur V5",
                "Correcteur H5",
            )
        ),
        24030,
    ),
    *_rules(
        "C7NI6703",
        (
            "09 OUT09 b37 Cmd I Dipôle 2",
            "06 OUT06 b25 Cmd I Quad 1",
            "07 OUT07 b29 Cmd I Quad 2",
            "03 OUT03 b13 Cmd I Triplet 2-1",
            "04 OUT04 b17 Cmd I Triplet 2-2",
        ),
        "Voie déviée",
        tuple(
            x + ".Consigne"
            for x in (
                "Dipôle 2",
                "Quadrupôle 1",
                "Quadrupôle 2",
                "Triplet 2-1",
                "Triplet 2-2",
            )
        ),
        24030,
    ),
    *_rules(
        "C1NI6071E",
        (
            "19 ACH19 b57 Mes I Quadripôle 1",
            "27 ACH27 b58 Mes I Quadripôle 2",
            "25 ACH25 b54 Mes I Triplet 2-1",
            "18 ACH18 b55 Mes I Triplet 2-2",
            "40 ACH40 b68 Mes I correcte Dipôle 21 (H4)",
            "33 ACH33 b69 Mes I Guidage V4",
            "21 ACH21 b61 Mes I Dipôle 2",
            "34 ACH34 b71 Mes I Guidage V5",
            "34 ACH34 b71 Mes I Guidage V5",  # original duplicated H5/V5 readback
        ),
        "Voie déviée",
        tuple(
            x + ".Lecture"
            for x in (
                "Quadrupôle 1",
                "Quadrupôle 2",
                "Triplet 2-1",
                "Triplet 2-2",
                "Correcteur H4",
                "Correcteur V4",
                "Dipôle 2",
                "Correcteur H5",
                "Correcteur V5",
            )
        ),
        29056,
    ),
    *_rules(
        "C8NI6703",
        ("01 OUT01 b05 Cmd Temp. Canon", "02 OUT02 b09 Cmd Temp. Section"),
        "Page Fluides",
        ("T° CANON:", "T° SECTION:"),
        53197,
    ),
    *_rules(
        "DPS",
        ("Arret refroidissement X", "Marche refroidissement X"),
        "Page Fluides",
        ("Arrêt régulation", "Marche régulation"),
        51051,
    ),
    *_rules(
        "DPS",
        (
            "X Marche alimentation aimant",
            "X Arrêt alimentation aimant",
            "X Alimentation aimant = 0V",
            "X Alimentation aimant = PT",
        ),
        "Page Alimentations",
        ("Marche Aimants.", "Arrêt Aimants", "Aimant 0V", "Aimant RUN"),
        51092,
    ),
    *_rules(
        "DPS",
        (
            "X Marche alimentation HT",
            "X Arrêt alimentation HT",
            "X Reset alimentation HT",
            "X Marche impulsion mod",
            "X Arret impulsion mod",
        ),
        "Page HT",
        ("Marche HT", "Arrêt HT", "Reset HT", "Marche pulse MOD", "Arrêt pulse MOD"),
        51150,
    ),
    *_rules(
        "DPS",
        ("X Marche Att Déph", "X Arret Att Déph"),
        "Page HF",
        ("Marche att./déph.", "Arrêt att./déph."),
        51225,
    ),
    *_rules(
        "DPS",
        (
            " X Marche GENERAL Mod.",
            "X Arrêt GENERAL Mod.",
            "X RESET Mod.",
            "X Marche CHAUFFAGE Mod.",
            "X Arrêt CHAUFFAGE Mod.",
            "X Marche PREMA Mod. ",
            "X Arrêt PREMA Mod.",
            " X Marche RELAIS HT Mod.",
            "X Arrêt RELAIS HT Mod.",
            "X Marche FOCALE Mod.",
            "X Arrêt FOCALE Mod.",
        ),
        "Page Modulateur",
        (
            "Marche MOD",
            "Arrêt MOD",
            "Reset MOD",
            "Marche CHAUFFAGE MOD",
            "Arrêt CHAUFFAGE MOD",
            "Marche PREMA MOD",
            "Arrêt PREMA MOD",
            "Marche RELAIS HT MOD",
            "Arrêt RELAIS HT MOD",
            "Marche FOCALES MOD",
            "Arrêt FOCALES MOD",
        ),
        27819,
    ),
)


def project_timeout_fields(
    snapshots: Mapping[str, Mapping[str, object]],
) -> tuple[UiPatch, ...]:
    """Patch only evidenced fields; leave all other local/UI fields untouched."""
    patches = []
    for rule in REFRESH_RULES:
        try:
            value = snapshots[rule.source_cluster][rule.source_field]
        except KeyError as error:
            raise ValueError(
                f"Missing resolved field: {rule.source_cluster}/"
                f"{rule.source_field}; no fabricated zero"
            ) from error
        if rule.source_cluster == "DPS":
            if type(value) is not bool:
                raise ValueError("DPS projection requires decoded Boolean fields")
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Readback/setpoint projection requires finite DBL fields")
        patches.append(
            UiPatch(rule.target_cluster, rule.target_path, value, rule.bundle_uid)
        )
    return tuple(patches)
