"""Original APP00/Event43/frame23113 direct bounded hierarchical replay.
Python3.4 stdlib. Supplied original-subVI/native leaves never execute.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='23113'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'23811': (2, 15, '5994', '23821', 32, 'booleans'),
 '23961': (3, 44, '66774', '23971', 77, 'booleans'),
 '24025': (3, 36, '71105', '24028', 29, 'booleans'),
 '24155': (4, 36, '71105', '24158', 29, 'booleans'),
 '54862': (1, 15, '5994', '54865', 32, 'booleans')}
BUNDLES={'23800': (2, '23811', '23806', '23803', (('23807', 8, True, '23782'),)),
 '23928': (3,
           '23961',
           '23940',
           '23932',
           (('23943', 32, False, '23886'), ('23952', 35, True, '23896'), ('31995', 33, False, '23886'))),
 '24001': (3, '24025', '24016', '24007', (('24017', 11, False, '23906'),)),
 '54852': (1, '54862', '54857', '54854', (('54858', 8, False, '54930'),))}
WRITES={'23740': (0, 35, '9101', '23743', None),
 '23792': (2, 15, '5994', '23796', '23800'),
 '23916': (3, 44, '66774', '23919', '23928'),
 '23980': (3, 36, '71105', '23989', '24001'),
 '54844': (1, 15, '5994', '54847', '54852')}
LEAVES={'23625': (0, 0),
 '23748': (0, None),
 '24147': (4, None),
 '24161': (4, None),
 '24178': (4, None),
 '46521': (0, 0),
 '48835': (0, 1),
 '54877': (1, None)}
LEAF_INPUTS={'23625': (('23730', 'unwired', 'opaque', None),
           ('23735', 'unwired', 'opaque', None),
           ('23757', 'unwired', 'opaque', None),
           ('23771', 'unwired', 'opaque', None),
           ('31059', 'unwired', 'opaque', None),
           ('31068', 'unwired', 'opaque', None)),
 '23748': (('23754', 'border', '23512', None),),
 '24147': (('24152', 'literal', '24067', 100),),
 '24161': (('24163', 'reference', '24129', None),
           ('24169', 'unwired', 'error', None),
           ('24175', 'read', '24155', None)),
 '24178': (('24187', 'unwired', 'opaque', None),
           ('24190', 'unwired', 'I32', None),
           ('24193', 'unwired', 'string', None),
           ('24205', 'unwired', 'U16', None),
           ('24208', 'return', '24161', '24172')),
 '46521': (('46535', 'unwired', 'opaque', None),
           ('46538', 'unwired', 'I32', None),
           ('46542', 'unwired', 'string', None),
           ('46555', 'unwired', 'U16', None),
           ('46559', 'return', '23625', '23726')),
 '48835': (('48844', 'literal', '50145', 500),),
 '54877': (('54889', 'border', '54840', None),)}
LEAF_OUTPUTS={'23625': (('23726', 'error'),),
 '23748': (('23750', 'U32'),),
 '24147': (('24149', 'U32'),),
 '24161': (('24166', 'opaque'), ('24172', 'error')),
 '24178': (('24181', 'boolean'), ('24184', 'I32'), ('24196', 'string'), ('24199', 'error'), ('24202', 'string')),
 '46521': (('46528', 'boolean'), ('46532', 'I32'), ('46545', 'string'), ('46548', 'error'), ('46552', 'string')),
 '48835': (('48841', 'U32'),),
 '54877': (('54880', 'U32'),)}
CONSUMED_OUTPUTS={'23625': ('23726',),
 '23748': (),
 '24147': (),
 '24161': ('24172',),
 '24178': (),
 '46521': (),
 '48835': (),
 '54877': ()}
REFERENCE_URIS={'24129': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}
STAGES=('23518', '54833', '23774', '23880', '24054')
NESTED_STAGES=('57312', '47864')
NESTED_CONTAINERS=('57299', '47855')
BORDER_PATH=(('wire', '24232', '24232', '23463', '23486', '24247'),
 ('paired', '23463', '23486', '23490', '23487'),
 ('wire', '23463', '23490', '23507', '23509', '24225'),
 ('paired', '23507', '23509', '23512', '23510'),
 ('wire', '23507', '23512', '23748', '23754', '23759'),
 ('paired', '23507', '23509', '54840', '23510'),
 ('wire', '23507', '54840', '54877', '54889', '54941'))
BORDER_VALUES={'23512': 150, '54840': 150}
REQUIRED=(('23740', '23748', '47864'),
 ('54862', '54852', '54844', '54877'),
 ('23811', '23800', '23792'),
 ('23961', '23928', '23916', '24025', '24001', '23980'),
 ('24155', '24161', '24178', '24147'))
NESTED_REQUIRED=(('23625', '46521'), ('48835',))
CONSTANTS=((('23694', True),),
 (('54930', False),),
 (('23782', True),),
 (('23886', False), ('23896', True), ('23906', False)),
 (('24067', 100), ('24129', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS')))
NESTED_CONSTANTS=((), (('50145', 500),))
CASE_UID='23463'
SEQUENCE_UID='23507'
NESTED_SEQUENCE_UID='57283'
EVENT_DATA_UID='23294'
TRUE_FRAME='23501'
FALSE_FRAME='23493'
NEWVAL_FACE='23447'
EVENT_INPUT_FACES=('23296',)
EVENT_UNUSED_FACES=('23299', '23363', '23386', '23438')
SEQUENCE_UNUSED_FACES=('23513', '23514', '23515')
OUTER_CONSTANT_UID='24232'
MAX_TOKENS=37
LIMITS=dict(execution_allowed=False,external_calls_executed=False,hardware_writes=False,native_runtime_equivalence=False,native_callee_equivalence=False,whole_event_equivalence=False,whole_vi_equivalence=False,native_default_qualified=False,native_ref_interpretation_qualified=False,native_task_reference_qualified=False,psp_delivery_qualified=False,wait_units_or_pulse_duration_qualified=False,snapshot_equality_qualified=False,scheduler_qualified=False,event_selection_qualified=False,event_acknowledgement_qualified=False,native_cluster_decode_qualified=False)


def _exact(value,keys,label):
    if type(value)is not dict or set(value)!=set(keys):raise ValueError(label+' requires exact fields')
def _value(mapping,key,label):
    if type(mapping)is not dict or key not in mapping:raise ValueError(label+' requires explicit source UID '+key)
    return mapping[key]
def _integer(value,lo,hi,label):
    if type(value)is not int or not lo<=value<=hi:raise TypeError(label+' requires bounded exact integer')
def _error(value):
    if type(value)is not ErrorValue or type(value.status)is not bool or type(value.source)is not str:
        raise TypeError('explicit ErrorValue(status bool, code I32, source str) required')
    _integer(value.code,-2147483648,2147483647,'error code')
def _typed(value,kind):
    if kind=='error':_error(value)
    elif kind=='I32':_integer(value,-2147483648,2147483647,kind)
    elif kind=='U16':_integer(value,0,65535,kind)
    elif kind=='U32':_integer(value,0,4294967295,kind)
    elif kind=='boolean' and type(value)is not bool:raise TypeError('explicit Boolean required')
    elif kind=='string' and type(value)is not str:raise TypeError('explicit String required')
def _bank(value,count,kind):
    if type(value)is not tuple or len(value)!=count:raise TypeError('explicit decoded tuple length'+str(count)+' required')
    if kind=='booleans' and any(type(v)is not bool for v in value):raise TypeError('exact Boolean carrier fields required')
def _binding(bindings,uid):
    r=_value(bindings,uid,'supplied reference binding');_exact(r,('constant_uid','saved_uri','native_ref'),'reference binding')
    if r['constant_uid']!=uid or r['saved_uri']!=REFERENCE_URIS[uid]:raise ValueError('matching saved constant/URI required')
    return r['native_ref']

def replay_event(new_value,schedule,*,snapshots,leaf_returns,unwired_inputs,reference_bindings):
    """Direct Case and hierarchical Sequence. Explicit inert finite tokens only.

    StageComplete uses original diagram UID; nested container UID is metadata.
    Supplied leaf completion joins are independent of Error.status/success.
    No external subVI body or native primitive is implemented or executed.
    """
    if type(new_value)is not bool:raise TypeError('explicit Boolean NewVal required')
    r=dict(source_id=SOURCE_ID,event_uid=EVENT_UID,frame_uid=FRAME_UID,source_version=SOURCE_VERSION,
        scope='SUPPLIED_ACQ_FRAME23113_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
        event_data_consumed_ports=(NEWVAL_FACE,),event_data_unconsumed_input_ports=EVENT_INPUT_FACES,event_data_unconsumed_ports=EVENT_UNUSED_FACES,
        unconsumed_sequence_input_faces=SEQUENCE_UNUSED_FACES,log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],
        completed_nested_stages=[],active_stage=None,active_nested_stage=None,pending_leaf_uids=(),remaining_node_uids=(),
        remaining_nested_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid=EVENT_DATA_UID,terminal_uid=NEWVAL_FACE,value=new_value),
        dict(kind='constant',node_uid=OUTER_CONSTANT_UID,value=150),dict(kind='case',node_uid=CASE_UID,selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>MAX_TOKENS:raise ValueError('bounded tuple of inert source tokens required')
    for path in BORDER_PATH:r['log'].append(dict(kind='border_transfer',source_path=path,value=150,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0;nested=0
    r['log'].append(dict(kind='sequence',node_uid=SEQUENCE_UID,stage_uids=STAGES))
    r['log'].append(dict(kind='nested_sequence',node_uid=NESTED_SEQUENCE_UID,parent_frame_uid=STAGES[0],diagram_uids=NESTED_STAGES,sequence_frame_container_uids=NESTED_CONTAINERS))
    def enter(i):
        for uid,v in CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS))
    def enter_nested(i):
        for uid,v in NESTED_CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v))
    def leaf_current(uid):
        if uid not in LEAVES:return False
        outer,inner=LEAVES[uid]
        return stage==outer and(inner is None or nested==inner)
    enter(0);enter_nested(0)
    for token in schedule:
        if stage==5:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            uid=token.frame_uid
            if type(uid)is not str:raise TypeError('exact saved diagram UID required')
            if uid in NESTED_STAGES:
                if stage!=0 or nested==2 or uid!=NESTED_STAGES[nested]:raise ValueError('current nested actual diagram UID required')
                if not set(NESTED_REQUIRED[nested])<=done:raise ValueError('nested frame requires all explicit supplied leaf completions')
                done.add(uid);r['completed_nested_stages'].append(uid)
                r['log'].append(dict(kind='nested_stage_complete',frame_uid=uid,sequence_frame_container_uid=NESTED_CONTAINERS[nested],sequence_uid=NESTED_SEQUENCE_UID,parent_frame_uid=STAGES[0]))
                nested+=1
                if nested<2:enter_nested(nested)
            else:
                if uid!=STAGES[stage]:raise ValueError('current main actual diagram UID required')
                if not set(REQUIRED[stage])<=done:raise ValueError('source nodes and nested/supplied leaf completions required before main join')
                r['completed_stages'].append(uid);r['log'].append(dict(kind='stage_complete',frame_uid=uid,sequence_uid=SEQUENCE_UID));stage+=1
                if stage<5:enter(stage)
            continue
        if type(token)not in(Step,LeafCall,LeafReturn)or type(token.node_uid)is not str:raise TypeError('known inert token and exact source node UID required')
        uid=token.node_uid
        if type(token)is Step:
            if uid in done:raise ValueError('source node completes only once')
            if uid in READS:
                owner,bank,target,face,count,kind=READS[uid]
                if stage!=owner:raise ValueError('local read requires current main stage')
                v=_value(snapshots,uid,'local snapshot');_bank(v,count,kind);values[uid]=v
                r['log'].append(dict(kind='local_read',node_uid=uid,terminal_uid=face,bank_index=bank,control_terminal_uid=target,value=v))
            elif uid in BUNDLES:
                owner,read,base,output,fields=BUNDLES[uid]
                if stage!=owner or read not in done:raise ValueError('bundle requires completed fresh source snapshot')
                v=list(values[read]);inputs={base:values[read]};changes=[]
                for face,index,bit,literal in fields:
                    v[index]=bit;inputs[face]=bit;changes.append(dict(terminal_uid=face,field_index=index,value=bit,constant_uid=literal))
                values[uid]=tuple(v);r['log'].append(dict(kind='bundle',node_uid=uid,input_ports=inputs,output_terminal_uid=output,assignments=changes,value=values[uid]))
            elif uid in WRITES:
                owner,bank,target,face,bundle=WRITES[uid]
                if stage!=owner or(bundle is not None and bundle not in done):raise ValueError('local write requires current saved bundle dependency')
                v=True if bundle is None else values[bundle];row=dict(kind='local_write',node_uid=uid,terminal_uid=face,bank_index=bank,control_terminal_uid=target,value=v)
                r['writes'].append(row);r['log'].append(row)
            else:raise ValueError('Step requires exact saved local or bundle')
            done.add(uid)
        elif type(token)is LeafCall:
            if not leaf_current(uid)or uid in started:raise ValueError('one current original leaf call required')
            inputs={};unwired=[]
            for face,kind,producer,port in LEAF_INPUTS[uid]:
                if kind=='unwired':
                    v=_value(unwired_inputs,face,'unwired leaf input');_typed(v,producer);unwired.append(face)
                elif kind=='return':
                    if producer not in done:raise ValueError('wired producer explicit return required')
                    v=returned[producer][port]
                elif kind=='read':
                    if producer not in done:raise ValueError('PSP leaf requires independent fresh snapshot')
                    v=values[producer]
                elif kind=='reference':v=_binding(reference_bindings,producer)
                elif kind=='border':v=BORDER_VALUES[producer]
                else:v=port
                inputs[face]=v
            started.add(uid);row=dict(kind='leaf_call',node_uid=uid,input_ports=inputs,input_port_order=tuple(x[0]for x in LEAF_INPUTS[uid]),
                unwired_input_ports=tuple(unwired),original_subvi_boundary=uid=='23625',supplied_ref_interpretation=any(p[1]=='reference'for p in LEAF_INPUTS[uid]))
            r['leaf_calls'].append(row);r['log'].append(row)
        else:
            if not leaf_current(uid)or uid not in started or uid in done:raise ValueError('one started current leaf return required')
            v=_value(leaf_returns,uid,'supplied leaf return');_exact(v,[f for f,k in LEAF_OUTPUTS[uid]],'leaf return')
            for face,kind in LEAF_OUTPUTS[uid]:_typed(v[face],kind)
            returned[uid]=v;done.add(uid);row=dict(kind='leaf_return',node_uid=uid,output_ports=v,consumed_output_ports=CONSUMED_OUTPUTS[uid],success_does_not_gate_stage=True)
            r['leaf_returns'].append(row);r['log'].append(row)
    r['active_stage']=STAGES[stage]if stage<5 else None
    r['active_nested_stage']=NESTED_STAGES[nested]if stage==0 and nested<2 else None
    r['pending_leaf_uids']=tuple(uid for uid in sorted(started)if uid not in done)
    r['remaining_node_uids']=tuple(sorted(set(REQUIRED[stage])-done))if stage<5 else()
    r['remaining_nested_node_uids']=tuple(sorted(set(NESTED_REQUIRED[nested])-done))if stage==0 and nested<2 else()
    r['selected_body_completed']=r['schedule_complete']=stage==5
    return r

def _json_error(v):
    _exact(v,('status','code','source'),'JSON error');r=ErrorValue(v['status'],v['code'],v['source']);_error(r);return r
def _json_tree(v,depth=0):
    if depth>32:raise ValueError('bounded JSON nesting required')
    if v is None or type(v)in(str,bool,int):return v
    if type(v)is float:
        if v!=v or v in(float('inf'),float('-inf')):raise ValueError('finite JSON number required')
        return v
    if type(v)is ErrorValue:return dict(status=v.status,code=v.code,source=v.source)
    if type(v)in(list,tuple):return [_json_tree(x,depth+1)for x in v]
    if type(v)is dict and all(type(k)is str for k in v):return{k:_json_tree(x,depth+1)for k,x in v.items()}
    raise TypeError('inert JSON value required')

def replay_saved_acq_event_23113(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>MAX_TOKENS:raise ValueError('bounded JSON token list required')
    classes={'step':Step,'leaf_call':LeafCall,'leaf_return':LeafReturn,'stage_complete':StageComplete};tokens=[]
    for row in rows:
        _exact(row,('kind','uid'),'JSON token')
        if type(row['kind'])is not str or row['kind']not in classes or type(row['uid'])is not str:raise ValueError('known JSON token and exact UID required')
        tokens.append(classes[row['kind']](row['uid']))
    known_unwired={face for plans in LEAF_INPUTS.values()for face,kind,producer,port in plans if kind=='unwired'}
    for key,allowed in(('snapshots',READS),('leaf_returns',LEAVES),('unwired_inputs',known_unwired),('reference_bindings',REFERENCE_URIS)):
        v=payload[key]
        if type(v)is not dict or not set(v)<=set(allowed):raise ValueError('known exact source keys required in '+key)
    snapshots,returns,unwired,bindings={},{},{},{}
    for token in tokens:
        uid=token.frame_uid if type(token)is StageComplete else token.node_uid
        if type(token)is Step and uid in READS:
            v=_value(payload['snapshots'],uid,'JSON snapshot')
            if type(v)is not list:raise TypeError('JSON decoded snapshot list required')
            snapshots[uid]=tuple(_json_tree(v))
        elif type(token)is LeafReturn and uid in LEAVES:
            v=_value(payload['leaf_returns'],uid,'JSON leaf return')
            if type(v)is not dict:raise TypeError('JSON output port map required')
            returns[uid]=dict(v)
            for face,kind in LEAF_OUTPUTS[uid]:
                if kind=='error':returns[uid][face]=_json_error(_value(v,face,'JSON error output'))
            _json_tree(returns[uid])
        elif type(token)is LeafCall and uid in LEAVES:
            for face,kind,producer,port in LEAF_INPUTS[uid]:
                if kind=='unwired':
                    v=_value(payload['unwired_inputs'],face,'JSON unwired argument')
                    unwired[face]=_json_error(v)if producer=='error'else _json_tree(v)
                elif kind=='reference':bindings[producer]=_json_tree(_value(payload['reference_bindings'],producer,'JSON reference interpretation'))
    return _json_tree(replay_event(new,tuple(tokens),snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=bindings))
