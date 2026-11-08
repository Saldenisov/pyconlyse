"""G71 portable exact current-source literals; copy-only stdlib3.4.
No external evidence-path or runtime/provider dependency.
"""
import copy
if __package__:
    from .tenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
    )
else:
    from tenth_next_event_fixtures_acq_payload_data import (
        ACQ_PAYLOAD,
        INFLIGHT_ACQ_PAYLOAD,
        SUP_PAYLOAD,
    )

def acq_payload():return copy.deepcopy(ACQ_PAYLOAD)

FALSE_ACQ_PAYLOAD={'event_uid': '43',
 'frame_uid': '23113',
 'leaf_returns': None,
 'new_value': False,
 'reference_bindings': None,
 'schedule': None,
 'snapshots': None,
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': None}

def false_acq_payload():return copy.deepcopy(FALSE_ACQ_PAYLOAD)


def inflight_acq_payload():return copy.deepcopy(INFLIGHT_ACQ_PAYLOAD)


def sup_payload():return copy.deepcopy(SUP_PAYLOAD)

if __package__:
    from .tenth_next_event_fixtures_minimal_sup_payload_data import (
        MINIMAL_SUP_PAYLOAD,
        SPARSE_SUP_PAYLOAD,
    )
else:
    from tenth_next_event_fixtures_minimal_sup_payload_data import (
        MINIMAL_SUP_PAYLOAD,
        SPARSE_SUP_PAYLOAD,
    )

def minimal_sup_payload():return copy.deepcopy(MINIMAL_SUP_PAYLOAD)


def sparse_sup_payload():return copy.deepcopy(SPARSE_SUP_PAYLOAD)


def sup_mask_payload(mask=1024,index=3,x10=False):
    """Source comparison discriminator; Variant and read epochs supplied apart."""
    p=sup_payload()
    for i in range(11):p['new_value'][i]=list(p['old_value'][i])
    for j in range(11):
        if mask&(1<<j):p['new_value'][index][j]=not p['old_value'][index][j] if j not in(5,6)else p['old_value'][index][j]+1.0
    variant=p['native_boundaries']['65015']['outputs']['65045']
    variant[4]=x10
    variant[5]=60.0 if index==1 else 180.0 if index==2 else 0.0
    p['max_index_7844']=index if mask==0 else None
    p['completed_sinks']=[]
    return p

def oversized_sup_payload():
    """Opaque supplied carriers; validity must be checked on frozen pure core.
    Byte size does not qualify native references or RPC acceptance.
    """
    p=sup_payload()
    p['native_boundaries']['7957']['outputs']['7971'][3]='R'*12000
    for uid,face in(('7985','7990'),('7957','7968'),('65015','65023')):
        p['native_boundaries'][uid]['outputs'][face]['source_hex']='AB'*4096
    return p
