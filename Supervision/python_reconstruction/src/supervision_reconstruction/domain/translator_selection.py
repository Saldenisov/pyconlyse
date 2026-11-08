"""Event 3 Laser/T1/T2/T3 branches; no physical translator move is inferred.

Only the selected C5 fields are patched. Other cameras are NOT switched off by
these branches. UI color and PSP write in frame 0 are unordered; T1/T2/T3 color
restore and Wait(2000) also coexist without a dependency in frame 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .event_effects import EffectIntent, SequenceFrameIntent, UiPatch


class TranslatorSelection(IntEnum):
    LASER = 1
    T1 = 2
    T2 = 3
    T3 = 4


@dataclass(frozen=True)
class TranslatorSelectionPlan:
    selection: TranslatorSelection
    sequence_uid: int
    assignments: tuple[tuple[str, bool], ...]
    frames: tuple[SequenceFrameIntent, ...]
    switches_other_cameras_off: bool = False
    commands_position: bool = False
    external_effects_blocked: bool = field(default=True, init=False)


_FIELDS = {
    TranslatorSelection.LASER: (
        "03 CPB3 b75 M/A Caméra chambre de préparation",
        "05 CPB5 b71 M/A Caméra Miroir",
    ),
    TranslatorSelection.T1: (
        "01 CPB1 b79 Alimentation moteur",
        "07 CPB7 b67 M/A Eclairage Ecran 1",
        "09 CPC1 b63 M/A Caméra Ecran 1",
        "31 DPB7 b68 M/A Alimentation Ecrans",
    ),
    TranslatorSelection.T2: (
        "01 CPB1 b79 Alimentation moteur",
        "13 CPC5 b55 M/A Eclairage Ecran 2",
        "15 CPC7 b51 M/A Caméra Ecran 2",
        "31 DPB7 b68 M/A Alimentation Ecrans",
    ),
    TranslatorSelection.T3: (
        "01 CPB1 b79 Alimentation moteur",
        "19 DPA3 b92 M/A Eclairage Ecran 3",
        "21 DPA5 b88 M/A Caméra Ecran 3",
        "31 DPB7 b68 M/A Alimentation Ecrans",
    ),
}
_UIDS = {
    TranslatorSelection.LASER: (60090, 60397, 60437, 67340, 60491, 60907, 61219),
    TranslatorSelection.T1: (74459, 74822, 74915, 75146, 75085, 75401, 75804),
    TranslatorSelection.T2: (85690, 85810, 85829, 85871, 85846, 86127, 85988),
    TranslatorSelection.T3: (9933, 13265, 13366, 13984, 13677, 16822, 16529),
}


def plan_translator_selection(
    selection: TranslatorSelection,
) -> TranslatorSelectionPlan:
    if not isinstance(selection, TranslatorSelection):
        raise ValueError("selection requires LASER/T1/T2/T3; Arrêt has a separate plan")
    seq, bundle, write, handler, color, wait, restore = _UIDS[selection]
    assignments = tuple((name, True) for name in _FIELDS[selection])
    effects = (
        EffectIntent("bundle C5_OUT_DIO96", bundle, assignments),
        EffectIntent(
            "sharedVariableDynamicWrite",
            write,
            (
                ("data", "bundle result"),
                ("url", "ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96"),
            ),
        ),
        EffectIntent("Simple Error Handler.vi", handler, (("after", write),)),
    )
    delay = EffectIntent("Wait (ms)", wait, (("ms", 2000),))
    laser = selection is TranslatorSelection.LASER
    frames = (
        SequenceFrameIntent(
            0,
            effects + ((delay,) if laser else ()),
            (
                UiPatch("Translateurs", "Colors", (7171459, 7171459), color),
                UiPatch("C5_OUT_DIO96", "Value", "bundle result"),
            ),
        ),
        SequenceFrameIntent(
            1,
            () if laser else (delay,),
            (UiPatch("Translateurs", "Colors", (12171705, 12171705), restore),),
            note="T1/T2/T3 wait does NOT serialize the same-frame color restore",
        ),
    )
    return TranslatorSelectionPlan(selection, seq, assignments, frames)
