"""Pure, non-actuating setpoint arithmetic from copied Supervision VI frames.

Evidence: ``docs/ELYSE_SUP_ACQ_BUSINESS_LOGIC_2026-09-28.md``,
``docs/ELYSE_SUP_FLUIDES_REQUEST_GATE_2026-09-30.md``, and linked saved
LabVIEW frames. This module calculates requested values and the verified
beam-line transfer guard only. It does not publish PSP banks, operate NI cards,
or interpret the still-unresolved X1/X10 Boolean polarity.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple


# UI row indices are those used by the nested Case in events 19/20, not card
# indices. Card-field mappings are recorded separately in the analog crosswalk.
_BEAM_GROUPS: Dict[str, Dict[int, str]] = {
    "direct": {
        0: "dipole_triplet",
        1: "focale",
        2: "phase_hf_laser",
        3: "corrector",
        4: "corrector",
        5: "corrector",
        6: "corrector",
        7: "dipole_triplet",
        8: "dipole_triplet",
        9: "corrector",
        10: "corrector",
    },
    "deviated": {
        0: "dipole_triplet",
        1: "dipole_triplet",
        2: "dipole_triplet",
        3: "dipole_triplet",
        4: "corrector",
        5: "corrector",
        6: "dipole_triplet",
        7: "corrector",
        8: "corrector",
    },
}

# (minimum, maximum, << or >> step choices, < or > step choices)
_BEAM_RULES: Dict[str, Tuple[float, float, Tuple[float, float], Tuple[float, float]]] = {
    "focale": (0.0, 120.0, (10.0, 1.0), (1.0, 0.1)),
    "phase_hf_laser": (0.0, 360.0, (50.0, 5.0), (5.0, 1.0)),
    "dipole_triplet": (-16.0, 16.0, (1.0, 0.1), (0.1, 0.01)),
    "corrector": (-5.0, 5.0, (1.0, 0.1), (0.1, 0.01)),
}

_BEAM_ACTIONS = {128: -1.0, 256: -1.0, 512: 1.0, 1024: 1.0}
_BEAM_COARSE_ACTIONS = frozenset((128, 1024))
_BEAM_CHANGE_MASK = 1937  # Bits 0, 4, 7..10 in each 11-field row.
_BEAM_TRANSFER_THRESHOLD = 128

_HT_STEPS = {1: -1.0, 2: -0.1, 4: 0.1, 8: 1.0}
_PREAMP_STEPS = {16: -5.0, 32: -1.0, 64: 1.0, 128: 5.0}
_HF_ATTENUATION_STEPS = {1: -5.0, 2: -1.0, 4: 1.0, 8: 1.0}
_HF_PHASE_STEPS = {16: -10.0, 32: -1.0, 64: 1.0, 128: 10.0}
# Page Fluides event 14's one-hot Boolean Array To Number cases. Each tuple
# is (C8NI6703 bank index, arithmetic delta). No clamp appears in these cases.
_FLUIDES_TEMPERATURE_STEPS = {
    1: (1, -0.1),  # < Canon
    2: (1, 0.1),   # > Canon
    4: (2, -0.1),  # < Section
    8: (2, 0.1),   # > Section
}


def _finite_number(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _clamped_adjustment(
    current: float, delta: float, minimum: float, maximum: float
) -> float:
    value = _finite_number(current, "current") + delta
    return min(max(value, minimum), maximum)


def beam_group(line: str, row_index: int) -> str:
    """Return nested adjustment group; not a physical channel identity."""

    if type(row_index) is not int:
        raise ValueError(f"unsupported beam line/row: {line!r}/{row_index!r}")
    try:
        return _BEAM_GROUPS[line][row_index]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported beam line/row: {line!r}/{row_index!r}") from exc


def beam_line_transfer_guard(line: str, changed_row_masks: Sequence[int]) -> bool:
    """Whether event 19/20 frame 1 transfers UI rows to local C6/C7(/C8).

    Each mask represents one 11-field row after the saved VI's OldVal/NewVal
    inequality, Cluster To Array, and Boolean Array To Number chain. This is
    *not* a PSP-write guard: event frame 2 republishes C6-C9 even when False.
    """

    try:
        row_count = len(_BEAM_GROUPS[line])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported beam line: {line!r}") from exc
    if len(changed_row_masks) != row_count:
        raise ValueError(f"{line} requires {row_count} changed-row masks")
    for mask in changed_row_masks:
        if type(mask) is not int or not 0 <= mask < (1 << 11):
            raise ValueError(f"invalid 11-field changed-row mask: {mask!r}")
    return max(mask & _BEAM_CHANGE_MASK for mask in changed_row_masks) >= _BEAM_TRANSFER_THRESHOLD


def adjust_beam_setpoint(
    line: str,
    row_index: int,
    current: float,
    action_code: int,
    selected_step: float,
) -> float:
    """Apply a verified direct/deviated arrow action to one UI setpoint.

    ``selected_step`` is the magnitude selected by the legacy Select node.
    Each action/group permits exactly two magnitudes. The X1/X10 Boolean-to-
    magnitude mapping is not yet verified and deliberately is not guessed.
    Actions 0, 1, and 16 are outside this adjustment function.
    """

    group = beam_group(line, row_index)
    if type(action_code) is not int:
        raise ValueError(f"unsupported beam adjustment action: {action_code!r}")
    if action_code not in _BEAM_ACTIONS:
        raise ValueError(f"unsupported beam adjustment action: {action_code!r}")
    minimum, maximum, coarse, fine = _BEAM_RULES[group]
    choices = coarse if action_code in _BEAM_COARSE_ACTIONS else fine
    magnitude = _finite_number(selected_step, "selected_step")
    if magnitude not in choices:
        raise ValueError(
            f"step {magnitude!r} is not in {choices!r} for {line}/{row_index}/{action_code}"
        )
    return _clamped_adjustment(
        current, _BEAM_ACTIONS[action_code] * magnitude, minimum, maximum
    )


def _adjust_page(
    current: float,
    action_code: int,
    steps: Dict[int, float],
    minimum: float,
    maximum: float,
) -> float:
    if type(action_code) is not int:
        raise ValueError(f"unsupported page adjustment action: {action_code!r}")
    try:
        delta = steps[action_code]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported page adjustment action: {action_code!r}") from exc
    return _clamped_adjustment(current, delta, minimum, maximum)


def adjust_ht_setpoint(current: float, action_code: int) -> float:
    """Page HT -> C9NI6703.OUT00, with the native [6, 20] clamp."""

    return _adjust_page(current, action_code, _HT_STEPS, 6.0, 20.0)


def adjust_preamp_setpoint(current: float, action_code: int) -> float:
    """Page HT preamp -> C8NI6703.OUT06, with the native [200, 400] clamp."""

    return _adjust_page(current, action_code, _PREAMP_STEPS, 200.0, 400.0)


def adjust_hf_attenuation(current: float, action_code: int) -> float:
    """Page HF -> C8NI6703.OUT04; both + actions add 1 in LabVIEW."""

    return _adjust_page(current, action_code, _HF_ATTENUATION_STEPS, 0.0, 20.0)


def adjust_hf_phase(current: float, action_code: int) -> float:
    """Page HF -> C8NI6703.OUT03, with the native [-180, 180] clamp."""

    return _adjust_page(current, action_code, _HF_PHASE_STEPS, -180.0, 180.0)


def adjust_fluides_temperature_setpoint(
    current: float, action_code: int
) -> Tuple[int, float]:
    """Return one proven Page Fluides C8 field and requested setpoint.

    `current` must be the matching Page Fluides Canon or Section setpoint.
    No PSP write or card operation occurs. Multi-button masks and case 0 are
    excluded because their effective behavior is not established here.
    """

    if type(action_code) is not int or action_code not in _FLUIDES_TEMPERATURE_STEPS:
        raise ValueError(f"unsupported Fluides temperature action: {action_code!r}")
    bank_index, delta = _FLUIDES_TEMPERATURE_STEPS[action_code]
    return bank_index, _finite_number(current, "current") + delta
