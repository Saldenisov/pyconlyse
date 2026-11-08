"""Six exact frozen G79 literal examples; no external evidence reads."""
import copy

if __package__:
    from .eighteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
    )
else:
    from eighteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
    )

FALSE_ACQ_PAYLOAD = {'event_uid': '43',
 'field_index_bindings': None,
 'frame_uid': '34531',
 'leaf_returns': None,
 'literal_inputs': None,
 'new_value': False,
 'reference_bindings': None,
 'schedule': None,
 'snapshots': None,
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': None}

if __package__:
    from .eighteenth_next_event_fixtures_inflight_acq_payload_data import (
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
        SPARSE_SUP_PAYLOAD,
    )
else:
    from eighteenth_next_event_fixtures_inflight_acq_payload_data import (
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
        SPARSE_SUP_PAYLOAD,
    )


MINIMAL_SUP_PAYLOAD = {'completed_sinks': ['43942'],
 'event_outputs': None,
 'event_time_30833': 'inactive source border observation',
 'event_uid': '5909',
 'frame_uid': '30817',
 'intrinsic_inputs': {},
 'literal_inputs': {'42193': 17},
 'local_reads': {'30929': [True,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False,
                           False]},
 'native_boundaries': {'43942': {'outputs': 'unused supplied U32 timer observation'}},
 'new_value': 'inactive Page observation',
 'reference_bindings': {},
 'source_id': 'APP-17',
 'source_version': 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9',
 'unqualified_boundaries': {'native_DBL_bitwise_equivalence_qualified': False,
                            'native_ErrorCluster_Case_selection_qualified': False,
                            'native_String_encoding_qualified': False,
                            'native_atomic_snapshot_qualified': False,
                            'native_callee_equivalence_qualified': False,
                            'native_default_policy_qualified': False,
                            'native_delivery_or_scheduling_qualified': False,
                            'native_event_selection_qualified': False,
                            'native_execution_qualified': False,
                            'native_field_index_selection_qualified': False,
                            'native_primitive_coercion_qualified': False,
                            'native_reference_validity_qualified': False,
                            'native_storage_serializer_qualified': False,
                            'native_wait_units_or_timing_qualified': False,
                            'whole_VI_equivalence': False,
                            'whole_event_equivalence': False},
 'unwired_inputs': {}}


def acq_payload():
    return copy.deepcopy(ACQ_PAYLOAD)

def false_acq_payload():
    return copy.deepcopy(FALSE_ACQ_PAYLOAD)

def inflight_acq_payload():
    return copy.deepcopy(INFLIGHT_ACQ_PAYLOAD)

def sup_payload():
    return copy.deepcopy(SUP_PAYLOAD)

def minimal_sup_payload():
    return copy.deepcopy(MINIMAL_SUP_PAYLOAD)

def sparse_sup_payload():
    return copy.deepcopy(SPARSE_SUP_PAYLOAD)

def acq_expected_writes(p):
    """Original source-slot recipe; no core constants or earlier event outputs."""
    expected = {}
    for uid, read, updates in (
        ('34688', '34742', {0: True}), ('34906', '34957', {0: False}),
        ('35059', '35075', {2: True}), ('25108', '25217', {2: False}),
        ('31999', '32017', {2: True}), ('33233', '33251', {2: False}),
        ('35479', '35509', {11: False, 8: True, 6: False}), ('35515', '35533', {2: False})):
        carrier = list(p['snapshots'][read])
        for index, value in updates.items(): carrier[index] = value
        expected[uid] = carrier
    expected['34760'] = True
    return expected


def sup_expected_dps(p):
    """Eleven exact saved Boolean incidences in the flat Page59/DPS29 domain."""
    updated = list(p['local_reads']['30929'])
    for source, target in ((22, 2), (23, 3), (46, 4), (47, 5), (48, 6), (49, 7),
                           (50, 8), (51, 9), (52, 10), (53, 11), (21, 12)):
        updated[target] = p['new_value'][source]
    return updated


def acq_refusal_payloads():
    mutants = []
    for face in ('34732', '34942'):
        for value in (None, False, -1, 1, 0.0):
            p = acq_payload(); p['field_index_bindings'][face] = value; mutants.append(p)
        p = acq_payload(); del p['field_index_bindings'][face]; mutants.append(p)
    for uid in ('25728', '32614', '33267', '34877', '35419', '35459'):
        for value in (True, 0, None):
            p = acq_payload(); p['literal_inputs'][uid] = value; mutants.append(p)
        p = acq_payload(); del p['literal_inputs'][uid]; mutants.append(p)
    p = acq_payload(); p['reference_bindings']['35588']['saved_uri'] += '/other'; mutants.append(p)
    p = acq_payload(); p['leaf_returns']['35620']['35631']['status'] = 0; mutants.append(p)
    p = acq_payload(); p['unwired_inputs']['35664'] = 65536; mutants.append(p)
    p = acq_payload(); p['unwired_inputs']['35649'] = -(2**31) - 1; mutants.append(p)
    p = acq_payload(); p['snapshots']['34742'][0] = 1; mutants.append(p)
    return mutants


def sup_refusal_payloads():
    mutants = []
    for value in (-1, 4294967296, True, 0.0, None):
        p = sup_payload(); p['event_time_30833'] = value; mutants.append(p)
        p = minimal_sup_payload(); p['literal_inputs']['42193'] = value; mutants.append(p)
    for value in ([False] * 28, [False] * 30, [0] * 29):
        p = sup_payload(); p['local_reads']['30929'] = value; mutants.append(p)
    for value in (0, None, 'True'):
        p = sup_payload(); p['intrinsic_inputs']['33976'] = value; mutants.append(p)
    for index, value in ((22, 0), (31, 0), (44, True)):
        p = sup_payload(); p['new_value'][index] = value; mutants.append(p)
    p = sup_payload(); p['new_value'] = p['new_value'][:-1]; mutants.append(p)
    p = sup_payload(); p['reference_bindings']['31469']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['literal_inputs']['34420']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['33792']['outputs']['33926']['code'] = 2**31; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['33792']['outputs']['33926']['status'] = 0; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['33792']['outputs']['33926']['source_hex'] = 'AA' * 4097; mutants.append(p)
    p = sup_payload(); del p['unwired_inputs']['33899']; mutants.append(p)
    for report in (['33792', '33792'], ['30946']):
        p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
    return mutants


def oversized_sup_payload():
    """Allowed opaque observations; response cap is replay transport policy."""
    p = sup_payload()
    p['reference_bindings']['31469']['native_reference'] = {'opaque': 'R' * 7000}
    p['native_boundaries']['33792']['outputs']['33864'] = {'opaque': 'U' * 7000}
    p['native_boundaries']['33792']['outputs']['33926']['source_hex'] = 'AB' * 4096
    p['unwired_inputs']['33899']['source_hex'] = 'CD' * 4096
    p['native_boundaries']['43942']['outputs'] = {'unused': ['Q' * 8192] * 3}
    return p
