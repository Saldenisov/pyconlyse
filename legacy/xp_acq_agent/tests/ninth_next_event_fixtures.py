"""Portable G70 exact payloads; supplied boundaries are hypothetical. No evidence file reads."""
import copy

if __package__:
    from .ninth_next_event_fixtures_acq_full_data import (
        _ACQ_FULL,
        _ACQ_INFLIGHT,
    )
else:
    from ninth_next_event_fixtures_acq_full_data import (
        _ACQ_FULL,
        _ACQ_INFLIGHT,
    )

_ACQ_FALSE={'event_uid': '43',
 'frame_uid': '8896',
 'leaf_returns': None,
 'new_value': False,
 'reference_bindings': None,
 'schedule': None,
 'snapshots': None,
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': None}


if __package__:
    from .ninth_next_event_fixtures_sup_full_data import (
        _SUP_FULL,
        _SUP_MINIMUM,
        _SUP_SPARSE,
        _SUP_ARM_ROWS,
    )
else:
    from ninth_next_event_fixtures_sup_full_data import (
        _SUP_FULL,
        _SUP_MINIMUM,
        _SUP_SPARSE,
        _SUP_ARM_ROWS,
    )


_SUP_WRITER_PORTS={'38989': {'0': '38991', '1': '38994', '2': '38997', '3': '39000', '4': '39003'},
 '39649': {'0': '39655', '1': '39679', '2': '39685', '3': '39698', '4': '39707'},
 '49259': {'0': '49261', '1': '49264', '2': '49267', '3': '49271', '4': '49274'},
 '60592': {'0': '60594', '1': '60601', '2': '60610', '3': '60614', '4': '60617'},
 '69180': {'0': '69182', '1': '69185', '2': '69188', '3': '69191', '4': '69194'},
 '70809': {'0': '70811', '1': '70814', '2': '70817', '3': '70820', '4': '70823'},
 '72012': {'0': '72014', '1': '72017', '2': '72020', '3': '72023', '4': '72026'},
 '73519': {'0': '73521', '1': '73524', '2': '73527', '3': '73530', '4': '73533'},
 '75435': {'0': '75437', '1': '75440', '2': '75443', '3': '75446', '4': '75449'}}

_SUP_PROPERTY_PORTS={'67505': {'0': '67512', '1': '67515', '2': '67518', '3': '67521', '4': '67527'},
 '67577': {'0': '67580', '1': '67583', '2': '67586', '3': '67589', '4': '67593'},
 '67619': {'0': '67628', '1': '67634', '2': '67637', '3': '67644', '4': '67647'},
 '67657': {'0': '67660', '1': '67663', '2': '67667', '3': '67670', '4': '67679'},
 '67698': {'0': '67701', '1': '67704', '2': '67707', '3': '67710', '4': '67714'},
 '68962': {'0': '68969', '1': '68972', '2': '68979', '3': '68984', '4': '68990'},
 '7002': {'0': '7009', '1': '7012', '2': '7015', '3': '7018', '4': '7021'},
 '70250': {'0': '70266', '1': '70274', '2': '70284', '3': '70289', '4': '70299'}}

_SUP_READ_UIDS=('38750', '39775', '70856', '60664', '75471', '49338', '69227', '72059', '73555')

_SUP_WRITER_UIDS=('38989', '39649', '70809', '60592', '75435', '49259', '69180', '72012', '73519')

_SUP_PROPERTY_UIDS=('67577', '67619', '67657', '67698', '7002', '70250', '67505', '68962')

_SUP_WAIT_UIDS=('41480', '70927', '60722', '75522', '78590', '69278', '72110', '73612')

_SUP_UNWIRED_UIDS=('38997',
 '39685',
 '70817',
 '60610',
 '75443',
 '49267',
 '69188',
 '72020',
 '73527',
 '67580',
 '67586',
 '67628',
 '67637',
 '67660',
 '67667',
 '67701',
 '67707',
 '7009',
 '7015',
 '70266',
 '70284',
 '67512',
 '67518',
 '68969',
 '68979')

_SUP_LITERAL_UIDS=('38907',
 '39257',
 '39271',
 '84932',
 '41470',
 '70911',
 '60712',
 '75512',
 '78580',
 '69268',
 '72100',
 '73601',
 '39565',
 '71016',
 '60820',
 '75618',
 '49392',
 '69362',
 '72198',
 '73706')

_SUP_PAGE_DBL_FIELDS=(1, 2, 3, 12, 17, 18, 23)

_SUP_REQUEST_POSITIONS=(15, 13, 14, 16, 21, 19, 20, 22)

_SUP_SOURCE_ID='APP-17'

_SUP_SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'

_SUP_EVENT_UID='5909'

_SUP_FRAME_UID='38707'

def acq_payload(new_value=True):
    p=copy.deepcopy(_ACQ_FULL);p['new_value']=new_value;return p

def false_acq_payload():return copy.deepcopy(_ACQ_FALSE)
def inflight_acq_payload():return copy.deepcopy(_ACQ_INFLIGHT)
def sup_payload():return copy.deepcopy(_SUP_FULL)
def minimum_sup_payload():return copy.deepcopy(_SUP_MINIMUM)
def sparse_sup_payload():return copy.deepcopy(_SUP_SPARSE)

def request_sup_payload(mask=1,busy=False,error_selector=True,stop=False,start=False,reset=False):
    page=[False]*28
    for i in _SUP_PAGE_DBL_FIELDS:page[i]=float(i)+0.25
    page[12]=10.0;page[18]=300.0;page[24]=stop;page[25]=start
    for i,pos in enumerate(_SUP_REQUEST_POSITIONS):page[pos]=bool(mask&(1<<i))
    dps=[False]*29;dps[0]=busy
    reads=dict((uid,None)for uid in _SUP_READ_UIDS);reads['38750']=dps
    native=dict((uid,None)for uid in _SUP_WRITER_UIDS+_SUP_PROPERTY_UIDS+_SUP_WAIT_UIDS)
    unwired=dict((uid,None)for uid in _SUP_UNWIRED_UIDS)
    literals=dict((uid,None)for uid in _SUP_LITERAL_UIDS)
    error=dict(status=True,code=-7,source_hex='00FF4641554C54')
    clean=dict(status=False,code=91,source_hex='FF00')
    active='38989'if not(busy or mask)else _SUP_ARM_ROWS[mask]['writer_uid']if mask in _SUP_ARM_ROWS else None
    if active:
        p=_SUP_WRITER_PORTS[active];native[active]={p['1']:dict(supplied_reference_out=active),p['3']:dict(error)};unwired[p['2']]=dict(clean)
    if mask in _SUP_ARM_ROWS:
        a=_SUP_ARM_ROWS[mask];reads[a['carrier_read_uid']]=[100.0+i for i in range(10)];native[a['wait_uid']]={a['wait_output_face']:dict(supplied_timer=17)}
        literals[a['reference_literal_uid']]=dict(supplied_reference=a['reference_literal_uid']);literals[a['reset_literal_uid']]=reset
    if not(busy or mask):
        literals['38907']=dict(supplied_reference='38907')
        props=[]
        if stop:props.extend(('67577','67619','67657','67698'))
        if start:props.extend(('7002','70250','67505','68962'));literals['84932']=23
        for u in props:
            p=_SUP_PROPERTY_PORTS[u];native[u]={p['1']:dict(unused_reference=u),p['3']:dict(unused_error=u)};unwired[p['0']]=dict(supplied_property_reference=u);unwired[p['2']]=dict(clean)
    if busy and not mask:literals['39257']='00FF';literals['39271']=dict(error)
    completed=[active]if active else None
    if mask in _SUP_ARM_ROWS:completed.append(_SUP_ARM_ROWS[mask]['carrier_write_uid'])
    return dict(source_id=_SUP_SOURCE_ID,source_version=_SUP_SOURCE_VERSION,event_uid=_SUP_EVENT_UID,frame_uid=_SUP_FRAME_UID,
        event_returns={'38726':{'38728':dict(unused_aggregate=True),'38731':dict(unused_event_type=True),'38734':dict(unused_time=True),'38737':dict(unused_reference=True),'38740':dict(unwired_OldVal=True),'38743':page}},
        local_reads=reads,native_returns=native,unwired_inputs=unwired,border_inputs={'38717':None,'38720':None,'38723':None,'38714':17},literal_inputs=literals,intrinsic_outputs={'41026':error_selector},completed_sinks=completed)


def oversized_sup_payload():
    """Only explicit native supplied outputs enlarged; original literals unchanged."""
    p=sup_payload()
    p['native_returns']['39649']['39679']=['R'*700 for unused in range(64)]
    p['native_returns']['39649']['39698']['source_hex']='FF00'*2048
    return p
