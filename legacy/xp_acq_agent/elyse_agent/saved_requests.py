# -*- coding: utf-8 -*-
"""Pure Supervision request-serialization logic from saved LabVIEW wiring.

This module neither publishes a shared variable nor actuates hardware. A
selected DPS branch only forwards operator intent; it does not establish
cooling, modulator, or high-voltage hardware safety or execution.
"""
HT_ADJUSTMENT_FIELD_INDEXES = (15, 13, 14, 16, 21, 19, 20, 22)
HT_DPS_COMMAND_FIELDS = ((10, 15), (11, 17), (9, 16), (25, 18), (24, 19))
MODULATOR_DPS_COMMAND_FIELDS = ((22, 2), (23, 3), (46, 4), (47, 5), (48, 6), (49, 7), (50, 8), (51, 9), (52, 10), (53, 11), (21, 12))
FLUIDES_TEMPERATURE_BUTTON_FIELDS = (7, 6, 20, 19)
FLUIDES_DPS_COMMAND_FIELDS = ((9, 0), (8, 1))
MAGNET_DPS_COMMAND_FIELDS = (20, 23, 21)
HF_ADJUSTMENT_FIELD_INDEXES = (2, 4, 3, 1, 14, 16, 15, 13)
HF_DPS_COMMAND_FIELDS = ((7, 13), (6, 14))

def page_ht_event_selects_dps_branch(pending_dps, ht_adjustment_buttons):
    """Whether Page HT event 15 enters its five-command DPS-write branch.

    `pending_dps` is the 29-Boolean local request cluster sampled by the
    event. `ht_adjustment_buttons` are the eight Page HT arrow states in
    `HT_ADJUSTMENT_FIELD_INDEXES` order. This is UI request serialization,
    not a radioprotection, electrical, or Acquisition authorization check.
    """
    if len(pending_dps) != 29 or any((type(bit) is not bool for bit in pending_dps)):
        raise ValueError('pending DPS must contain exactly 29 Boolean fields')
    if len(ht_adjustment_buttons) != 8 or any((type(bit) is not bool for bit in ht_adjustment_buttons)):
        raise ValueError('HT adjustment buttons must contain exactly 8 Boolean fields')
    return not (any(pending_dps) or any(ht_adjustment_buttons))

def project_page_ht_dps_write(pending_dps, ht_adjustment_buttons, ht_command_buttons):
    """Project the saved Page HT false-branch DPS write without publishing it.

    `ht_command_buttons` follows `HT_DPS_COMMAND_FIELDS` order. None means
    this event takes the other branch and does not perform this DPS write.
    An all-false button vector still yields a write of five False fields.
    """
    selected = page_ht_event_selects_dps_branch(pending_dps, ht_adjustment_buttons)
    if len(ht_command_buttons) != len(HT_DPS_COMMAND_FIELDS) or any((type(bit) is not bool for bit in ht_command_buttons)):
        raise ValueError('HT command buttons must contain exactly 5 Boolean fields')
    if not selected:
        return None
    projected = list(pending_dps)
    for (_, dps_index), pressed in zip(HT_DPS_COMMAND_FIELDS, ht_command_buttons):
        projected[dps_index] = pressed
    return tuple(projected)

def project_page_modulator_dps_write(pending_dps, modulator_buttons):
    """Project event 18's 11 DPS fields without publishing or actuating.

    The saved event writes the DPS cluster only if no local request flag is
    True. This is request serialization, not stage sequencing, readiness,
    radioprotection, or permission to operate hardware.
    """
    if len(pending_dps) != 29 or any((type(bit) is not bool for bit in pending_dps)):
        raise ValueError('pending DPS must contain exactly 29 Boolean fields')
    if len(modulator_buttons) != len(MODULATOR_DPS_COMMAND_FIELDS) or any((type(bit) is not bool for bit in modulator_buttons)):
        raise ValueError('modulator buttons must contain exactly 11 Boolean fields')
    if any(pending_dps):
        return None
    projected = list(pending_dps)
    for (_, dps_index), pressed in zip(MODULATOR_DPS_COMMAND_FIELDS, modulator_buttons):
        projected[dps_index] = pressed
    return tuple(projected)

def project_page_fluides_dps_write(pending_dps, temperature_buttons, cooling_buttons):
    """Project event 14's cooling-request write, without publishing it.

    The temperature buttons follow `FLUIDES_TEMPERATURE_BUTTON_FIELDS` order:
    lower/raise Canon, lower/raise Section. The cooling buttons follow
    `FLUIDES_DPS_COMMAND_FIELDS` order: start/stop regulation. The saved
    event enters this DPS-write branch only when both the pending DPS bank
    and all four temperature buttons are false. A temperature request uses
    another branch; this function makes no claim about that branch or about
    physical water flow, thermal safety, or Acquisition acceptance.
    """
    if len(pending_dps) != 29 or any((type(bit) is not bool for bit in pending_dps)):
        raise ValueError('pending DPS must contain exactly 29 Boolean fields')
    if len(temperature_buttons) != 4 or any((type(bit) is not bool for bit in temperature_buttons)):
        raise ValueError('Fluides temperature buttons must contain exactly 4 Boolean fields')
    if len(cooling_buttons) != 2 or any((type(bit) is not bool for bit in cooling_buttons)):
        raise ValueError('Fluides cooling buttons must contain exactly 2 Boolean fields')
    if any(pending_dps) or any(temperature_buttons):
        return None
    projected = list(pending_dps)
    for (_, dps_index), pressed in zip(FLUIDES_DPS_COMMAND_FIELDS, cooling_buttons):
        projected[dps_index] = pressed
    return tuple(projected)

def project_page_alimentations_dps_write(pending_dps, magnet_buttons):
    """Project saved Page Alimentations event 17's three-request DPS write.

    Buttons are Marche Aimants., Arrêt Aimants, Aimant 0V, in that order.
    The branch requires every sampled local DPS bit to be False. It does
    not test power-supply readback, safety permission, or stage readiness.
    Returned tuple is a local projection, never a PSP publication.
    """
    if len(pending_dps) != 29 or any((type(bit) is not bool for bit in pending_dps)):
        raise ValueError('pending DPS must contain exactly 29 Boolean fields')
    if len(magnet_buttons) != 3 or any((type(bit) is not bool for bit in magnet_buttons)):
        raise ValueError('magnet buttons must contain exactly 3 Boolean fields')
    if any(pending_dps):
        return None
    projected = list(pending_dps)
    for dps_index, pressed in zip(MAGNET_DPS_COMMAND_FIELDS, magnet_buttons):
        projected[dps_index] = pressed
    return tuple(projected)

def project_page_hf_dps_write(pending_dps, hf_adjustment_buttons, hf_command_buttons):
    """Project saved Page HF event 16's two DPS request fields only.

    The DPS-write branch requires every sampled local DPS bit and all eight
    HF adjustment arrow fields to be False. It is not a physical permissive,
    and this pure function never publishes a PSP value or touches hardware.
    """
    if len(pending_dps) != 29 or any((type(bit) is not bool for bit in pending_dps)):
        raise ValueError('pending DPS must contain exactly 29 Boolean fields')
    if len(hf_adjustment_buttons) != 8 or any((type(bit) is not bool for bit in hf_adjustment_buttons)):
        raise ValueError('HF adjustment buttons must contain exactly 8 Boolean fields')
    if len(hf_command_buttons) != 2 or any((type(bit) is not bool for bit in hf_command_buttons)):
        raise ValueError('HF command buttons must contain exactly 2 Boolean fields')
    if any(pending_dps) or any(hf_adjustment_buttons):
        return None
    projected = list(pending_dps)
    for (_, dps_index), pressed in zip(HF_DPS_COMMAND_FIELDS, hf_command_buttons):
        projected[dps_index] = pressed
    return tuple(projected)


# Fixed source correspondence; values are extracted Boolean terminal inputs,
# never a decoded Page cluster. Gate and bundle-base snapshots are separate.
PAGE_SPECS = {
    'ht': ('38707', 8, (15, 17, 16, 18, 19)),
    'modulator': ('30817', 0, (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)),
    'fluides': ('38030', 4, (0, 1)),
    'magnets': ('47072', 0, (20, 23, 21)),
    'hf': ('53716', 8, (13, 14)),
}


def boolean_vector(value, count, label):
    if type(value) not in (list, tuple) or len(value) != count or any(type(b) is not bool for b in value):
        raise ValueError(label + ' requires exact Boolean vector length ' + str(count))


def route_page_request(page, gate_dps, adjustments, commands, base_dps):
    """Project one DPS writer facet; do not read base when that facet is skipped.

    Other busy/adjustment branches are outside this projection. A skipped DPS
    writer does not imply an empty whole event or prohibit a parameter write.
    """
    if type(page) is not str or page not in PAGE_SPECS:
        raise ValueError('known saved request page required')
    unused_uid, arrow_count, targets = PAGE_SPECS[page]
    boolean_vector(gate_dps, 29, 'gate_dps')
    boolean_vector(adjustments, arrow_count, 'adjustments')
    boolean_vector(commands, len(targets), 'commands')
    if any(gate_dps) or any(adjustments):
        return None
    boolean_vector(base_dps, 29, 'base_dps')
    result = list(base_dps)
    for index, value in zip(targets, commands):
        result[index] = value
    return tuple(result)


def procedure_entry_values(event_index, new_value):
    """Only the saved Boolean NewVal entry; duration is raw U32 argument."""
    if type(event_index) is not int or not 3 <= event_index <= 25:
        raise ValueError('explicit procedure event3..25 required')
    if type(new_value) is not bool:
        raise TypeError('explicit Boolean event NewVal required')
    return (event_index, new_value, (1000 if event_index == 3 else 150) if new_value else None,
            -2147483647 if event_index == 25 else 1)


def exact_fields(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('exact saved request fields required')


def replay_saved_requests(payload):
    if type(payload) is not dict:
        raise ValueError('exact saved request payload required')
    facet = payload.get('facet')
    if facet == 'supervision_dps':
        exact_fields(payload, ('facet', 'source_id', 'uid', 'page', 'gate_dps', 'base_dps', 'adjustments', 'commands'))
        page = payload['page']
        if type(page) is not str or page not in PAGE_SPECS or payload['source_id'] != 'APP-17' or payload['uid'] != PAGE_SPECS[page][0]:
            raise ValueError('matching APP-17 saved request page/UID required')
        result = route_page_request(page, payload['gate_dps'], payload['adjustments'], payload['commands'], payload['base_dps'])
        if result is None and payload['base_dps'] is not None:
            raise ValueError('unselected bundle-base must be absent in replay payload')
        outputs = dict(dps_writer_selected=result is not None,
                       projected_dps=list(result) if result is not None else None,
                       bundle_base_read_selected=result is not None, other_branches_replayed=False)
    elif facet == 'acquisition_entry':
        exact_fields(payload, ('facet', 'source_id', 'uid', 'event_index', 'new_value'))
        if payload['source_id'] != 'APP-00' or payload['uid'] != '43':
            raise ValueError('APP-00 event structure43 required')
        values = procedure_entry_values(payload['event_index'], payload['new_value'])
        outputs = dict(event_index=values[0], enters_sequence=values[1], duration_argument=values[2], registration_flags=values[3])
    else:
        raise ValueError('known saved request facet required')
    return dict(source_id=payload['source_id'], uid=payload['uid'], scope='SUPPLIED_SNAPSHOT_REQUEST_FACET', facet=facet,
                outputs=outputs, hardware_writes=False, execution_allowed=False, external_calls_executed=False,
                atomic_snapshots_qualified=False, psp_delivery_qualified=False,
                native_cluster_decode_qualified=False, whole_event_equivalence=False)
