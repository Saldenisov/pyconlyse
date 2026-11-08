"""Pure Supervision request-serialization logic from saved LabVIEW wiring.

This module neither publishes a shared variable nor actuates hardware. A
selected DPS branch only forwards operator intent; it does not establish
cooling, modulator, or high-voltage hardware safety or execution.
"""
from __future__ import annotations
from typing import Optional, Sequence, Tuple
from legacy.xp_acq_agent.elyse_agent import saved_requests as _shared
replay_saved_requests = _shared.replay_saved_requests
HT_ADJUSTMENT_FIELD_INDEXES = (15, 13, 14, 16, 21, 19, 20, 22)
HT_DPS_COMMAND_FIELDS = ((10, 15), (11, 17), (9, 16), (25, 18), (24, 19))
MODULATOR_DPS_COMMAND_FIELDS = ((22, 2), (23, 3), (46, 4), (47, 5), (48, 6), (49, 7), (50, 8), (51, 9), (52, 10), (53, 11), (21, 12))
FLUIDES_TEMPERATURE_BUTTON_FIELDS = (7, 6, 20, 19)
FLUIDES_DPS_COMMAND_FIELDS = ((9, 0), (8, 1))
MAGNET_DPS_COMMAND_FIELDS = (20, 23, 21)
HF_ADJUSTMENT_FIELD_INDEXES = (2, 4, 3, 1, 14, 16, 15, 13)
HF_DPS_COMMAND_FIELDS = ((7, 13), (6, 14))

def page_ht_event_selects_dps_branch(pending_dps: Sequence[bool], ht_adjustment_buttons: Sequence[bool]) -> bool:
    """Whether Page HT event 15 enters its five-command DPS-write branch.

    `pending_dps` is the 29-Boolean local request cluster sampled by the
    event. `ht_adjustment_buttons` are the eight Page HT arrow states in
    `HT_ADJUSTMENT_FIELD_INDEXES` order. This is UI request serialization,
    not a radioprotection, electrical, or Acquisition authorization check.
    """
    return _shared.page_ht_event_selects_dps_branch(pending_dps, ht_adjustment_buttons)

def project_page_ht_dps_write(pending_dps: Sequence[bool], ht_adjustment_buttons: Sequence[bool], ht_command_buttons: Sequence[bool]) -> Optional[Tuple[bool, ...]]:
    """Project the saved Page HT false-branch DPS write without publishing it.

    `ht_command_buttons` follows `HT_DPS_COMMAND_FIELDS` order. None means
    this event takes the other branch and does not perform this DPS write.
    An all-false button vector still yields a write of five False fields.
    """
    return _shared.project_page_ht_dps_write(pending_dps, ht_adjustment_buttons, ht_command_buttons)

def project_page_modulator_dps_write(pending_dps: Sequence[bool], modulator_buttons: Sequence[bool]) -> Optional[Tuple[bool, ...]]:
    """Project event 18's 11 DPS fields without publishing or actuating.

    The saved event writes the DPS cluster only if no local request flag is
    True. This is request serialization, not stage sequencing, readiness,
    radioprotection, or permission to operate hardware.
    """
    return _shared.project_page_modulator_dps_write(pending_dps, modulator_buttons)

def project_page_fluides_dps_write(pending_dps: Sequence[bool], temperature_buttons: Sequence[bool], cooling_buttons: Sequence[bool]) -> Optional[Tuple[bool, ...]]:
    """Project event 14's cooling-request write, without publishing it.

    The temperature buttons follow `FLUIDES_TEMPERATURE_BUTTON_FIELDS` order:
    lower/raise Canon, lower/raise Section. The cooling buttons follow
    `FLUIDES_DPS_COMMAND_FIELDS` order: start/stop regulation. The saved
    event enters this DPS-write branch only when both the pending DPS bank
    and all four temperature buttons are false. A temperature request uses
    another branch; this function makes no claim about that branch or about
    physical water flow, thermal safety, or Acquisition acceptance.
    """
    return _shared.project_page_fluides_dps_write(pending_dps, temperature_buttons, cooling_buttons)

def project_page_alimentations_dps_write(pending_dps: Sequence[bool], magnet_buttons: Sequence[bool]) -> Optional[Tuple[bool, ...]]:
    """Project saved Page Alimentations event 17's three-request DPS write.

    Buttons are Marche Aimants., Arrêt Aimants, Aimant 0V, in that order.
    The branch requires every sampled local DPS bit to be False. It does
    not test power-supply readback, safety permission, or stage readiness.
    Returned tuple is a local projection, never a PSP publication.
    """
    return _shared.project_page_alimentations_dps_write(pending_dps, magnet_buttons)

def project_page_hf_dps_write(pending_dps: Sequence[bool], hf_adjustment_buttons: Sequence[bool], hf_command_buttons: Sequence[bool]) -> Optional[Tuple[bool, ...]]:
    """Project saved Page HF event 16's two DPS request fields only.

    The DPS-write branch requires every sampled local DPS bit and all eight
    HF adjustment arrow fields to be False. It is not a physical permissive,
    and this pure function never publishes a PSP value or touches hardware.
    """
    return _shared.project_page_hf_dps_write(pending_dps, hf_adjustment_buttons, hf_command_buttons)
