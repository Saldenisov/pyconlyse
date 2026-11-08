"""Six exact frozen G78 literal examples; no external evidence reads."""
import copy

if __package__:
    from .seventeenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
    )
else:
    from seventeenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
    )

FALSE_ACQ_PAYLOAD = {'event_uid': '43',
 'field_index_bindings': None,
 'frame_uid': '42457',
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
    from .seventeenth_next_event_fixtures_inflight_acq_payload_data import (
        INFLIGHT_ACQ_PAYLOAD,
    )
else:
    from seventeenth_next_event_fixtures_inflight_acq_payload_data import (
        INFLIGHT_ACQ_PAYLOAD,
    )

SUP_PAYLOAD = {'completed_sinks': ['40558', '32048'],
 'event_outputs': {'unused_old_value': 'independent'},
 'event_time_40518': 4294967295,
 'event_uid': '5909',
 'frame_uid': '47072',
 'intrinsic_inputs': {'19594': True},
 'literal_inputs': {'35281': {'bytes_hex': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465204D2F41206F75206379636C6167652064657320616C696D656E746174696F6E733A20'}},
 'local_reads': {'47137': [False,
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
 'native_boundaries': {'28270': {'outputs': {'unused_U32_timer_observation': None}},
                       '32048': {'outputs': {'32655': {'unused_ref': None},
                                             '32661': {'code': -11,
                                                       'source_hex': '00FF',
                                                       'status': True}}}},
 'new_value': [[0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5],
               1,
               True,
               False,
               True,
               False,
               2,
               3,
               4,
               True,
               {'bytes_hex': '00FF'},
               5,
               True,
               False],
 'reference_bindings': {'31390': {'native_reference': {'opaque_ref': 'DPS'},
                                  'stored_URI_bytes': {'bytes_hex': '6E692E7661722E7073703A2F2F6C6F63616C686F73742F5355504552564953494F4E2F445053'}}},
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
 'unwired_inputs': {'32658': {'code': 7, 'source_hex': 'FF00', 'status': False}}}

MINIMAL_SUP_PAYLOAD = {'completed_sinks': [],
 'event_outputs': None,
 'event_time_40518': None,
 'event_uid': '5909',
 'frame_uid': '47072',
 'intrinsic_inputs': None,
 'literal_inputs': {'42462': 0},
 'local_reads': {'47137': [True,
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
 'native_boundaries': {'28270': {'outputs': {'unused_U32_timer_observation': 0}}},
 'new_value': None,
 'reference_bindings': None,
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
 'unwired_inputs': None}

SPARSE_SUP_PAYLOAD = {'completed_sinks': ['28270'],
 'event_outputs': {'unused_old_value': 'independent'},
 'event_time_40518': 17,
 'event_uid': '5909',
 'frame_uid': '47072',
 'intrinsic_inputs': {'19594': False},
 'literal_inputs': {},
 'local_reads': {'47137': [False,
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
 'native_boundaries': {'28270': {'outputs': {'unused_U32_timer_observation': None}},
                       '32048': {'outputs': {'32655': {'unused_ref': None},
                                             '32661': {'code': -11,
                                                       'source_hex': '00FF',
                                                       'status': True}}}},
 'new_value': [[0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5],
               1,
               True,
               True,
               False,
               False,
               2,
               3,
               4,
               True,
               {'bytes_hex': '00FF'},
               5,
               False,
               False],
 'reference_bindings': {'31390': {'native_reference': {'opaque_ref': 'DPS'},
                                  'stored_URI_bytes': {'bytes_hex': '6E692E7661722E7073703A2F2F6C6F63616C686F73742F5355504552564953494F4E2F445053'}}},
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
 'unwired_inputs': {'32658': {'code': 7, 'source_hex': 'FF00', 'status': False}}}

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
    """Independent source-slot recipe; no runtime/module constant lookup."""
    expected = {}
    for uid, read, updates in (
        ('42565', '42602', {i: 0.0 for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)}),
        ('51300', '51349', {i: 0.0 for i in (0, 1, 3, 4, 5, 6, 7, 8, 9)}),
        ('1953', '30243', {i: False for i in (9, 11, 15, 17, 21, 23, 25, 27, 29, 31, 32, 33, 34, 35, 36, 37, 38, 39)}),
        ('42967', '42997', {65: False, 58: False, 64: False, 67: True, 61: False}),
        ('43003', '43022', {23: False})):
        carrier = list(p['snapshots'][read])
        for index, value in updates.items(): carrier[index] = value
        expected[uid] = carrier
    expected['42608'] = True
    return expected

def oversized_sup_payload():
    """Allowed opaque observations; response cap remains replay transport policy."""
    p = sup_payload()
    p['reference_bindings']['31390']['native_reference'] = {'opaque': 'R' * 7000}
    p['native_boundaries']['32048']['outputs']['32655'] = {'opaque': 'U' * 7000}
    p['native_boundaries']['32048']['outputs']['32661']['source_hex'] = 'AB' * 4096
    p['unwired_inputs']['32658']['source_hex'] = 'CD' * 4096
    p['native_boundaries']['28270']['outputs'] = {'unused': ['Q' * 8192] * 3}
    return p
