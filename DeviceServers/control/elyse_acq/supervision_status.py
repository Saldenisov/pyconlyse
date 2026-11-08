"""Pure Supervision display projections from saved LabVIEW wiring.

These are raw Boolean copies, not safety decisions or hardware readback
validation. No EPS "OK" bit is substituted for a C4 digital input.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence


# 0_SUP_ELYSE.vi sequence 36869 frame 17: source C4_IN_DIO96 field index
# to destination Page HT field name. The copied VI has direct, non-inverted
# wires for these seven assignments.
_HT_FLAGS = {
    "V HT": 35,
    "I HT": 36,
    "Radioprotection": 46,
    "Relais 1 HT": 37,
    "Relais 2 HT": 32,
    "HT en marche": 48,
    "HT en défaut": 49,
}

# 0_SUP_ELYSE.vi sequence 36869 frame 16: raw C4 input index to
# Page Radioprotection display field. This is a display mapping only.
_RADIOPROTECTION_FLAGS = {
    "Porte lourde": 53,
    "Porte légére": 52,
    "Porte de Secours": 54,
    "Porte Laser": 55,
    "Rondiers": 60,
    "Occulteur LASER": 63,
    "BACO-TIR EN/HORS": 62,
    "BACO PA/MOD": 61,
    "RONDIER 1": 57,
    "RONDIER 2": 58,
    "RONDIER 3": 59,
    "ARRETS D'URGENCE": 56,
}

# 0_SUP_ELYSE.vi sequence 36869 frame 8: raw C3/C4 inputs to Page Fluides.
# These are display copies, not EPS completion flags or permissive decisions.
_FLUIDES_C3_FLAGS = {
    "Canon 220V": 0,
    "Canon Défauts": 1,
    "Canon Pressostat": 4,
    "Section 220V": 6,
    "Section Défauts": 7,
    "Section Pressostat": 10,
}
_FLUIDES_C4_FLAGS = {
    "Canon débimètre": 19,
    "Section débimètre": 38,
    "Résistivité": 39,
}

# 0_SUP_ELYSE.vi sequence 49452 frame 10: EPS software-status fields to
# Page Modulateur's five named OK indicators. These are not direct NI inputs.
_MODULATOR_STAGE_OK_EPS_FIELDS = {
    "GENERAL MOD OK": 8,
    "CHAUFFAGE OK": 14,
    "PREMA OK": 20,
    "RELAIS HT OK": 26,
    "FOCALES OK": 32,
}


def _validate_c4_snapshot(c4_in_dio96: Sequence[bool]) -> None:
    if len(c4_in_dio96) != 64 or any(type(bit) is not bool for bit in c4_in_dio96):
        raise ValueError("C4_IN_DIO96 must contain exactly 64 Boolean fields")


def project_ht_display_flags(c4_in_dio96: Sequence[bool]) -> Dict[str, bool]:
    """Copy seven raw C4 input bits to Page HT display fields.

    This does not decode electrical polarity, enable a control, or assert
    that an EPS procedure finished. The caller must distinguish these display
    bits from command intent and verified safety interlock state.
    """

    _validate_c4_snapshot(c4_in_dio96)
    return {display: c4_in_dio96[index] for display, index in _HT_FLAGS.items()}


def project_radioprotection_display_flags(
    c4_in_dio96: Sequence[bool],
) -> Dict[str, bool]:
    """Copy 12 raw C4 inputs to the Page Radioprotection display.

    The display values do not imply interlock permission, electrical
    polarity, a general-stop transition, or current readback validity.
    """

    _validate_c4_snapshot(c4_in_dio96)
    return {
        display: c4_in_dio96[index]
        for display, index in _RADIOPROTECTION_FLAGS.items()
    }


def project_fluides_raw_display_flags(
    c3_in_dio96: Sequence[bool], c4_in_dio96: Sequence[bool]
) -> Dict[str, bool]:
    """Copy nine raw digital-input bits to Page Fluides display fields.

    The saved Supervision frame also copies analog C1 temperature readings,
    which this Boolean projection deliberately excludes. No bit here proves
    physical flow or readiness; electrical polarity is unresolved.
    """

    if len(c3_in_dio96) != 56 or any(
        type(bit) is not bool for bit in c3_in_dio96
    ):
        raise ValueError("C3_IN_DIO96 must contain exactly 56 Boolean fields")
    _validate_c4_snapshot(c4_in_dio96)
    return {
        **{display: c3_in_dio96[index]
           for display, index in _FLUIDES_C3_FLAGS.items()},
        **{display: c4_in_dio96[index]
           for display, index in _FLUIDES_C4_FLAGS.items()},
    }


def project_modulator_stage_ok_from_eps(eps: Sequence[bool]) -> Dict[str, bool]:
    """Copy five EPS software flags to Page Modulateur OK indicators.

    The source EPS cluster is published by ACQ and ingested by Supervision.
    These indicator values do not establish real relay state, stage order,
    bank freshness, or permission to operate hardware.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    return {name: eps[index]
            for name, index in _MODULATOR_STAGE_OK_EPS_FIELDS.items()}


def radioprotection_graph_summary(page: Mapping[str, bool]) -> bool:
    """Return the saved Supervision graph's eight-input Boolean aggregate.

    This is not an equipment safety interlock or an authorization to command
    HT. Individual RONDIER 1-3 fields are displayed but not inputs here.
    """

    if set(page) != set(_RADIOPROTECTION_FLAGS) or any(
        type(value) is not bool for value in page.values()
    ):
        raise ValueError("Page Radioprotection must contain exactly 12 Boolean fields")
    return (
        page["Porte lourde"]
        and page["Porte légére"]
        and page["Porte de Secours"]
        and page["Porte Laser"]
        and not page["Rondiers"]
        and page["ARRETS D'URGENCE"]
        and not page["BACO-TIR EN/HORS"]
        and page["BACO PA/MOD"]
    )
