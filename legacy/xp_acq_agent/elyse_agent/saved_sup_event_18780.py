"""Bounded original [6] "Page Synchronisation": Value Change source body.

All33 OldVal-NewVal differences, comparisons, iterations, increment, array
indexing, raw32 carrier updates, assignments, Case arms and byte concatenation
are direct. Identified property/ref/class/variant/format/PSP/Wait leaf outputs
are explicit supplied observations. Raw9/5byte literal storage, False-case
unwired Error and loop output/Error selector policies remain unresolved.
Caller completion pairs are observations, not feasible source schedules.
"""
from collections import namedtuple
import math

SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909';FRAME_UID='18780';SAVED_CAPTION='[6] "Page Synchronisation": Value Change'
READ_UIDS=('19687','19774','8733')
LITERAL_UIDS=('49984','47580','41829','40424','19972')
BORDER_UIDS=('19400','19464','19482','19374')
FIELD_COUNT=33;NUMERIC_ABS_BOUND=float(2**40)
LOCAL_IDENTITIES={'19687':('135295',176,'135293'),'19774':('38232',163,'38230'),'20535':('61053',184,'61051'),'21948':('32429',183,'32427'),'22126':('37458',182,'37456'),'35923':('38232',163,'38230'),'37769':('30288',170,'30286'),'8733':('32429',183,'32427')}
ERROR_PREFIX=bytes.fromhex('45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E64652064652064656C616973206F75206C617267657572206465732073796E6368726F733A20')
INITIAL_PREFIX=bytes.fromhex('53796E6368726F2022')
FORMAT_BYTES=bytes.fromhex('2220E020252E3266B5532E')
WAIT_MS=300;LOOP_COLOR=16448250;FINAL_COLOR=11776947

EventDataReturn=namedtuple('EventDataReturn','event_type time control_reference old_value new_value aggregate_effective_value')
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
PropertyReturn=namedtuple('PropertyReturn','reference_out error_out values')
CastReturn=namedtuple('CastReturn','reference_out error_out')
WriterReturn=namedtuple('WriterReturn','reference_out error_out')
VariantReturn=namedtuple('VariantReturn','error_out data')
FormatterReturn=namedtuple('FormatterReturn','error_out formatted_bytes')
WaitReturn=namedtuple('WaitReturn','timer_value')
LoopReturn=namedtuple('LoopReturn','control_reference cluster_property cast color_property writer')
FinalReturn=namedtuple('FinalReturn','control_reference cluster_property cast numeric_property variant formatter')
NativeBoundaries=namedtuple('NativeBoundaries','loop_returns final_return wait_return unwired_inputs border_values')
IntrinsicBoundaries=namedtuple('IntrinsicBoundaries','unwired_false_case_errors loop_error_output error_case_selector')
LocalRead=namedtuple('LocalRead','node_uid control_id saved_param_index saved_bank_uid data loop_iteration')
LocalAssignment=namedtuple('LocalAssignment','node_uid control_id saved_param_index saved_bank_uid data loop_iteration')
LeafObservation=namedtuple('LeafObservation','node_uid loop_iteration inputs supplied_outputs intrinsic_scope')
IndexProjection=namedtuple('IndexProjection','node_uid loop_iteration array_terminal_uid index_terminal_uid output_terminal_uid array index value')
LoopIteration=namedtuple('LoopIteration','index increment difference comparison_literal changed selected_frame supplied_or_returned_error')
Event18780Slice=namedtuple('Event18780Slice','event_return dps_any selected_frames differences iteration_count iterations local_reads field_updates local_assignments leaf_observations index_projections loop_error_candidate supplied_loop_error_output initial_string formatted_string returned_error error_case_selector message_bytes completed_sinks literal_observations')

def exact(value,keys):
    if type(value)is not dict or set(value)!=set(keys):raise ValueError('Exact frame18780 fields required')

def hex_bytes(raw):
    if type(raw)is not bytes:raise TypeError('Exact byte string required')
    return ''.join('{:02X}'.format(b)for b in raw)

def bytes_value(value):
    if type(value)is not bytes or len(value)>4096:raise TypeError('Bounded exact bytes required')
    return value

def finite(value):
    if type(value)is not float or not math.isfinite(value)or abs(value)>NUMERIC_ABS_BOUND:raise ValueError('Finite exact DBL abs<=2**40 required')
    return value

def carrier(value):
    if type(value)is not tuple or len(value)!=FIELD_COUNT or any(type(v)is not float for v in value):raise TypeError('Decoded tuple33DBL required')

def dps_carrier(value):
    if type(value)is not tuple or len(value)!=29 or any(type(v)is not bool for v in value):raise TypeError('Decoded tuple29Boolean DPS required')

def error(value):
    if type(value)is not ErrorValue or type(value.status)is not bool or type(value.code)is not int or not -(2**31)<=value.code<2**31:raise TypeError('Decoded Error Boolean/I32/bytes required')
    bytes_value(value.source_bytes)

def controls(value):
    if type(value)is not tuple or len(value)>64:raise TypeError('Explicit bounded tuple of opaque control references required')

def index_array(array,index):
    controls(array)
    if type(index)is not int or not 0<=index<len(array):raise ValueError('Only in-bounds signed-I32 array index qualified; native defaults unresolved')
    return array[index]

def property_return(value,value_keys):
    if type(value)is not PropertyReturn:raise TypeError('Explicit property return required')
    error(value.error_out);exact(value.values,value_keys)

def concatenate_bytes(a,b):
    bytes_value(a);bytes_value(b);return a+b

def project_event_18780(event_return,local_reads,native_boundaries,intrinsic_boundaries,literal_inputs,completed_sinks=None):
    """Direct guarded structures, not original/native VI execution."""
    if type(event_return)is not EventDataReturn or type(native_boundaries)is not NativeBoundaries or type(intrinsic_boundaries)is not IntrinsicBoundaries:raise TypeError('Explicit event/native/intrinsic boundary records required')
    exact(local_reads,READ_UIDS);exact(literal_inputs,LITERAL_UIDS);exact(native_boundaries.unwired_inputs,('40566',));exact(native_boundaries.border_values,BORDER_UIDS)
    dps_carrier(local_reads['19687']);busy=any(local_reads['19687'])
    def read(uid,value,i=None):return LocalRead(uid,*LOCAL_IDENTITIES[uid],data=value,loop_iteration=i)
    def assignment(uid,value,i=None):return LocalAssignment(uid,*LOCAL_IDENTITIES[uid],data=value,loop_iteration=i)
    reads=[read('19687',local_reads['19687'])];assignments=[];leaves=[];indices=[];updates=[];iterations=[];frames=[];literal_observations={}
    differences=None;candidate=None;loop_error=None;initial=None;formatted=None;returned_error=None;selector=None;message=None;count=0
    def leaf(uid,i,inputs,outputs,scope='supplied_native_leaf'):
        leaves.append(LeafObservation(uid,i,inputs,outputs,scope))
    if busy:frames.append(('19705','22679',True))
    else:
        frames.append(('19705','19879',False));carrier(event_return.old_value);carrier(event_return.new_value)
        differences=tuple(finite(finite(old)-finite(new))for old,new in zip(event_return.old_value,event_return.new_value));count=len(differences)
        if count!=FIELD_COUNT:raise ValueError('Only exact source33-field numeric cluster domain')
        threshold=finite(literal_inputs['49984']);literal_observations['49984']=threshold
        for value in(native_boundaries.loop_returns,local_reads['19774'],native_boundaries.unwired_inputs['40566'],intrinsic_boundaries.unwired_false_case_errors):
            if type(value)is not tuple or len(value)!=count:raise TypeError('Exactly33 independently supplied iteration observations required')
        frames.append(('35757','35778',0));iteration_errors=[]
        for i,difference in enumerate(differences):
            increment=i+1;changed=difference!=threshold;selected='28797'if changed else'28769'
            if not changed:
                out=intrinsic_boundaries.unwired_false_case_errors[i];error(out)
            else:
                r=native_boundaries.loop_returns[i]
                if type(r)is not LoopReturn:raise TypeError('Selected loop native returns required')
                property_return(r.cluster_property,('40574',));property_return(r.color_property,())
                if type(r.cast)is not CastReturn or type(r.writer)is not WriterReturn:raise TypeError('Selected cast/PSP returns required')
                error(r.cast.error_out);error(r.writer.error_out);unwired=native_boundaries.unwired_inputs['40566'][i];error(unwired)
                refs=r.cluster_property.values['40574'];element=index_array(refs,i)
                indices.append(IndexProjection('40586',i,'40588','41540','40591',refs,i,element))
                value=local_reads['19774'][i];carrier(value);reads.append(read('19774',value,i))
                data=list(value);data[32]=float(increment);data=tuple(data)
                updates.append(('23628','23717',32,(32,),float(increment),i))
                assignments.extend((assignment('21948',i,i),assignment('35923',data,i),assignment('37769',data,i)))
                leaf('20125',i,{}, {'41925':r.control_reference},'supplied_control_reference_no_bank_slot')
                leaf('40540',i,{'40548':r.control_reference,'40566':unwired},{'40552':r.cluster_property.reference_out,'40570':r.cluster_property.error_out,'40574':refs})
                leaf('41806',i,{'41814':literal_inputs['41829'],'41817':element,'41821':r.cluster_property.error_out},{'41808':r.cast.reference_out,'41811':r.cast.error_out})
                leaf('41566',i,{'41573':r.cast.reference_out,'41584':r.cast.error_out,'41597':LOOP_COLOR},{'41579':r.color_property.reference_out,'41588':r.color_property.error_out})
                leaf('20132',i,{'20134':literal_inputs['19972'],'20141':r.color_property.error_out,'20151':data},{'20138':r.writer.reference_out,'20148':r.writer.error_out})
                literal_observations['41829']=literal_inputs['41829'];literal_observations['19972']=literal_inputs['19972'];out=r.writer.error_out
            iteration_errors.append(out);iterations.append(LoopIteration(i,increment,difference,threshold,changed,selected,out))
        # This candidate is a private ordered projection, never the original
        # lpTun mode/default proof. The consumed output is explicitly supplied.
        candidate=iteration_errors[-1];loop_error=intrinsic_boundaries.loop_error_output;error(loop_error)
        frames.append(('35757','28430',1))
        if type(native_boundaries.wait_return)is not WaitReturn:raise TypeError('Supplied Wait return required')
        leaf('35801',None,{'37387':WAIT_MS},{'37383':native_boundaries.wait_return.timer_value})
        frames.append(('35757','36545',2));r=native_boundaries.final_return
        if type(r)is not FinalReturn:raise TypeError('Supplied final native returns required')
        property_return(r.cluster_property,('40279',));property_return(r.numeric_property,('55971','57536'))
        if type(r.cast)is not CastReturn or type(r.variant)is not VariantReturn or type(r.formatter)is not FormatterReturn:raise TypeError('Typed final cast/variant/format returns required')
        error(r.cast.error_out);error(r.variant.error_out);error(r.formatter.error_out)
        co=local_reads['8733']
        if type(co)is not int or not 0<=co<2**31:raise ValueError('Supplied COFlash U32 restricted to nonnegative signed-I32 intersection')
        refs=r.cluster_property.values['40279'];element=index_array(refs,co);indices.append(IndexProjection('40313',None,'40324','40350','40336',refs,co,element));reads.append(read('8733',co))
        label=bytes_value(r.numeric_property.values['55971']);variant=r.numeric_property.values['57536'];example=finite(literal_inputs['47580']);data=finite(r.variant.data)
        initial=concatenate_bytes(INITIAL_PREFIX,label);formatted=bytes_value(r.formatter.formatted_bytes);returned_error=r.formatter.error_out
        selector=intrinsic_boundaries.error_case_selector
        if type(selector)is not bool:raise TypeError('Supplied hypothetical ErrorCluster Case Boolean required')
        frames.append(('20154','20179'if selector else'20168',selector))
        if selector:message=concatenate_bytes(ERROR_PREFIX,returned_error.source_bytes);assignments.append(assignment('20535',message))
        else:message=formatted;assignments.append(assignment('22126',message))
        leaf('40447',None,{}, {'40450':r.control_reference},'supplied_control_reference_no_bank_slot')
        leaf('40236',None,{'40239':r.control_reference,'40252':loop_error},{'40245':r.cluster_property.reference_out,'40259':r.cluster_property.error_out,'40279':refs})
        leaf('40404',None,{'40412':literal_inputs['40424'],'40415':element,'40418':r.cluster_property.error_out},{'40406':r.cast.reference_out,'40409':r.cast.error_out})
        leaf('40371',None,{'40373':r.cast.reference_out,'40379':r.cast.error_out,'40385':FINAL_COLOR},{'40376':r.numeric_property.reference_out,'40382':r.numeric_property.error_out,'55971':label,'57536':variant})
        leaf('62591',None,{'62606':r.numeric_property.error_out,'62630':variant,'62638':example},{'62617':r.variant.error_out,'62646':data})
        leaf('22086',None,{'49809':FORMAT_BYTES,'49817':initial,'53676':r.variant.error_out,'53682':data},{'53673':formatted,'53679':returned_error},'supplied_identified_formatter_leaf_no_format_or_locale_equivalence')
        literal_observations['40424']=literal_inputs['40424'];literal_observations['47580']=example
    active={(a.node_uid,a.loop_iteration)for a in assignments}|{(a.node_uid,a.loop_iteration)for a in leaves}
    if completed_sinks is not None:
        if type(completed_sinks)is not tuple or any(type(p)is not tuple or len(p)!=2 or type(p[0])is not str or(p[1]is not None and type(p[1])is not int)for p in completed_sinks):raise TypeError('Completion tuple(nodeUID,iteration or None) pairs required')
        if len(set(completed_sinks))!=len(completed_sinks)or any(p not in active for p in completed_sinks):raise ValueError('Unique completion subset of selected source sink observations required')
    return Event18780Slice(event_return,busy,tuple(frames),differences,count,tuple(iterations),tuple(reads),tuple(updates),tuple(assignments),tuple(leaves),tuple(indices),candidate,loop_error,initial,formatted,returned_error,selector,message,completed_sinks,literal_observations)

def _json_tree(value):
    budget=[32768]
    def visit(v,depth):
        budget[0]-=1
        if budget[0]<0 or depth>14:raise ValueError('JSON node/depth bound exceeded')
        t=type(v)
        if v is None or t is bool:return
        if t is int:
            if not -(2**63)<=v<2**64:raise ValueError('JSON integer bound exceeded')
            return
        if t is float:
            if not math.isfinite(v):raise ValueError('Finite JSON numbers required')
            return
        if t is str:
            if len(v)>8192:raise ValueError('JSON string bound exceeded')
            return
        if t is list:
            if len(v)>64:raise ValueError('JSON list bound exceeded')
            for x in v:visit(x,depth+1)
            return
        if t is dict:
            if len(v)>64 or any(type(k)is not str or len(k)>256 for k in v):raise ValueError('JSON object bound exceeded')
            for x in v.values():visit(x,depth+1)
            return
        raise TypeError('Only inert exact JSON values required')
    visit(value,0)

def _bytes_json(raw):
    if type(raw)is not str or len(raw)>8192 or len(raw)%2 or any(c not in'0123456789ABCDEF'for c in raw):raise ValueError('Canonical uppercase bounded byte hex required')
    return bytes.fromhex(raw)

def _error_json(raw):
    exact(raw,('status','code','source_hex'));value=ErrorValue(raw['status'],raw['code'],_bytes_json(raw['source_hex']));error(value);return value

def _property_json(uid,raw):
    ports={'40540':('40552','40570',('40574',)),'41566':('41579','41588',()),'40236':('40245','40259',('40279',)),'40371':('40376','40382',('55971','57536'))}
    ref,err,keys=ports[uid];exact(raw,(ref,err)+keys);values={u:raw[u]for u in keys}
    for key in('40574','40279'):
        if key in values:
            if type(values[key])is not list:raise TypeError('JSON control-reference array required')
            values[key]=tuple(values[key])
    if'55971'in values:values['55971']=_bytes_json(values['55971'])
    return PropertyReturn(raw[ref],_error_json(raw[err]),values)

def replay_saved_sup_event_18780(payload):
    _json_tree(payload);exact(payload,('source_id','source_version','event_uid','frame_uid','event_returns','local_reads','loop_returns','final_returns','wait_return','unwired_inputs','border_inputs','literal_inputs','intrinsic_outputs','completed_sinks'))
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('Exact original source/version/event/frame required')
    exact(payload['event_returns'],('19499',));events=payload['event_returns']['19499'];exact(events,('19506','19613','19667','19672','19675','19678'))
    exact(payload['local_reads'],READ_UIDS);reads=dict(payload['local_reads'])
    if type(reads['19687'])is not list:raise TypeError('JSON DPS29 list required')
    reads['19687']=tuple(reads['19687']);dps_carrier(reads['19687']);busy=any(reads['19687'])
    old,new=events['19675'],events['19678'];literal_inputs=dict(payload['literal_inputs']);exact(literal_inputs,LITERAL_UIDS)
    exact(payload['intrinsic_outputs'],('29467','29296','20154'));intrinsic=payload['intrinsic_outputs'];exact(payload['unwired_inputs'],('40566',));unwired=dict(payload['unwired_inputs'])
    loops=payload['loop_returns'];final=payload['final_returns'];wait=payload['wait_return'];false_errors=intrinsic['29467'];loop_error=intrinsic['29296']
    if not busy:
        if type(old)is not list or type(new)is not list:raise TypeError('JSON Old/New33DBL lists required')
        old,new=tuple(old),tuple(new);carrier(old);carrier(new)
        threshold=finite(literal_inputs['49984'])
        for a in(loops,reads['19774'],unwired['40566'],false_errors):
            if type(a)is not list or len(a)!=FIELD_COUNT:raise TypeError('JSON33 iteration observations required')
        loops=list(loops);readrows=list(reads['19774']);unwiredrows=list(unwired['40566']);false=list(false_errors)
        for i,(x,y)in enumerate(zip(old,new)):
            changed=finite(finite(x)-finite(y))!=threshold
            if not changed:false[i]=_error_json(false[i])
            else:
                raw=loops[i];exact(raw,('20125','40540','41806','41566','20132'))
                exact(raw['20125'],('41925',));exact(raw['41806'],('41808','41811'));exact(raw['20132'],('20138','20148'))
                loops[i]=LoopReturn(raw['20125']['41925'],_property_json('40540',raw['40540']),CastReturn(raw['41806']['41808'],_error_json(raw['41806']['41811'])),_property_json('41566',raw['41566']),WriterReturn(raw['20132']['20138'],_error_json(raw['20132']['20148'])))
                if type(readrows[i])is not list:raise TypeError('Selected JSON PageSync33DBL carrier list required')
                readrows[i]=tuple(readrows[i]);unwiredrows[i]=_error_json(unwiredrows[i])
        loops=tuple(loops);reads['19774']=tuple(readrows);unwired['40566']=tuple(unwiredrows);false_errors=tuple(false);loop_error=_error_json(loop_error)
        exact(final,('40447','40236','40404','40371','62591','22086'));exact(final['40447'],('40450',));exact(final['40404'],('40406','40409'));exact(final['62591'],('62617','62646'));exact(final['22086'],('53673','53679'))
        final=FinalReturn(final['40447']['40450'],_property_json('40236',final['40236']),CastReturn(final['40404']['40406'],_error_json(final['40404']['40409'])),_property_json('40371',final['40371']),VariantReturn(_error_json(final['62591']['62617']),final['62591']['62646']),FormatterReturn(_error_json(final['22086']['53679']),_bytes_json(final['22086']['53673'])))
        exact(wait,('37383',));wait=WaitReturn(wait['37383'])
    event=EventDataReturn(events['19613'],events['19667'],events['19672'],old,new,events['19506'])
    completion=payload['completed_sinks']
    if completion is not None:
        if type(completion)is not list or any(type(p)is not list or len(p)!=2 for p in completion):raise TypeError('JSON completion pair list or null required')
        completion=tuple(tuple(p)for p in completion)
    result=project_event_18780(event,reads,NativeBoundaries(loops,final,wait,unwired,payload['border_inputs']),IntrinsicBoundaries(false_errors,loop_error,intrinsic['20154']),literal_inputs,completion)
    def data(value):
        if type(value)is ErrorValue:return dict(status=value.status,code=value.code,source_hex=hex_bytes(value.source_bytes))
        if type(value)is bytes:return dict(bytes_hex=hex_bytes(value))
        if type(value)is tuple:return[data(v)for v in value]
        if type(value)is dict:return{k:data(v)for k,v in value.items()}
        return value
    return dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,saved_caption=SAVED_CAPTION,dps_any=result.dps_any,event_returns=payload['event_returns'],
        differences=data(result.differences),iteration_count=result.iteration_count,selected_frames=[list(v)for v in result.selected_frames],
        iterations=[dict(index=r.index,increment=r.increment,difference=r.difference,comparison_literal=r.comparison_literal,changed=r.changed,selected_frame=r.selected_frame,supplied_or_returned_error=data(r.supplied_or_returned_error))for r in result.iterations],
        local_reads=[dict(node_uid=r.node_uid,control_id=r.control_id,saved_param_index=r.saved_param_index,saved_bank_uid=r.saved_bank_uid,data=data(r.data),loop_iteration=r.loop_iteration)for r in result.local_reads],
        local_assignments=[dict(node_uid=a.node_uid,control_id=a.control_id,saved_param_index=a.saved_param_index,saved_bank_uid=a.saved_bank_uid,data=data(a.data),loop_iteration=a.loop_iteration)for a in result.local_assignments],
        field_updates=[dict(node_uid=u,terminal_uid=t,raw_flattened_field_index=i,descriptor_projection_ordinal=i,typed_position_path=list(p),value=v,loop_iteration=j)for u,t,i,p,v,j in result.field_updates],
        leaf_observations=[dict(node_uid=a.node_uid,loop_iteration=a.loop_iteration,inputs=data(a.inputs),supplied_outputs=data(a.supplied_outputs),intrinsic_scope=a.intrinsic_scope)for a in result.leaf_observations],
        index_projections=[dict(node_uid=a.node_uid,loop_iteration=a.loop_iteration,array_terminal_uid=a.array_terminal_uid,index_terminal_uid=a.index_terminal_uid,output_terminal_uid=a.output_terminal_uid,index=a.index,value=data(a.value))for a in result.index_projections],
        loop_error_candidate=data(result.loop_error_candidate),supplied_loop_error_output=data(result.supplied_loop_error_output),loop_error_candidate_is_native_projection=False,
        initial_string_hex=None if result.initial_string is None else hex_bytes(result.initial_string),formatted_string_hex=None if result.formatted_string is None else hex_bytes(result.formatted_string),returned_error=data(result.returned_error),error_case_selector=result.error_case_selector,message_hex=None if result.message_bytes is None else hex_bytes(result.message_bytes),
        literal_observations=data(result.literal_observations),completed_sinks=None if completion is None else[list(p)for p in completion],
        completion_observation_semantics='caller_pair_subset_reported_order_not_source_feasible_schedule_or_prefix',native_literal_storage_decode_qualified=False,
        null_model_terminal20047_restored=False,source_alias_type20047_is_native_default=False,control_reference_constants_are_local_bank_reads=False,
        source_execution=False,native_execution=False,PSP_execution=False,hardware_execution=False,native_float_bitwise_equivalence=False,native_coercion_qualified=False,native_reference_decoding_qualified=False,
        native_error_selector_projection_qualified=False,native_loop_output_policy_qualified=False,native_false_case_default_qualified=False,native_formatting_qualified=False,native_variant_conversion_qualified=False,
        native_defaults_qualified=False,unwired_native_defaults_qualified=False,units_qualified=False,UI_permitted_values_qualified=False,event_queue_selection_qualified=False,atomic_snapshot_qualified=False,fanout_order_qualified=False,
        writer_success_gates_local_assignment=False,native_primitive_semantics_qualified=False,whole_body_qualified=False,whole_frame_equivalence=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        qualification_scope='Direct33-field differences/loop/comparisons/increment/index/carriers/Case/concat with narrowly identified supplied native, literal and intrinsic output boundaries')
