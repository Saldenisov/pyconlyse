"""Saved Supervision reader caller slices; supplied returns,Python3.4,no PSP."""
from collections import namedtuple
from .saved_xnode import ErrorValue

CHAIN=('35960','36097','36228','36360','12682','12956','19970','27617','12699','13185','13825','17409','8475')
INDEPENDENT='51964'
LOCALS=(('DPC','134463'),('DPS','135295'),('VDD','68070'),('VAD','97714'),
        ('C3_OUT_DIO96','64981'),('C4_OUT_DIO96','65901'),('C5_OUT_DIO96','66821'),
        ('C10-11 NI6602','30288'),('C6NI6703','67290'),('C7NI6703','67171'),
        ('C8NI6703','67056'),('C9NI6703','66941'),('VTA','46530'))
UNWIRED=namedtuple('UnwiredValue','connection')('unwired')
ReaderReturn=namedtuple('ReaderReturn','data error')
ReaderCall=namedtuple('ReaderCall','node_uid reference_in error_in default_data returned')
ReadSlice=namedtuple('ReadSlice','calls local_assignments final_error')


def require_error(error):
    if type(error) is not ErrorValue or type(error.status) is not bool or type(error.code) is not int or type(error.source) is not str:
        raise TypeError('Explicit bool/int/str ErrorValue required')


def require_inputs(uids,defaults,references,returns):
    expected=set(uids)
    if any(type(d) is not dict or set(d)!=expected for d in (defaults,references,returns)):
        raise ValueError('Exact supplied default/reference/return sites required')
    for uid in uids:
        if type(returns[uid]) is not ReaderReturn:
            raise TypeError('Explicit ReaderReturn required')
        require_error(returns[uid].error)


def read_chain(defaults,references,returns):
    """Completed frames0/1:13 returned-data writes and wired error forwarding.

    Data/reference objects are opaque supplied snapshots,never coerced or read
    for selection. Native input-error/default-substitution behavior is external.
    The last Error is supplied to sequence local34531;its consumer is outside.
    """
    require_inputs(CHAIN,defaults,references,returns)
    error=UNWIRED
    calls,assignments=[],[]
    for uid,(name,control) in zip(CHAIN,LOCALS):
        returned=returns[uid]
        calls.append(ReaderCall(uid,references[uid],error,defaults[uid],returned))
        assignments.append((name,control,returned.data))
        error=returned.error
    return ReadSlice(tuple(calls),tuple(assignments),error)


def independent_read(defaults,references,returns):
    """Frame2 reader51964 starts with unwired Error;returned Error is unused.

    Returned data feeds local C10-11 NI6602 and demux58801. Only unconditional
    local assignment is projected here;counter request consumer is outside.
    """
    require_inputs((INDEPENDENT,),defaults,references,returns)
    returned=returns[INDEPENDENT]
    call=ReaderCall(INDEPENDENT,references[INDEPENDENT],UNWIRED,defaults[INDEPENDENT],returned)
    return ReadSlice((call,),((LOCALS[7][0],LOCALS[7][1],returned.data),),None)


def exact(value,fields):
    if type(value) is not dict or set(value)!=set(fields):
        raise ValueError('Exact replay fields required')


def replay_saved_sup_reads(payload):
    exact(payload,('source_id','uid','frames_returned','defaults','references','returns'))
    if payload['source_id']!='APP-17' or payload['uid'] not in ('13595','51964'):
        raise ValueError('Selected APP-17 reader slice required')
    chain=payload['uid']=='13595'
    expected_frames=['14799','15121'] if chain else ['49696']
    if type(payload['frames_returned']) is not list or payload['frames_returned']!=expected_frames:
        raise ValueError('Explicit completed selected frames required')
    uids=CHAIN if chain else (INDEPENDENT,)
    if type(payload['returns']) is not dict or set(payload['returns'])!=set(uids):
        raise ValueError('Exact supplied return sites required')
    returns={}
    for uid in uids:
        entry=payload['returns'][uid];exact(entry,('data','error'));error=entry['error']
        exact(error,('status','code','source'))
        err=ErrorValue(error['status'],error['code'],error['source']);require_error(err)
        if not -(2**31)<=err.code<2**31 or len(err.source)>1024:
            raise ValueError('Replay Error storage limits exceeded')
        returns[uid]=ReaderReturn(entry['data'],err)
    result=(read_chain if chain else independent_read)(payload['defaults'],payload['references'],returns)
    return dict(source_id='APP-17',uid=payload['uid'],scope='SUPPLIED_COMPLETED_SUPERVISION_READ_SLICE',
        calls=[dict(node_uid=c.node_uid,reference_in=c.reference_in,
            error_in=dict(connection='unwired') if c.error_in is UNWIRED else dict(c.error_in._asdict()),
            default_data=c.default_data,returned_data=c.returned.data,returned_error=dict(c.returned.error._asdict())) for c in result.calls],
        local_assignments=[dict(name=name,control_id=control,data=data) for name,control,data in result.local_assignments],
        final_error=dict(result.final_error._asdict()) if result.final_error is not None else None,
        downstream_consumers_implemented=False,data_and_references='OPAQUE_SUPPLIED_SNAPSHOTS',
        frame_reachability_supplied=True,execution_allowed=False,external_calls_executed=False,
        hardware_writes=False,psp_delivery_qualified=False,atomic_snapshots_qualified=False,
        native_default_return_semantics_qualified=False,native_refnum_decoding_qualified=False,
        native_runtime_equivalence=False,whole_timeout_equivalence=False)
