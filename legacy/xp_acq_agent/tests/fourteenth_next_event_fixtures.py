"""Exact frozen current six literal examples; no external evidence reads."""
import copy

if __package__:
    from .fourteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
    )
else:
    from fourteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
    )

FALSE_ACQ_PAYLOAD = {'event_uid': '43',
 'frame_uid': '23143',
 'leaf_returns': None,
 'literal_inputs': None,
 'new_value': False,
 'reference_bindings': None,
 'schedule': None,
 'snapshots': None,
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': None}


MINIMAL_SUP_PAYLOAD = {'event_uid': '5909',
 'frame_uid': '23770',
 'literal_inputs': {},
 'local_reads': {},
 'native_boundaries': {},
 'new_value': False,
 'reference_bindings': {},
 'source_id': 'APP-17',
 'source_version': 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9',
 'unqualified_boundaries': {'native_String_encoding_qualified': False,
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

if __package__:
    from .fourteenth_next_event_fixtures_sparse_sup_payload_data import (
        SPARSE_SUP_PAYLOAD,
    )
else:
    from fourteenth_next_event_fixtures_sparse_sup_payload_data import (
        SPARSE_SUP_PAYLOAD,
    )

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

def oversized_sup_payload():
    """Allowed hypothetical inert carriers; response cap is replay policy."""
    p = sup_payload()
    for uid in ('78252', '78481'):
        p['reference_bindings'][uid]['native_reference'] = {'opaque': 'R' * 8192}
    for uid, face in (('78302', '78392'), ('78531', '78542')):
        p['native_boundaries'][uid]['outputs'][face]['source_hex'] = 'AB' * 4096
    for face in ('78389', '78539'):
        p['unwired_inputs'][face]['source_hex'] = 'CD' * 4096
    return p
