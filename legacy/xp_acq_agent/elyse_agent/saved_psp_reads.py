"""Saved completed-frame PSP caller routing; Python3.4 and no transport."""
import math
from collections import namedtuple
from .saved_xnode import ErrorValue

SITES = (('10310', 'C6NI6703', 9, 10, float), ('10333', 'C7NI6703', 10, 10, float), ('10369', 'C8NI6703', 11, 10, float), ('10449', 'C9NI6703', 12, 10, float), ('22278', 'C1011NI6602', 39, 33, float), ('25403', 'C3_OUT_DIO96', 17, 40, bool), ('25426', 'C4_OUT_DIO96', 15, 32, bool), ('25449', 'C5_OUT_DIO96', 13, 40, bool), ('19950', 'DPS', 36, 29, bool), ('19974', 'DPC', 37, 5, bool), ('19997', 'EPS', 44, 77, bool), ('22840', 'EPC', 38, 12, bool))
URI_PREFIX='ni.var.psp://10.20.30.2/SUPERVISION/'
UNWIRED=namedtuple('UnwiredValue','connection')('unwired')
PspReturn=namedtuple('PspReturn','data error')
ReadCall=namedtuple('ReadCall','node_uid uri error_in default_data returned')
ReadFrame=namedtuple('ReadFrame','calls data_assignments fault_assignments stop_after tcp_ed_after')


def route_read_values(default_snapshots,returned_snapshots,stop_before,tcp_ed_before,unwired):
    """Prevalidated supplied returns; identity-preserving caller body,not a callback."""
    error=unwired
    calls,assignments=[],[]
    for uid,tag,bank,size,element in SITES:
        prior,returned=default_snapshots[uid],returned_snapshots[uid]
        calls.append(ReadCall(uid,URI_PREFIX+tag,error,prior,returned))
        assignments.append((bank,returned.data))
        error=returned.error
    faults=((30,False),(45,False)) if error.status else ()
    return ReadFrame(tuple(calls),tuple(assignments),faults,
        False if error.status else stop_before,False if error.status else tcp_ed_before)


def require_cluster(value,size,element):
    if type(value) is not tuple or len(value)!=size or any(type(v) is not element for v in value):
        raise TypeError('explicit immutable full-size PSP cluster snapshot required')


def require_error(error):
    if type(error) is not ErrorValue or type(error.status) is not bool or type(error.code) is not int or type(error.source) is not str:
        raise TypeError('explicit bool/int/str ErrorValue required')


def read_frame(default_snapshots,returned_snapshots,stop_before,tcp_ed_before):
    if type(stop_before) is not bool or type(tcp_ed_before) is not bool:
        raise TypeError('explicit stop and TCP ED Boolean snapshots required')
    expected={s[0] for s in SITES}
    if type(default_snapshots) is not dict or type(returned_snapshots) is not dict or set(default_snapshots)!=expected or set(returned_snapshots)!=expected:
        raise ValueError('all twelve reader-return/default snapshots required')
    for uid,tag,bank,size,element in SITES:
        returned=returned_snapshots[uid]
        if type(returned) is not PspReturn:
            raise TypeError('explicit PSP data and ErrorValue return required')
        require_error(returned.error)
        require_cluster(default_snapshots[uid],size,element)
        require_cluster(returned.data,size,element)
    return route_read_values(default_snapshots,returned_snapshots,stop_before,tcp_ed_before,UNWIRED)


def exact(value,fields):
    if type(value) is not dict or set(value)!=set(fields):
        raise ValueError('exact saved PSP replay fields required')


def json_cluster(value,size,element):
    if type(value) is not list:
        raise ValueError('explicit JSON cluster list required')
    result=tuple(value)
    require_cluster(result,size,element)
    if element is float and any(not math.isfinite(v) for v in result):
        raise ValueError('finite replay float storage required')
    return result


def json_error(value):
    exact(value,('status','code','source'))
    error=ErrorValue(value['status'],value['code'],value['source'])
    require_error(error)
    if not -(2**31)<=error.code<2**31 or len(error.source)>1024:
        raise ValueError('replay Error storage limits exceeded')
    return error


def encode_error(value):
    return dict(connection='unwired') if value is UNWIRED else dict(value._asdict())


def replay_saved_psp_reads(payload):
    exact(payload,('source_id','uid','frame_returned','defaults','returns','stop_before','tcp_ed_before'))
    if payload['source_id']!='APP-00' or payload['uid']!='10115':
        raise ValueError('APP-00 saved frame10115 required')
    if payload['frame_returned'] is not True:
        raise ValueError('explicit completed frame required;partial writes are not projected')
    expected={s[0] for s in SITES}
    if type(payload['defaults']) is not dict or type(payload['returns']) is not dict or set(payload['defaults'])!=expected or set(payload['returns'])!=expected:
        raise ValueError('all twelve JSON default/return snapshots required')
    defaults,returns={},{}
    for uid,tag,bank,size,element in SITES:
        defaults[uid]=json_cluster(payload['defaults'][uid],size,element)
        returned=payload['returns'][uid]
        exact(returned,('data','error'))
        returns[uid]=PspReturn(json_cluster(returned['data'],size,element),json_error(returned['error']))
    result=read_frame(defaults,returns,payload['stop_before'],payload['tcp_ed_before'])
    return dict(source_id='APP-00',uid='10115',scope='SUPPLIED_COMPLETED_FRAME_PSP_CALLER',
        calls=[dict(node_uid=c.node_uid,uri=c.uri,error_in=encode_error(c.error_in),
            default_data=list(c.default_data),returned_data=list(c.returned.data),returned_error=encode_error(c.returned.error)) for c in result.calls],
        data_assignments=[dict(bank=bank,data=list(data)) for bank,data in result.data_assignments],
        fault_assignments=[dict(bank=bank,value=value) for bank,value in result.fault_assignments],
        stop_after=result.stop_after,tcp_ed_after=result.tcp_ed_after,frame_reachability_supplied=True,
        execution_allowed=False,external_calls_executed=False,hardware_writes=False,psp_delivery_qualified=False,
        atomic_snapshots_qualified=False,native_default_return_semantics_qualified=False,native_runtime_equivalence=False,
        scheduling_qualified=False,whole_timeout_equivalence=False)
