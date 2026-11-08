"""Saved [2] "AXE H": Value Change; "GAP H": Value Change, frame65050.

Separate local read observations feed eight Python arithmetic steps and fields2/3
of a decoded ten-DBL carrier. Native writer/handler leaves and all completions
are supplied. Source/native bitwise/coercion/units/event semantics remain open.
Completion tuples are caller-selected reported subsets in supplied order, never
source-feasible execution traces or prefixes. A reported handler observation
does not establish or exclude an unreported writer predecessor completion.
"""
from collections import namedtuple
import math
import struct

SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909'
FRAME_UID='65050'
SAVED_CAPTION='[2] "AXE H": Value Change; "GAP H": Value Change'
SCALAR_READ_UIDS=('62319','62327','69067','69089')
READ_UIDS=SCALAR_READ_UIDS+('88920',)
SINK_UIDS=('88976','88939','83833')
HANDLER_INPUT_UIDS=('86365','86368','86371','86383')
HANDLER_OUTPUT_UIDS=('86359','86362','86374','86377','86380')
BODY_NODE_UIDS=('62171','62191','62203','62222','62285','62296','62309','62319','62327','65078','67319','68988','69008','69023','69033','69044','69057','69067','69089','83833','88920','88926','88939','88958','88976')
REFERENCE_LITERAL='ni.var.psp://localhost/SUPERVISION/C9NI6703'
NUMERIC_ABS_BOUND=float(2**40)
LITERAL_HEX={'62191':'4014000000000000','62222':'3FB90FF972474539','62309':'3FA916872B020C4A','68988':'4014000000000000','69023':'BFB90FF972474539','69057':'3FA916872B020C4A'}
LITERALS={uid:struct.unpack('>d',bytes.fromhex(raw))[0]for uid,raw in LITERAL_HEX.items()}
DEPENDENCIES=(('62327','62203'),('62222','62203'),('62203','62171'),('62191','62171'),('62319','62296'),('62309','62296'),('62171','62285'),('62296','62285'),('69089','69008'),('69023','69008'),('69008','67319'),('68988','67319'),('69067','69044'),('69057','69044'),('67319','69033'),('69044','69033'),('62285','88926'),('69033','88926'),('88920','88926'),('88926','88976'),('88926','88939'),('88958','88939'),('88939','83833'))

EventDataReturn=namedtuple('EventDataReturn','event_type time control_reference old_value new_value')
UnwiredInput=namedtuple('UnwiredInput','effective_value')
WriterReturn=namedtuple('WriterReturn','reference_out error_out')
HandlerUnwiredInputs=namedtuple('HandlerUnwiredInputs','input86365 input86368 input86371 input86383')
HandlerReturn=namedtuple('HandlerReturn','output86359 output86362 output86374 output86377 output86380')
LocalRead=namedtuple('LocalRead','node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment=namedtuple('LocalAssignment','node_uid control_id saved_param_index saved_bank_uid data')
ArithmeticStep=namedtuple('ArithmeticStep','node_uid prim_res_id input_slots output_terminal_uid value')
WriterCall=namedtuple('WriterCall','node_uid reference_constant_uid reference_literal reference_in supplied_error_input data returned')
HandlerCall=namedtuple('HandlerCall','node_uid wired_error_input_uid supplied_error_in unwired_inputs returned')
Event65050Slice=namedtuple('Event65050Slice','local_reads event_return arithmetic_steps updated_cluster local_assignment writer_call handler_call completed_sinks dependencies')


def exact(value,fields):
    if type(value)is not dict or set(value)!=set(fields):raise ValueError('Exact frame65050 fields required')


def require_completion(value):
    if value is None:return
    if type(value)is not tuple or len(value)>3 or any(type(uid)is not str or uid not in SINK_UIDS for uid in value)or len(set(value))!=len(value):
        raise ValueError('Unique caller supplied saved sink completion tuple required')


def require_reads(value):
    exact(value,READ_UIDS)
    for uid in SCALAR_READ_UIDS:
        number=value[uid]
        if type(number)is not float or not math.isfinite(number)or abs(number)>NUMERIC_ABS_BOUND:
            raise ValueError('Exact finite scalar float abs<=2**40 required; source UI bounds unqualified')
    carrier=value['88920']
    if type(carrier)is not tuple or len(carrier)!=10 or any(type(v)is not float for v in carrier):
        raise TypeError('Explicit tuple of ten decoded DBL fields required')


def project_event_65050(local_reads,event_return,reference_in,writer_error_input,writer_return,
                       handler_unwired_inputs,handler_return,completed_sinks=None):
    """Apply saved slots; subtract slot2 minus slot1. No native leaf called."""
    require_reads(local_reads)
    for value,cls in ((event_return,EventDataReturn),(writer_error_input,UnwiredInput),(writer_return,WriterReturn),
                     (handler_unwired_inputs,HandlerUnwiredInputs),(handler_return,HandlerReturn)):
        if type(value)is not cls:raise TypeError('Explicit native/event boundary record required')
    require_completion(completed_sinks)
    steps=[]
    def arithmetic(uid,resid,in1,in2,terminal):
        value=in1+in2 if resid==1050 else in2-in1 if resid==1051 else in1*in2
        steps.append(ArithmeticStep(uid,resid,((1,in1),(2,in2)),terminal,value))
        return value
    first_axis=arithmetic('62203',1052,local_reads['62327'],LITERALS['62222'],'62205')
    first_sum=arithmetic('62171',1050,first_axis,LITERALS['62191'],'62177')
    first_gap=arithmetic('62296',1052,local_reads['62319'],LITERALS['62309'],'62298')
    field2=arithmetic('62285',1051,first_gap,first_sum,'62287')
    second_axis=arithmetic('69008',1052,local_reads['69089'],LITERALS['69023'],'69012')
    second_sum=arithmetic('67319',1050,second_axis,LITERALS['68988'],'68974')
    second_gap=arithmetic('69044',1052,local_reads['69067'],LITERALS['69057'],'69046')
    field3=arithmetic('69033',1051,second_gap,second_sum,'69035')
    fields=list(local_reads['88920']);fields[2]=field2;fields[3]=field3;updated=tuple(fields)
    reads=tuple(LocalRead(uid,control,slot,bank,local_reads[uid])for uid,control,slot,bank in
        (('62319','81239',222,'81237'),('62327','118192',221,'118190'),('69067','81239',222,'81237'),('69089','118192',221,'118190'),('88920','66941',25,'66939')))
    assignment=LocalAssignment('88976','66941',25,'66939',updated)
    writer=WriterCall('88939','88958',REFERENCE_LITERAL,reference_in,writer_error_input.effective_value,updated,writer_return)
    handler=HandlerCall('83833','86386',writer_return.error_out,handler_unwired_inputs,handler_return)
    return Event65050Slice(reads,event_return,tuple(steps),updated,assignment,writer,handler,completed_sinks,DEPENDENCIES)


def _json_tree(value):
    budget=[1024]
    def visit(item,depth):
        budget[0]-=1
        if budget[0]<0 or depth>8:raise ValueError('JSON frame65050 node/depth bound exceeded')
        kind=type(item)
        if item is None or kind is bool:return
        if kind is int:
            if not -(2**63)<=item<2**64:raise ValueError('JSON integer bound exceeded')
            return
        if kind is float:
            if not math.isfinite(item):raise ValueError('Finite JSON numbers required')
            return
        if kind is str:
            if len(item)>4096:raise ValueError('JSON string bound exceeded')
            return
        if kind is list:
            if len(item)>64:raise ValueError('JSON list bound exceeded')
            for child in item:visit(child,depth+1)
            return
        if kind is dict:
            if len(item)>64 or any(type(k)is not str or len(k)>256 for k in item):raise ValueError('JSON object bound exceeded')
            for child in item.values():visit(child,depth+1)
            return
        raise TypeError('Inert JSON values required')
    visit(value,0)


def replay_saved_sup_event_65050(payload):
    _json_tree(payload)
    exact(payload,('source_id','source_version','event_uid','frame_uid','local_reads','event_returns','reference_inputs','unwired_inputs','native_returns','completed_sinks'))
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):
        raise ValueError('Exact original source/version/event/frame required')
    local=payload['local_reads'];exact(local,READ_UIDS)
    reads=dict(local)
    if type(reads['88920'])is not list:raise ValueError('JSON carrier list required')
    reads['88920']=tuple(reads['88920'])
    events=payload['event_returns'];exact(events,('65078',));event=events['65078'];exact(event,('65083','65087','65090','65094','65097'))
    refs=payload['reference_inputs'];exact(refs,('88958',))
    unwired=payload['unwired_inputs'];exact(unwired,('88947',)+HANDLER_INPUT_UIDS)
    native=payload['native_returns'];exact(native,('88939','83833'))
    writer=native['88939'];exact(writer,('88944','88950'))
    handler=native['83833'];exact(handler,HANDLER_OUTPUT_UIDS)
    completion=payload['completed_sinks']
    if completion is not None:
        if type(completion)is not list:raise ValueError('JSON completion list or null required')
        completion=tuple(completion)
    result=project_event_65050(reads,EventDataReturn(*(event[uid]for uid in('65083','65087','65090','65094','65097'))),refs['88958'],
        UnwiredInput(unwired['88947']),WriterReturn(writer['88944'],writer['88950']),
        HandlerUnwiredInputs(*(unwired[uid]for uid in HANDLER_INPUT_UIDS)),HandlerReturn(*(handler[uid]for uid in HANDLER_OUTPUT_UIDS)),completion)
    arithmetic={s.node_uid:dict(saved_primResID=s.prim_res_id,input_slots={str(slot):value for slot,value in s.input_slots},output_terminal_uid=s.output_terminal_uid,value=s.value)for s in result.arithmetic_steps}
    local_rows={r.node_uid:dict(control_id=r.control_id,saved_param_index=r.saved_param_index,saved_bank_uid=r.saved_bank_uid,data=list(r.data)if type(r.data)is tuple else r.data)for r in result.local_reads}
    return dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,saved_caption=SAVED_CAPTION,
        local_reads=local_rows,event_returns=events,arithmetic_by_uid=arithmetic,projected_cluster=list(result.updated_cluster),
        local_assignments={'88976':dict(control_id='66941',saved_param_index=25,saved_bank_uid='66939',data=list(result.updated_cluster))},
        writer_call=dict(node_uid='88939',reference_constant_uid='88958',reference_literal=REFERENCE_LITERAL,reference_in=refs['88958'],
            source_error_connection='unwired',supplied_error_input=unwired['88947'],data=list(result.updated_cluster),supplied_returns=writer),
        handler_call=dict(node_uid='83833',wired_error_input_uid='86386',supplied_error_in=writer['88950'],unwired_inputs={uid:unwired[uid]for uid in HANDLER_INPUT_UIDS},supplied_returns=handler),
        completed_sinks=list(completion)if completion is not None else None,dependencies=[list(p)for p in DEPENDENCIES],
        completion_observation_semantics='caller_selected_subset_in_reported_order_not_execution_trace_or_prefix',
        source_execution=False,native_execution=False,PSP_execution=False,hardware_execution=False,
        native_primitive_semantics_qualified=False,native_float_bitwise_equivalence=False,native_coercion_qualified=False,
        native_reference_decoding_qualified=False,unwired_native_defaults_qualified=False,units_qualified=False,UI_permitted_values_qualified=False,
        event_queue_selection_qualified=False,atomic_snapshot_qualified=False,fanout_order_qualified=False,writer_success_gates_local_assignment=False,
        handler_success_gates_local_assignment=False,whole_body_qualified=False,whole_frame_equivalence=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        scalar_guard=dict(exact_type='float',finite=True,absolute_bound=NUMERIC_ABS_BOUND,guard_is_source_UI_bound=False),
        qualification_scope='Python arithmetic and carrier projection with explicit native leaves/read epochs/completions; full source native semantics open')
