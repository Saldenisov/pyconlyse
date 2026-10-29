"""Bounded original [20] Voie deviee event33463, no native/source execution.

Direct9x11 comparisons, nine mask iterations, max/matched Case arms, index
subcases, Select/arithmetic/interior range, field/reset copies, byte concat,
four sequence frames and independent read/writer/handler source edges.
Only identified leaf outputs and narrow storage/selector/tie policy supplied.
Caller completion observations are not feasible source schedules.
"""
from collections import namedtuple
import math,struct
SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909';FRAME_UID='33463';SAVED_CAPTION='[20] "Voie d\u00e9vi\u00e9e": Value Change'
BOOL_FIELDS=(0,1,2,3,4,7,8,9,10);DBL_FIELDS=(5,6)
MASK_DOMAIN=(0,1,16,128,256,512,1024);MASK_BITS=1937;ABS_BOUND=float(2**40)
READ_UIDS=('46585','46632','46671','46864','46903','46942','46981')
LITERAL_UIDS=('33526','33630','46410','46792','46810','46828','46846')
BORDER_UIDS=('33471','33474','33477','40510')
LOCAL_IDENTITIES={'46585':('83278',46,'83276'),'46632':('67290',22,'67288'),'46665':('67290',22,'67288'),'46671':('67171',23,'67169'),'46698':('67171',23,'67169'),'46864':('67290',22,'67288'),'46903':('67171',23,'67169'),'46942':('67056',24,'67054'),'46981':('66941',25,'66939'),'48604':('61053',184,'61051')}
ERROR_PREFIX=bytes.fromhex('45727265757220646520636F6D6D616E64652064616E73206C6520636C75737465722022566F69652064E97669E965222E20')
FIELD_ROWS={'34005':(('34011',6,(6,)),('34021',1,(1,)),('34024',2,(2,)),('34027',3,(3,)),('34030',4,(4,)),('34033',None,(0,)),('34036',5,(5,))),
    '34040':(('34046',6,(6,)),('34049',1,(1,)),('34052',2,(2,)),('34055',3,(3,)),('34058',4,(4,)),('34061',None,(0,)),('34064',5,(5,)),('34067',7,(7,)),('34070',8,(8,)),('34073',9,(9,)),('34076',10,(10,))),
    '46593':(('46598',54,(4,5)),('46601',66,(5,5)),('46604',102,(8,5)),('46607',90,(7,5)),('46610',78,(6,5)),('46613',6,(0,5)),('46616',18,(1,5)),('46619',30,(2,5)),('46622',42,(3,5))),
    '46640':(('46646',6,(6,)),('46649',7,(7,)),('46652',9,(9,)),('27884',8,(8,))),
    '46679':(('46685',9,(9,)),('46688',6,(6,)),('46691',7,(7,)),('46694',3,(3,)),('32226',4,(4,))), '48583':(('48588',2,(2,)),)}
# Exact two selected declarations omit i. Descriptor equality yields ordinal0;
# this is separate from original raw absence and no missing-index default.
ABSENT_I_DESCRIPTOR_ORDINALS={'34033':0,'34061':0}
# Select slot1=false value; slot3=true value. Every value is saved8byte DBL.
ARITH_ROWS={
 (128,0):('34331','34648','34702','34716','subtract','34728','3FB999999999999A','3FF0000000000000','C030000000000000','4030000000000000'),
 (128,1):('34331','34779','34834','34848','subtract','34859','3FB999999999999A','3FF0000000000000','C014000000000000','4014000000000000'),
 (256,0):('34950','35240','35294','35308','subtract','35319','3F847AE147AE147B','3FB999999999999A','C030000000000000','4030000000000000'),
 (256,1):('34950','35366','35420','35455','subtract','35497','3F847AE147AE147B','3FB999999999999A','C014000000000000','4014000000000000'),
 (512,0):('35756','45491','45545','45576','add','45559','3F847AE147AE147B','3FB999999999999A','C030000000000000','4030000000000000'),
 (512,1):('35756','45617','45671','45702','add','45685','3F847AE147AE147B','3FB999999999999A','C014000000000000','4014000000000000'),
 (1024,0):('45787','46076','46130','46161','add','46144','3FB999999999999A','3FF0000000000000','C030000000000000','4030000000000000'),
 (1024,1):('45787','46202','46256','46287','add','46270','3FB999999999999A','3FF0000000000000','C014000000000000','4014000000000000')}
MASK_FRAMES={0:'34244',1:'34271',16:'34298',128:'34325',256:'34944',512:'35750',1024:'45781'}
WRITER_ROWS=(('46864','47022','46792','47024','47027','47030','47033','47036','46870',('46879','46882','46885','46897'),'46900',('46873','46876','46888','46891','46894')),
 ('46903','47039','46810','47041','47044','47047','47050','47053','46909',('46918','46921','46924','46936'),'46939',('46912','46915','46927','46930','46933')),
 ('46942','47056','46828','47058','47061','47064','47067','47070','46948',('46957','46960','46963','46975'),'46978',('46951','46954','46966','46969','46972')),
 ('46981','47073','46846','47075','47078','47081','47084','47087','46989',('46998','47001','47004','47016'),'47019',('46992','46995','47007','47010','47013')))
UNWIRED_UIDS=('33919',)+tuple(r[5]for r in WRITER_ROWS)+tuple(u for r in WRITER_ROWS for u in r[9])
EventDataReturn=namedtuple('EventDataReturn','event_type time control_reference old_value new_value aggregate_effective_value')
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
PropertyReturn=namedtuple('PropertyReturn','reference_out error_out values')
CastReturn=namedtuple('CastReturn','reference_out error_out')
VariantReturn=namedtuple('VariantReturn','error_out data')
WriterReturn=namedtuple('WriterReturn','reference_out error_out')
CalleeReturn=namedtuple('CalleeReturn','outputs')
WaitReturn=namedtuple('WaitReturn','timer_value')
NativeBoundaries=namedtuple('NativeBoundaries','control_reference cast cluster_property current_property variant updated_property wait70 wait100 writers handlers unwired_inputs border_values')
IntrinsicBoundaries=namedtuple('IntrinsicBoundaries','argmax_tie_index error_case_selector')
LocalRead=namedtuple('LocalRead','node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment=namedtuple('LocalAssignment','node_uid control_id saved_param_index saved_bank_uid data')
LeafObservation=namedtuple('LeafObservation','node_uid inputs supplied_outputs scope')
FieldProjection=namedtuple('FieldProjection','node_uid terminal_uid raw_flattened_field_index typed_position_path value')
Event33463Slice=namedtuple('Event33463Slice','event_return comparisons masks max_mask selected_index max_index_supplied tied_indices selected_frames numeric_trace updated_cluster local_reads local_assignments leaf_observations field_projections error_case_selector error_message completion_observations')
def exact(v,keys):
    if type(v)is not dict or set(v)!=set(keys):raise ValueError('Exact frame33463 field keys required')
def finite(v):
    if type(v)is not float or not math.isfinite(v)or abs(v)>ABS_BOUND:raise ValueError('Finite exactDBL abs<=2**40 required')
    return v
def byte_string(v):
    if type(v)is not bytes or len(v)>4096:raise TypeError('Exact bounded byte string required')
    return v
def hex_bytes(v):
    # Supplied byteinputs<=4096; direct concatenation adds exact50byte prefix.
    if type(v)is not bytes or len(v)>4096+len(ERROR_PREFIX):raise TypeError('Exact bounded generated byte string required')
    return ''.join('{:02X}'.format(x)for x in v)
def error(v):
    if type(v)is not ErrorValue or type(v.status)is not bool or type(v.code)is not int or not -(2**31)<=v.code<2**31:raise TypeError('Explicit Error Boolean/I32/bytes required')
    byte_string(v.source_bytes)
def subcluster(v):
    if type(v)is not tuple or len(v)!=11 or any(type(v[i])is not bool for i in BOOL_FIELDS)or any(type(v[i])is not float for i in DBL_FIELDS):raise TypeError('Decoded5Boolean2DBL4Boolean cluster11 required')
def root_cluster(v):
    if type(v)is not tuple or len(v)!=9:raise TypeError('Decoded9-subcluster root required')
    for child in v:subcluster(child)
def numeric_carrier(v):
    if type(v)is not tuple or len(v)!=10 or any(type(x)is not float for x in v):raise TypeError('Decoded tuple10DBL carrier required')
def prop(v,keys):
    if type(v)is not PropertyReturn:raise TypeError('Explicit native property return required')
    error(v.error_out);exact(v.values,keys)
def saved_double(h):return struct.unpack('>d',bytes.fromhex(h))[0]
def field(v,path):
    for i in path:v=v[i]
    return v
def project_event_33463(event_return,local_reads,native_boundaries,intrinsic_boundaries,literal_inputs,completed_sinks=None):
    if type(event_return)is not EventDataReturn or type(native_boundaries)is not NativeBoundaries or type(intrinsic_boundaries)is not IntrinsicBoundaries:raise TypeError('Explicit source event/native/intrinsic records required')
    exact(local_reads,READ_UIDS);exact(literal_inputs,LITERAL_UIDS);exact(native_boundaries.unwired_inputs,UNWIRED_UIDS);exact(native_boundaries.border_values,BORDER_UIDS)
    root_cluster(event_return.old_value);root_cluster(event_return.new_value);comparisons=[];masks=[]
    # Original output shape9x11Boolean independently follows typed ports.
    for old,new in zip(event_return.old_value,event_return.new_value):
        row=tuple((finite(a)!=finite(b))if i in DBL_FIELDS else a!=b for i,(a,b)in enumerate(zip(old,new)))
        comparisons.append(row);masks.append(sum(1<<i for i,b in enumerate(row)if b)&MASK_BITS)
    maximum=max(masks);ties=tuple(i for i,v in enumerate(masks)if v==maximum);supplied=False
    if len(ties)==1:selected=ties[0]
    else:
        selected=intrinsic_boundaries.argmax_tie_index
        if selected is None:raise ValueError('Original max-index tie policy unresolved; unique maximum required by default')
        if type(selected)is not int or selected not in ties:raise ValueError('Hypothetical supplied max-index33835 must belong to exact argmax set')
        supplied=True
    if maximum not in MASK_DOMAIN:raise ValueError('Only saved matched mask0/1/16/128/256/512/1024; composite/default native policy unresolved')
    r=native_boundaries;prop(r.cluster_property,('33889',));prop(r.current_property,('33980',));prop(r.updated_property,())
    if type(r.cast)is not CastReturn or type(r.variant)is not VariantReturn:raise TypeError('Explicit native class/variant returns required')
    error(r.cast.error_out);error(r.variant.error_out);error(r.unwired_inputs['33919']);subcluster(r.variant.data);subcluster(literal_inputs['33526'])
    if type(literal_inputs['46410'])is not bool:raise TypeError('Explicit hypothetical decoded storedBoolean46410 required')
    refs=r.cluster_property.values['33889']
    if type(refs)is not tuple or len(refs)>64 or not selected<len(refs):raise ValueError('Only inbounds explicit reference array index qualified')
    reference=refs[selected];reads=[];assignments=[];leaves=[];fields=[];trace=[];frames=[('33504','33520',0),('34080',MASK_FRAMES[maximum],maximum)]
    def read(uid,data):reads.append(LocalRead(uid,*LOCAL_IDENTITIES[uid],data=data));return data
    def assign(uid,data):assignments.append(LocalAssignment(uid,*LOCAL_IDENTITIES[uid],data=data))
    def leaf(uid,inputs,outputs,scope='supplied_identified_native_leaf'):leaves.append(LeafObservation(uid,inputs,outputs,scope))
    current=r.variant.data
    for uid,i,path in FIELD_ROWS['34005']:fields.append(FieldProjection('34005',uid,i,path,field(current,path)))
    value=finite(current[5])
    if maximum>=128:
        family=0 if selected in(0,1,2,3,6)else 1
        case,diagram,select_uid,arith_uid,operation,range_uid,fhex,thex,lhex,uhex=ARITH_ROWS[(maximum,family)]
        step=saved_double(thex if current[4]else fhex);result=finite(value-step if operation=='subtract'else value+step);lower=saved_double(lhex);upper=saved_double(uhex)
        if not lower<result<upper:raise ValueError('Coerce native mode unresolved: only strict finite lower<x<upper; endpoints/outside refuse')
        frames.append((case,diagram,selected));trace.append(dict(select_uid=select_uid,selector=current[4],slot1_false=saved_double(fhex),slot3_true=saved_double(thex),selected_step=step,arithmetic_uid=arith_uid,operation=operation,slot1=step,slot2=value,result=result,range_uid=range_uid,lower=lower,upper=upper,unused_Boolean_output_evaluated=False));value=result
    frames.append(('46451','46392',0))
    if type(r.wait70)is not WaitReturn or type(r.wait100)is not WaitReturn:raise TypeError('Explicit native Wait outputs required')
    leaf('46420',{'46425':70},{'46422':r.wait70.timer_value},'supplied_Wait_no_timing_or_completion_semantics')
    data=list(literal_inputs['33526'])
    for uid,i,path in FIELD_ROWS['34040']:
        pos=path[0];v=value if pos==5 else literal_inputs['46410']if pos in(7,8,9,10)else current[pos];data[pos]=v;fields.append(FieldProjection('34040',uid,i,path,v))
    updated=tuple(data);selector=intrinsic_boundaries.error_case_selector
    if type(selector)is not bool:raise TypeError('Supplied hypothetical ErrorCluster Case selector required')
    frames.append(('48544','48564'if selector else'48557',selector));message=None
    if selector:
        message=ERROR_PREFIX+r.updated_property.error_out.source_bytes;fields.append(FieldProjection('48583','48588',2,(2,),r.updated_property.error_out.source_bytes));assign('48604',message)
    leaf('33897',{}, {'33900':r.control_reference},'supplied_ctlRefConst_not_bank_read')
    leaf('33905',{'33913':literal_inputs['33630'],'33916':r.control_reference,'33919':r.unwired_inputs['33919']},{'33907':r.cast.reference_out,'33910':r.cast.error_out})
    leaf('33859',{'33865':r.cast.reference_out,'33881':r.cast.error_out},{'33873':r.cluster_property.reference_out,'33886':r.cluster_property.error_out,'33889':refs})
    leaf('33966',{'33968':reference,'33974':r.cluster_property.error_out},{'33971':r.current_property.reference_out,'33977':r.current_property.error_out,'33980':r.current_property.values['33980']})
    leaf('65169',{'65173':r.current_property.error_out,'65181':r.current_property.values['33980'],'65185':literal_inputs['33526']},{'65177':r.variant.error_out,'65191':current})
    leaf('33935',{'33937':reference,'33943':r.variant.error_out,'33949':updated},{'33940':r.updated_property.reference_out,'33946':r.updated_property.error_out},'supplied_native_property_return_pure_cluster_carrier_not_native_Variant_coercion')
    gate=maximum>=128;frames.extend((('33504','46558',1),('46564','46579'if gate else'46573',gate)))
    if gate:
        voie=read('46585',local_reads['46585']);root_cluster(voie)
        for uid,i,path in FIELD_ROWS['46593']:fields.append(FieldProjection('46593',uid,i,path,finite(field(voie,path))))
        for mux,read_uid,write_uid,source_paths in [('46640','46632','46665',((4,5),(5,5),(8,5),(7,5))),('46679','46671','46698',((6,5),(0,5),(1,5),(2,5),(3,5)))]:
            original=read(read_uid,local_reads[read_uid]);numeric_carrier(original);changed=list(original)
            for (uid,i,path),source_path in zip(FIELD_ROWS[mux],source_paths):
                v=finite(field(voie,source_path));changed[path[0]]=v;fields.append(FieldProjection(mux,uid,i,path,v))
            assign(write_uid,tuple(changed))
    frames.append(('33504','46786',2));exact(r.writers,[row[1]for row in WRITER_ROWS]);exact(r.handlers,[row[8]for row in WRITER_ROWS])
    for read_uid,writer_uid,lit,ref_in,ref_out,err_in,err_out,data_in,handler_uid,handler_unwired,handler_error_in,handler_out in WRITER_ROWS:
        data=read(read_uid,local_reads[read_uid]);numeric_carrier(data);wr=r.writers[writer_uid];hr=r.handlers[handler_uid]
        if type(wr)is not WriterReturn or type(hr)is not CalleeReturn:raise TypeError('Explicit writer and identified callee returns required')
        error(wr.error_out);error(r.unwired_inputs[err_in]);exact(hr.outputs,handler_out)
        # Unwired input policies are supplied; handler outputs are unused and
        # opaque. No same-name dependency-body identity/equivalence inferred.
        inputs={u:r.unwired_inputs[u]for u in handler_unwired};inputs[handler_error_in]=wr.error_out
        leaf(writer_uid,{ref_in:literal_inputs[lit],err_in:r.unwired_inputs[err_in],data_in:data},{ref_out:wr.reference_out,err_out:wr.error_out})
        leaf(handler_uid,inputs,hr.outputs,'supplied_original_iUse_leaf_not_same_name_body_proof')
    frames.append(('33504','28288',3));leaf('27840',{'27849':100},{'27846':r.wait100.timer_value},'supplied_Wait_no_timing_or_completion_semantics')
    active={a.node_uid for a in assignments}|{l.node_uid for l in leaves}
    if completed_sinks is not None:
        if type(completed_sinks)is not tuple or any(type(x)is not str for x in completed_sinks):raise TypeError('Caller active-sink UID tuple required')
        if len(set(completed_sinks))!=len(completed_sinks)or any(x not in active for x in completed_sinks):raise ValueError('Unique active caller completion observations required')
    return Event33463Slice(event_return,tuple(comparisons),tuple(masks),maximum,selected,supplied,ties,tuple(frames),tuple(trace),updated,tuple(reads),tuple(assignments),tuple(leaves),tuple(fields),selector,message,completed_sinks)

def _json_tree(v):
    budget=[32768]
    def walk(x,depth):
        budget[0]-=1
        if budget[0]<0 or depth>14:raise ValueError('Bounded JSON depth/nodes required')
        t=type(x)
        if x is None or t is bool:return
        if t is int:
            if not -(2**63)<=x<2**64:raise ValueError('JSON integer range')
        elif t is float:
            if not math.isfinite(x):raise ValueError('Finite JSON values required')
        elif t is str:
            if len(x)>8192:raise ValueError('JSON string bound')
        elif t is list:
            if len(x)>64:raise ValueError('JSON list bound')
            for y in x:walk(y,depth+1)
        elif t is dict:
            if len(x)>64 or any(type(k)is not str or len(k)>256 for k in x):raise ValueError('JSON object bound')
            for y in x.values():walk(y,depth+1)
        else:raise TypeError('Only exact inert JSON values')
    walk(v,0)
def _bytes_json(x):
    if type(x)is not str or len(x)%2 or len(x)>8192 or any(c not in'0123456789ABCDEF'for c in x):raise ValueError('Uppercase canonical byte hex required')
    return bytes.fromhex(x)
def _error_json(x):
    exact(x,('status','code','source_hex'));v=ErrorValue(x['status'],x['code'],_bytes_json(x['source_hex']));error(v);return v
def _tuple_tree(x):return tuple(_tuple_tree(y)for y in x)if type(x)is list else x
def replay_saved_sup_event_33463(payload):
    _json_tree(payload);exact(payload,('source_id','source_version','event_uid','frame_uid','event_returns','local_reads','native_returns','unwired_inputs','border_inputs','literal_inputs','intrinsic_outputs','completed_sinks'))
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('Exact source/version/event/frame required')
    exact(payload['event_returns'],('33480',));ev=payload['event_returns']['33480'];exact(ev,('33482','33485','33488','33491','33494','33497'))
    event=EventDataReturn(ev['33485'],ev['33488'],ev['33491'],_tuple_tree(ev['33494']),_tuple_tree(ev['33497']),ev['33482'])
    exact(payload['literal_inputs'],LITERAL_UIDS);literal=dict(payload['literal_inputs']);literal['33526']=_tuple_tree(literal['33526']);exact(payload['local_reads'],READ_UIDS);reads=dict(payload['local_reads'])
    # Native/property leaves always selected; optional phase2 local carrier reads
    # are decoded only after direct gate selection. Inactive values stay opaque.
    nr=payload['native_returns'];expected=('33897','33905','33859','33966','65169','33935','46420','27840')+tuple(r[1]for r in WRITER_ROWS)+tuple(r[8]for r in WRITER_ROWS);exact(nr,expected)
    def p(uid,ref,err,keys):
        raw=nr[uid];exact(raw,(ref,err)+keys);values={k:raw[k]for k in keys}
        if'33889'in values:values['33889']=_tuple_tree(values['33889'])
        return PropertyReturn(raw[ref],_error_json(raw[err]),values)
    for uid,keys in [('33897',('33900',)),('33905',('33907','33910')),('65169',('65177','65191')),('46420',('46422',)),('27840',('27846',))]:exact(nr[uid],keys)
    for u in('46864','46903','46942','46981'):reads[u]=_tuple_tree(reads[u])
    # The gate depends only on direct source Old/New comparison.
    root_cluster(event.old_value);root_cluster(event.new_value)
    gate_masks=[sum(1<<i for i,(a,b)in enumerate(zip(old,new))if a!=b)&MASK_BITS for old,new in zip(event.old_value,event.new_value)]
    if max(gate_masks)>=128:
        for u in('46585','46632','46671'):reads[u]=_tuple_tree(reads[u])
    exact(payload['unwired_inputs'],UNWIRED_UIDS);unwired=dict(payload['unwired_inputs'])
    for u in('33919',)+tuple(r[5]for r in WRITER_ROWS):unwired[u]=_error_json(unwired[u])
    writers={};handlers={}
    for row in WRITER_ROWS:
        uid=row[1];exact(nr[uid],(row[4],row[6]));writers[uid]=WriterReturn(nr[uid][row[4]],_error_json(nr[uid][row[6]]));uid=row[8];exact(nr[uid],row[11]);handlers[uid]=CalleeReturn(nr[uid])
    native=NativeBoundaries(nr['33897']['33900'],CastReturn(nr['33905']['33907'],_error_json(nr['33905']['33910'])),p('33859','33873','33886',('33889',)),p('33966','33971','33977',('33980',)),VariantReturn(_error_json(nr['65169']['65177']),_tuple_tree(nr['65169']['65191'])),p('33935','33940','33946',()),WaitReturn(nr['46420']['46422']),WaitReturn(nr['27840']['27846']),writers,handlers,unwired,payload['border_inputs'])
    intrinsic=payload['intrinsic_outputs'];exact(intrinsic,('33835','48544'))
    completion=payload['completed_sinks']
    if completion is not None:
        if type(completion)is not list:raise TypeError('JSON completion UID list or null')
        completion=tuple(completion)
    r=project_event_33463(event,reads,native,IntrinsicBoundaries(intrinsic['33835'],intrinsic['48544']),literal,completion)
    def data(v):
        if type(v)is ErrorValue:return dict(status=v.status,code=v.code,source_hex=hex_bytes(v.source_bytes))
        if type(v)is bytes:return dict(bytes_hex=hex_bytes(v))
        if type(v)is tuple:return[data(x)for x in v]
        if type(v)is dict:return{k:data(x)for k,x in v.items()}
        return v
    result=dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,saved_caption=SAVED_CAPTION,event_returns=payload['event_returns'],comparisons=data(r.comparisons),masks=data(r.masks),loop_iteration_count=9,max_mask=r.max_mask,selected_index=r.selected_index,max_index_supplied=r.max_index_supplied,tied_indices=data(r.tied_indices),selected_frames=data(r.selected_frames),numeric_trace=data(r.numeric_trace),updated_cluster=data(r.updated_cluster),
        local_reads=[dict(node_uid=a.node_uid,control_id=a.control_id,saved_param_index=a.saved_param_index,saved_bank_uid=a.saved_bank_uid,data=data(a.data))for a in r.local_reads],local_assignments=[dict(node_uid=a.node_uid,control_id=a.control_id,saved_param_index=a.saved_param_index,saved_bank_uid=a.saved_bank_uid,data=data(a.data))for a in r.local_assignments],
        leaf_observations=[dict(node_uid=a.node_uid,inputs=data(a.inputs),supplied_outputs=data(a.supplied_outputs),scope=a.scope)for a in r.leaf_observations],field_projections=[dict(node_uid=a.node_uid,terminal_uid=a.terminal_uid,raw_flattened_field_index=a.raw_flattened_field_index,descriptor_projection_ordinal=ABSENT_I_DESCRIPTOR_ORDINALS[a.terminal_uid]if a.raw_flattened_field_index is None else a.raw_flattened_field_index,typed_position_path=list(a.typed_position_path),value=data(a.value))for a in r.field_projections],error_case_selector=r.error_case_selector,error_message_hex=None if r.error_message is None else hex_bytes(r.error_message),completed_sinks=data(completion),completion_observation_semantics='caller_active_UID_subset_report_order_not_source_schedule_prefix_or_success',null_model_ports_preserved=['28333','33657','33724'],null_ports_are_caller_inputs=False,ctlRefConst33897_is_gRef_bank_read=False,
        qualification_scope='Direct bounded nine-mask original source body with identified supplied native/callee/storage/intrinsic leaves')
    for name in ['source_execution','native_execution','PSP_execution','hardware_execution','native_float_bitwise_equivalence','native_primitive_semantics_qualified','native_comparison_mode_qualified','native_tie_index_policy_qualified','native_range_mode_qualified','native_storage_serializer_qualified','native_defaults_qualified','native_reference_validity_qualified','native_variant_conversion_qualified','native_error_selector_projection_qualified','native_coercion_qualified','units_qualified','UI_permitted_values_qualified','atomic_snapshot_qualified','source_schedule_qualified','completion_feasibility_qualified','fanout_order_qualified','writer_success_gates_assignment','same_name_callee_body_equivalence','whole_body_qualified','whole_event_equivalence','whole_frame_equivalence','whole_VI_equivalence']:result[name]=False
    return result
