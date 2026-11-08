"""Pure local-status projections from saved Acquisition VI frame wires.

No shared variable is published and no hardware adapter is accessed here.
These assignments represent software flags, not measured readback.
"""

from __future__ import annotations

from typing import Sequence, Tuple


COOLING_START_EPS_FIELDS = (
    (0, False),   # Marche refroidissement
    (1, False),   # Marche refroidissement ED
    (2, True),    # Marche refroidissement OK
    (5, False),   # Arret refroidissement OK
    (8, True),    # Marche GENERAL Mod. OK
)
COOLING_START_DPS_FIELDS = ((0, False),)  # Marche refroidissement X
COOLING_STOP_EPS_FIELDS = (
    (1, False),   # Marche refroidissement ED
    (2, False),   # Marche refroidissement OK
    (3, False),   # Arret refroidissement
    (5, True),    # Arret refroidissement OK
)
COOLING_STOP_DPS_FIELDS = ((1, False),)  # Arret refroidissement X
# Literal Wait (ms) nodes in ACQ event 4's ordered frames. A wait and a
# local output assignment within one frame can execute concurrently.
COOLING_STOP_FRAME_WAITS = (
    (0, 0.150), (2, 0.400), (3, 0.150), (4, 0.150), (6, 0.100)
)
COOLING_FLOW_TRIP_EPS_FIELDS = (
    (1, True),    # Marche refroidissement ED
    (2, False),   # Marche refroidissement OK
    (3, False),   # Arret refroidissement
    (5, True),    # Arret refroidissement OK
)
COOLING_FLOW_TRIP_DPS_FIELDS = ((1, False),)  # Arret refroidissement X
GENERAL_MODULATOR_STOP_EPS_FIELDS = (
    (8, False), (14, False), (20, False), (26, False), (32, False),
    (11, True), (17, True), (23, True), (29, True), (35, True),
    (9, False),
)
GENERAL_MODULATOR_STOP_DPS_FIELDS = ((3, False),)
IMPULSION_START_EPS_FIELDS = ((55, False), (52, True))
IMPULSION_START_DPS_FIELDS = ((18, False),)
# The saved stop frame writes EPS[42] (Arrêt Att Déph OK), not EPS[55]
# (Arrêt impulsion mod OK). Preserve that surprising source behavior.
IMPULSION_STOP_EPS_FIELDS = ((42, True), (52, False))
IMPULSION_STOP_DPS_FIELDS = ((19, False),)
MAGNET_COMPLETION_FIELDS = {
    16: (((56, False), (58, True), (64, False), (67, False)), ((20, False),)),
    17: (((65, False), (58, False), (64, False), (67, True), (61, False)),
         ((23, False),)),
    25: (((59, False), (64, False), (61, True)), ((21, False),)),
}
HF_POWER_COMPLETION_FIELDS = {
    18: (((42, False), (39, True)), ((13, False),)),
    19: (((42, True), (39, False)), ((14, False),)),
}


def project_timeout_remote_eps_ingest(
    remote_eps: Sequence[bool],
) -> Tuple[bool, ...]:
    """Project ACQ Timeout frame 0's whole-cluster EPS PSP read.

    Apply only to an explicitly supplied Boolean snapshot. This pure step
    does not perform PSP I/O or resolve read errors, freshness, or ordering
    relative to the sibling EPS publisher. Strict shape checking is a Python
    model boundary, not a claim about LabVIEW's runtime error semantics.
    """

    if len(remote_eps) != 77 or any(type(bit) is not bool for bit in remote_eps):
        raise ValueError("remote EPS must contain exactly 77 Boolean fields")
    return tuple(remote_eps)


def project_cooling_start_local_completion(
    eps: Sequence[bool], dps: Sequence[bool]
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project ACQ event 3 sequence frame 10's local EPS/DPS assignments.

    This says what the saved VI writes after its ordered start sequence,
    irrespective of physical flow, actual card response, or PSP delivery.
    The function does not execute that sequence or publish these banks.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    next_eps, next_dps = list(eps), list(dps)
    for index, value in COOLING_START_EPS_FIELDS:
        next_eps[index] = value
    for index, value in COOLING_START_DPS_FIELDS:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_cooling_stop_local_completion(
    eps: Sequence[bool], dps: Sequence[bool]
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project ACQ event 4 sequence frame 5's local EPS/DPS assignments.

    Fields not addressed by that frame, including EPS[8] (GENERAL Mod. OK),
    are deliberately preserved. This does not imply they remain unchanged
    elsewhere or represent hardware readback.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    next_eps, next_dps = list(eps), list(dps)
    for index, value in COOLING_STOP_EPS_FIELDS:
        next_eps[index] = value
    for index, value in COOLING_STOP_DPS_FIELDS:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_cooling_flow_trip_local_completion(
    eps: Sequence[bool], dps: Sequence[bool]
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project ACQ Timeout cooling-flow True arm's local status frame.

    The caller is responsible for evaluating the separate raw-input guard.
    This function neither executes stop-line commands nor publishes status.
    EPS[8] is preserved because this frame has no assignment to it.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    next_eps, next_dps = list(eps), list(dps)
    for index, value in COOLING_FLOW_TRIP_EPS_FIELDS:
        next_eps[index] = value
    for index, value in COOLING_FLOW_TRIP_DPS_FIELDS:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_general_modulator_stop_local_completion(
    eps: Sequence[bool], dps: Sequence[bool]
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project ACQ event 6 frame 15's local stage-status assignments.

    This does not execute its preceding hardware-command frames or publish
    status. It only copies the 11 literal EPS and one DPS assignments.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    next_eps, next_dps = list(eps), list(dps)
    for index, value in GENERAL_MODULATOR_STOP_EPS_FIELDS:
        next_eps[index] = value
    for index, value in GENERAL_MODULATOR_STOP_DPS_FIELDS:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_impulsion_modulator_local_completion(
    eps: Sequence[bool], dps: Sequence[bool], *, start: bool
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project saved ACQ event 23/24 local status assignments only.

    The start event writes EPS[55]=False and EPS[52]=True. The stop event
    writes EPS[42]=True and EPS[52]=False, leaving EPS[55] untouched in
    that event. This is source behavior, not confirmation of a pulse or
    a corrected semantic status. No NI task or PSP call is performed.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    if type(start) is not bool:
        raise ValueError("start must be Boolean")
    next_eps, next_dps = list(eps), list(dps)
    eps_fields = IMPULSION_START_EPS_FIELDS if start else IMPULSION_STOP_EPS_FIELDS
    dps_fields = IMPULSION_START_DPS_FIELDS if start else IMPULSION_STOP_DPS_FIELDS
    for index, value in eps_fields:
        next_eps[index] = value
    for index, value in dps_fields:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_magnet_local_completion(
    eps: Sequence[bool], dps: Sequence[bool], *, event_case: int
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project literal local status writes of ACQ magnet events 16/17/25.

    Start, stop, and zero-setpoint events assign software status flags and
    reset their own request bit. Fields not named by a given event remain
    unchanged. This does not execute analog/digital commands, publish PSP,
    or confirm magnet current or power-supply response.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    if type(event_case) is not int or event_case not in MAGNET_COMPLETION_FIELDS:
        raise ValueError("magnet event_case must be 16, 17, or 25")
    next_eps, next_dps = list(eps), list(dps)
    eps_fields, dps_fields = MAGNET_COMPLETION_FIELDS[event_case]
    for index, value in eps_fields:
        next_eps[index] = value
    for index, value in dps_fields:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)


def project_hf_power_local_completion(
    eps: Sequence[bool], dps: Sequence[bool], *, event_case: int
) -> Tuple[Tuple[bool, ...], Tuple[bool, ...]]:
    """Project ACQ event 18/19's local Att/Déph status assignments only.

    Event 24's unrelated pulse-stop completion also assigns EPS[42].
    Keeping these projections separate exposes that saved-code overlap;
    neither projection confirms HF chassis state or publishes status.
    """

    if len(eps) != 77 or any(type(bit) is not bool for bit in eps):
        raise ValueError("EPS must contain exactly 77 Boolean fields")
    if len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("DPS must contain exactly 29 Boolean fields")
    if type(event_case) is not int or event_case not in HF_POWER_COMPLETION_FIELDS:
        raise ValueError("HF power event_case must be 18 or 19")
    next_eps, next_dps = list(eps), list(dps)
    eps_fields, dps_fields = HF_POWER_COMPLETION_FIELDS[event_case]
    for index, value in eps_fields:
        next_eps[index] = value
    for index, value in dps_fields:
        next_dps[index] = value
    return tuple(next_eps), tuple(next_dps)
