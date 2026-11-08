"""Six exact frozen G77 literal examples; no external evidence reads."""
import copy

if __package__:
    from .sixteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
    )
else:
    from sixteenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
    )

FALSE_ACQ_PAYLOAD = {'event_uid': '43',
 'frame_uid': '40079',
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
    from .sixteenth_next_event_fixtures_sup_payload_data import (
        SUP_PAYLOAD,
        MINIMAL_SUP_PAYLOAD,
        SPARSE_SUP_PAYLOAD,
    )
else:
    from sixteenth_next_event_fixtures_sup_payload_data import (
        SUP_PAYLOAD,
        MINIMAL_SUP_PAYLOAD,
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
    """Allowed supplied opaque carriers; signed response cap is replay policy."""
    p = sup_payload()
    for uid in ('54139', '86088'):
        p['reference_bindings'][uid]['native_reference'] = {'opaque': 'R' * 8192}
    for uid, face in (('53908', '53930'), ('86028', '86039')):
        p['native_boundaries'][uid]['outputs'][face]['source_hex'] = 'AB' * 4096
    for face in ('53918', '86036'):
        p['unwired_inputs'][face]['source_hex'] = 'CD' * 4096
    return p
