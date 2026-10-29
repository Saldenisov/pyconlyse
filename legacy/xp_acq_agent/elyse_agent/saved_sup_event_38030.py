"""Bounded saved [14] "Page Fluides": Value Change body, original APP-17.

NewVal arithmetic and each Page/C8 read carrier are separate observations.
All native writer/Wait values, unwired inputs, and error-case selector are
supplied. The selector is a hypothetical typed boolean boundary; agreement
with supplied error.status does not prove native cluster-selection semantics.
Completion observations are caller subsets in reported order, not feasible
source traces, prefixes, timing, success, atomicity, or execution receipts.
"""
from collections import namedtuple
import math
import struct

SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909';FRAME_UID='38030';SAVED_CAPTION='[14] "Page Fluides": Value Change'
READ_UIDS=('38095','11796','43037','45088','48871','38705','43064','45134','48897')
WRITER_UIDS=('38229','36455','42992','44982','48837')
WAIT_UIDS=('62593','38508','57473','61892','56723')
BORDER_UIDS=('38040','38043','38046','38037')
SINK_UIDS=('38203','38229','62593','10163','26383','36455','38508','43029','42984','42992','57473','45062','44959','44982','61892','48863','48829','48837','56723','38326')
NUMERIC_ABS_BOUND=float(2**40)
DELTA=struct.unpack('>d',bytes.fromhex('3FB999999999999A'))[0]
REQUEST_PATHS=(7,6,20,19)
PAGE_FLOAT_FIELDS=(4,5,21,22)
RAW_TO_TOP={11:4,13:6,14:7,15:8,16:9,26:19,27:20,28:21}
# Primitive output, Page read/write/bundle, C8 read/write/bundle, native leaves.
BRANCHES={
 1:('39304',1051,'39815','11796','10163','13496','38705','26383','38656','36455','36087','38508','9718','10228','10559',4,1,'43510','38282'),
 2:('13520',1050,'39964','43037','43029','43043','43064','42984','43054','42992','43093','57473','57421','57423','57436',4,1,'43081','43070'),
 4:('10570',1051,'46355','45088','45062','45095','45134','44959','45113','44982','45220','61892','56752','61864','61876',21,2,'45195','45169'),
 8:('19403',1050,'29253','48871','48863','48877','48897','48829','48887','48837','48937','56723','56693','56695','56707',21,2,'48925','48914')}
UPDATE_TERMINALS={'38212':('38218','38222'),'13496':('16553','52924','70305','70308','70311'),'43043':('43050','62616','62621','62624','62627'),'45095':('45104','8796','63276','63279','63282'),'48877':('48883','57506','57511','57514','57517'),'38656':('41084',),'43054':('43060',),'45113':('45129',),'48887':('48893',)}
WRITER_PORTS={'38229':('38234','38237','38240','38243','38246'),'36455':('36458','36465','36600','36621','36647'),'42992':('42994','42997','43000','43003','43006'),'44982':('44984','44994','45004','45013','45022'),'48837':('48839','48842','48845','48848','48851')}
WAIT_PORTS={'62593':('62598','62595'),'38508':('38521','38518'),'57473':('57478','57475'),'61892':('61897','61894'),'56723':('56728','56725')}
PREFIX_HEX={
 '37662':'45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465204D2F412064752067726F7570652064652072E967756C6174696F6E3A20',
 '38282':'45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465203C206C65206C6120636F6E7369676E652064652054B02063616E6F6E3A20',
 '43070':'45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465203E206C65206C6120636F6E7369676E652064652054B02063616E6F6E3A20',
 '45169':'45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465203C206C65206C6120636F6E7369676E652064652054B0206465206C612073656374696F6E3A20',
 '48914':'45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465203E206C65206C6120636F6E7369676E652064652054B0206465206C612073656374696F6E3A20'}
PREFIX_BYTES={uid:bytes.fromhex(raw)for uid,raw in PREFIX_HEX.items()}

EventDataReturn=namedtuple('EventDataReturn','event_type time control_reference old_value new_value aggregate_effective_value')
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
WriterReturn=namedtuple('WriterReturn','reference_out error_out')
WriterBoundary=namedtuple('WriterBoundary','reference_in supplied_unwired_error_input returned')
WaitReturn=namedtuple('WaitReturn','timer_value')
NativeBoundaries=namedtuple('NativeBoundaries','border_values writers waits')
LocalRead=namedtuple('LocalRead','node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment=namedtuple('LocalAssignment','node_uid control_id saved_param_index saved_bank_uid data')
WriterCall=namedtuple('WriterCall','node_uid reference_constant_uid reference_literal boundary data')
WaitCall=namedtuple('WaitCall','node_uid input_terminal_uid milliseconds returned_timer')
ArithmeticStep=namedtuple('ArithmeticStep','node_uid prim_res_id input_slots output_terminal_uid value')
Event38030Slice=namedtuple('Event38030Slice','local_reads event_return request_vector request_any dps_any request_mask selected_frames arithmetic_steps field_updates local_assignments writer_call wait_call returned_error error_case_selector error_prefix_bytes error_text_bytes completed_sinks')

def hex_bytes(value):
    if type(value)is not bytes:raise TypeError('Exact bytes required')
    return ''.join('{:02X}'.format(b)for b in value)

def exact(value,fields):
    if type(value)is not dict or set(value)!=set(fields):raise ValueError('Exact frame38030 fields required')

def page(value):
    if type(value)is not tuple or len(value)!=23:raise TypeError('Decoded PageFluides tuple23 required')
    for i,v in enumerate(value):
        if i==3:
            if type(v)is not tuple or len(v)!=7 or any(type(x)is not float for x in v):raise TypeError('Decoded Graph tuple7DBL required')
        elif i in PAGE_FLOAT_FIELDS:
            if type(v)is not float:raise TypeError('Decoded Page DBL field required')
        elif type(v)is not bool:raise TypeError('Decoded Page Boolean field required')

def boolean_carrier(value):
    if type(value)is not tuple or len(value)!=29 or any(type(v)is not bool for v in value):raise TypeError('Decoded DPS tuple29Boolean required')

def dbl_carrier(value):
    if type(value)is not tuple or len(value)!=10 or any(type(v)is not float for v in value):raise TypeError('Decoded C8 tuple10DBL required')

def error(value):
    if type(value)is not ErrorValue or type(value.status)is not bool or type(value.code)is not int or not -(2**31)<=value.code<2**31 or type(value.source_bytes)is not bytes or len(value.source_bytes)>4096:
        raise TypeError('Explicit decoded error Boolean/I32/source bytes required')

def build_request_vector(values):
    if type(values)is not tuple or len(values)!=4 or any(type(v)is not bool for v in values):raise TypeError('Four source Boolean scalars required')
    return values

def concatenate_error_bytes(prefix,source):
    if type(prefix)is not bytes or type(source)is not bytes or len(prefix)>4096 or len(source)>4096:raise TypeError('Bounded byte string operands required')
    return prefix+source

def project_event_38030(event_return,local_reads,native_boundaries,error_case_selector,completed_sinks=None):
    """Direct bounded cases. No callback, PSP, sleep, or source execution."""
    if type(event_return)is not EventDataReturn or type(native_boundaries)is not NativeBoundaries:raise TypeError('Explicit native/event boundary records required')
    if type(error_case_selector)is not bool:raise TypeError('Hypothetical error-case Boolean boundary required')
    exact(local_reads,READ_UIDS);exact(native_boundaries.border_values,BORDER_UIDS)
    exact(native_boundaries.writers,WRITER_UIDS);exact(native_boundaries.waits,WAIT_UIDS)
    page(event_return.new_value);boolean_carrier(local_reads['38095'])
    vector=build_request_vector(tuple(event_return.new_value[i]for i in REQUEST_PATHS))
    request_any=any(vector);dps_any=any(local_reads['38095']);mask=sum((1<<i)for i,v in enumerate(vector)if v)
    if mask not in(0,1,2,4,8):raise ValueError('Composite request mask has unqualified saved default policy')
    reads=[LocalRead('38095','135295',176,'135293',local_reads['38095'])];frames=[];steps=[];updates=[];assignments=[];writer=None;wait=None
    returned_error=ErrorValue(False,0,b'');prefix=b''
    def native(writer_uid,reference_uid,reference_name,data,wait_uid):
        boundary=native_boundaries.writers[writer_uid];wait_return=native_boundaries.waits[wait_uid]
        if type(boundary)is not WriterBoundary or type(boundary.returned)is not WriterReturn or type(wait_return)is not WaitReturn:raise TypeError('Explicit selected writer/Wait records required')
        error(boundary.returned.error_out)
        milliseconds=native_boundaries.border_values['38037']
        if type(milliseconds)is not int or not 0<=milliseconds<2**32:raise TypeError('Exact supplied U32 wait input required')
        return WriterCall(writer_uid,reference_uid,reference_name,boundary,data),WaitCall(wait_uid,WAIT_PORTS[wait_uid][0],milliseconds,wait_return.timer_value),boundary.returned.error_out
    if not(request_any or dps_any):
        frames.append(('38117','38154',False));fields=list(local_reads['38095']);fields[0]=event_return.new_value[9];fields[1]=event_return.new_value[8];result=tuple(fields)
        updates.extend((('38212',None,(0,),fields[0]),('38212',1,(1,),fields[1])))
        assignments.append(LocalAssignment('38203','135295',176,'135293',result))
        writer,wait,returned_error=native('38229','38160','ni.var.psp://localhost/SUPERVISION/DPS',result,'62593');prefix=PREFIX_BYTES['37662']
    else:
        frames.append(('38117','38451',True));frames.append(('39025','43145'if request_any else'43139',request_any))
        if request_any:
            (arith,resid,out,pr,pw,pbundle,cr,cw,cbundle,writer_uid,reference_uid,wait_uid,seq,seqframe,diag,target,c8field,literal,prefix_uid)=BRANCHES[mask]
            frames.extend((('19503',{1:'41911',2:'38348',4:'39993',8:'27926'}[mask],mask),(seq,diag,0)))
            carrier=local_reads[pr];c8=local_reads[cr];page(carrier);dbl_carrier(c8)
            x=event_return.new_value[target]
            if not math.isfinite(x)or abs(x)>NUMERIC_ABS_BOUND:raise ValueError('Finite selected NewVal DBL abs<=2**40 required; source range unqualified')
            value=x-DELTA if resid==1051 else x+DELTA;steps.append(ArithmeticStep(arith,resid,((1,DELTA),(2,x)),out,value))
            pfields=list(carrier);pfields[target]=value
            # Raw 45095 has duplicate13, not13/14. Equal False writes preserve it.
            raw_fields=(13,13,26,27)if mask==4 else(13,14,26,27)
            for raw_index in raw_fields:
                top=RAW_TO_TOP[raw_index];pfields[top]=False;updates.append((pbundle,raw_index,(top,),False))
            updates.insert(0,(pbundle,11 if target==4 else 28,(target,),value))
            cfields=list(c8);cfields[c8field]=value;updates.append((cbundle,c8field,(c8field,),value))
            presult=tuple(pfields);cresult=tuple(cfields)
            reads.extend((LocalRead(pr,'125075',4,'125073',carrier),LocalRead(cr,'67056',24,'67054',c8)))
            assignments.extend((LocalAssignment(pw,'125075',4,'125073',presult),LocalAssignment(cw,'67056',24,'67054',cresult)))
            writer,wait,returned_error=native(writer_uid,reference_uid,'ni.var.psp://localhost/SUPERVISION/C8NI6703',cresult,wait_uid);prefix=PREFIX_BYTES[prefix_uid]
    frames.append(('38249','38276'if error_case_selector else'38268',error_case_selector))
    text=None
    if error_case_selector:
        text=concatenate_error_bytes(prefix,returned_error.source_bytes);assignments.append(LocalAssignment('38326','61053',184,'61051',text))
    active={a.node_uid for a in assignments}
    if writer:active.add(writer.node_uid)
    if wait:active.add(wait.node_uid)
    if completed_sinks is not None:
        if type(completed_sinks)is not tuple or len(set(completed_sinks))!=len(completed_sinks)or any(type(uid)is not str or uid not in active for uid in completed_sinks):raise ValueError('Unique caller completion subset of selected saved sinks required')
    return Event38030Slice(tuple(reads),event_return,vector,request_any,dps_any,mask,tuple(frames),tuple(steps),tuple(updates),tuple(assignments),writer,wait,returned_error,error_case_selector,prefix,text,completed_sinks)

def _json_tree(value):
    budget=[4096]
    def visit(v,depth):
        budget[0]-=1
        if budget[0]<0 or depth>10:raise ValueError('JSON node/depth bound exceeded')
        k=type(v)
        if v is None or k is bool:return
        if k is int:
            if not -(2**63)<=v<2**64:raise ValueError('JSON integer bound exceeded')
            return
        if k is float:
            if not math.isfinite(v):raise ValueError('Finite JSON numbers required')
            return
        if k is str:
            if len(v)>8192:raise ValueError('JSON string bound exceeded')
            return
        if k is list:
            if len(v)>64:raise ValueError('JSON list bound exceeded')
            for x in v:visit(x,depth+1)
            return
        if k is dict:
            if len(v)>64 or any(type(x)is not str or len(x)>256 for x in v):raise ValueError('JSON object bound exceeded')
            for x in v.values():visit(x,depth+1)
            return
        raise TypeError('Inert JSON values required')
    visit(value,0)

def _page_json(value):
    if type(value)is not list or len(value)!=23 or type(value[3])is not list:raise TypeError('JSON Page23/Graph7 lists required')
    fields=list(value);fields[3]=tuple(fields[3]);return tuple(fields)

def _error_json(value):
    exact(value,('status','code','source_hex'))
    raw=value['source_hex']
    if type(raw)is not str or len(raw)>8192 or len(raw)%2 or any(c not in'0123456789ABCDEF'for c in raw):raise ValueError('Canonical uppercase source byte hex required')
    result=ErrorValue(value['status'],value['code'],bytes.fromhex(raw));error(result);return result

def replay_saved_sup_event_38030(payload):
    _json_tree(payload);exact(payload,('source_id','source_version','event_uid','frame_uid','local_reads','event_returns','border_inputs','unwired_inputs','reference_inputs','native_returns','error_case_selector','completed_sinks'))
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('Exact original source/version/event/frame required')
    exact(payload['local_reads'],READ_UIDS);reads=dict(payload['local_reads'])
    exact(payload['event_returns'],('38049',));events=payload['event_returns']['38049'];exact(events,('38051','38054','38058','38062','38070','38074'))
    newval=_page_json(events['38074']);event=EventDataReturn(events['38054'],events['38058'],events['38062'],events['38070'],newval,events['38051'])
    # Determine active alternatives before accessing their supplied carriers.
    if type(reads['38095'])is not list:raise TypeError('JSON DPS29 list required')
    reads['38095']=tuple(reads['38095']);page(newval);boolean_carrier(reads['38095'])
    mask=sum(1<<i for i,p in enumerate(REQUEST_PATHS)if newval[p])
    if mask in BRANCHES:
        pr,cr=BRANCHES[mask][3],BRANCHES[mask][6];reads[pr]=_page_json(reads[pr])
        if type(reads[cr])is not list:raise TypeError('JSON C8 carrier list required')
        reads[cr]=tuple(reads[cr])
    exact(payload['border_inputs'],BORDER_UIDS)
    reference_uids=('38160','36087','43093','45220','48937');exact(payload['reference_inputs'],reference_uids)
    error_input_uids=tuple(WRITER_PORTS[u][2]for u in WRITER_UIDS);exact(payload['unwired_inputs'],error_input_uids)
    exact(payload['native_returns'],WRITER_UIDS+WAIT_UIDS);writers={};waits={}
    for uid,ref in zip(WRITER_UIDS,reference_uids):
        raw=payload['native_returns'][uid];ports=WRITER_PORTS[uid];exact(raw,(ports[1],ports[3]));writers[uid]=WriterBoundary(payload['reference_inputs'][ref],payload['unwired_inputs'][ports[2]],WriterReturn(raw[ports[1]],_error_json(raw[ports[3]])))
    for uid in WAIT_UIDS:
        raw=payload['native_returns'][uid];exact(raw,(WAIT_PORTS[uid][1],));waits[uid]=WaitReturn(raw[WAIT_PORTS[uid][1]])
    completion=payload['completed_sinks']
    if completion is not None:
        if type(completion)is not list:raise TypeError('JSON completion list or null required')
        completion=tuple(completion)
    result=project_event_38030(event,reads,NativeBoundaries(payload['border_inputs'],writers,waits),payload['error_case_selector'],completion)
    def data(value):
        if type(value)is bytes:return dict(bytes_hex=hex_bytes(value))
        if type(value)is tuple:return[data(v)for v in value]
        return value
    writer=None
    if result.writer_call:
        call=result.writer_call;writer=dict(node_uid=call.node_uid,reference_constant_uid=call.reference_constant_uid,reference_literal=call.reference_literal,reference_in=call.boundary.reference_in,supplied_unwired_error_input=call.boundary.supplied_unwired_error_input,data=data(call.data),supplied_returns=payload['native_returns'][call.node_uid])
    wait=None
    if result.wait_call:
        call=result.wait_call;wait=dict(node_uid=call.node_uid,input_terminal_uid=call.input_terminal_uid,milliseconds=call.milliseconds,supplied_timer_return=call.returned_timer)
    field_updates=[];ordinals={}
    for uid,raw_index,path,value in result.field_updates:
        ordinal=ordinals.get(uid,0);ordinals[uid]=ordinal+1
        field_updates.append(dict(node_uid=uid,terminal_uid=UPDATE_TERMINALS[uid][ordinal],raw_flattened_field_index=raw_index,descriptor_projection_ordinal=raw_index if raw_index is not None else 0,typed_position_path=list(path),value=value))
    return dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,saved_caption=SAVED_CAPTION,
        request_vector=list(result.request_vector),request_any=result.request_any,dps_any=result.dps_any,request_mask=result.request_mask,
        selected_frames=[list(r)for r in result.selected_frames],event_returns=payload['event_returns'],
        local_reads={r.node_uid:dict(control_id=r.control_id,saved_param_index=r.saved_param_index,saved_bank_uid=r.saved_bank_uid,data=data(r.data))for r in result.local_reads},
        arithmetic_by_uid={s.node_uid:dict(saved_primResID=s.prim_res_id,input_slots={str(i):v for i,v in s.input_slots},output_terminal_uid=s.output_terminal_uid,value=s.value)for s in result.arithmetic_steps},
        field_updates=field_updates,
        local_assignments={a.node_uid:dict(control_id=a.control_id,saved_param_index=a.saved_param_index,saved_bank_uid=a.saved_bank_uid,data=data(a.data))for a in result.local_assignments},
        writer_call=writer,wait_call=wait,returned_error=dict(status=result.returned_error.status,code=result.returned_error.code,source_hex=hex_bytes(result.returned_error.source_bytes)),
        error_case_selector=result.error_case_selector,error_prefix_hex=hex_bytes(result.error_prefix_bytes),error_text_hex=None if result.error_text_bytes is None else hex_bytes(result.error_text_bytes),
        completed_sinks=None if completion is None else list(completion),completion_observation_semantics='caller_subset_in_reported_order_not_feasible_trace_or_prefix',
        selector_boundary_semantics='hypothetical_supplied_boolean_incompatible_error_status_pairs_do_not_prove_source_realizability',
        source_execution=False,native_execution=False,PSP_execution=False,hardware_execution=False,native_float_bitwise_equivalence=False,
        native_coercion_qualified=False,native_reference_decoding_qualified=False,native_error_selector_projection_qualified=False,
        native_defaults_qualified=False,unwired_native_defaults_qualified=False,units_qualified=False,UI_permitted_values_qualified=False,
        event_queue_selection_qualified=False,atomic_snapshot_qualified=False,fanout_order_qualified=False,writer_success_gates_local_assignment=False,
        native_primitive_semantics_qualified=False,multi_request_mask_default_qualified=False,whole_body_qualified=False,whole_frame_equivalence=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        qualification_scope='Direct Python cases/request reductions/numeric/carrier/byte concat in guarded domains; native leaves and error selector explicitly supplied')
