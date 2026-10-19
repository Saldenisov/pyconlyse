"""Original APP00/Event43/frame17899 direct bounded supplied-body replay.
Python3.4 stdlib; native leaves never execute. Explicit saved-storage projections.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='17899'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'13611': (0, 17, '5074', '13654', 40, 'booleans'),
 '20437': (1, 17, '5074', '20765', 40, 'booleans'),
 '21967': (3, 17, '5074', '21982', 40, 'booleans'),
 '22138': (4, 17, '5074', '22141', 40, 'booleans'),
 '22985': (5, 44, '66774', '22990', 77, 'booleans'),
 '23076': (5, 36, '71105', '23079', 29, 'booleans'),
 '23171': (6, 36, '71105', '23174', 29, 'booleans')}
BUNDLES={'11019': (0, '13611', '13600', '13571', (('13606', 1, False, '7970'),)),
 '20420': (1, '20437', '20428', '20423', (('20429', 1, True, '18873'),)),
 '21826': (3, '21967', '21945', '21837', (('21954', 4, False, '21733'),)),
 '22115': (4, '22138', '22129', '22121', (('22131', 4, True, '22071'),)),
 '22959': (5,
           '22985',
           '22964',
           '22961',
           (('22965', 3, False, '22885'),
            ('22968', 2, False, '22900'),
            ('22972', 5, True, '22910'),
            ('22975', 1, False, '22921'))),
 '23043': (5, '23076', '23051', '23048', (('23052', 1, False, '22931'),))}
WRITES={'10838': (0, 17, '5074', '10853', '11019'),
 '16177': (0, 35, '9101', '16339', None),
 '20410': (1, 17, '5074', '20414', '20420'),
 '21773': (3, 17, '5074', '21789', '21826'),
 '22098': (4, 17, '5074', '22106', '22115'),
 '22951': (5, 44, '66774', '22954', '22959'),
 '23005': (5, 36, '71105', '23034', '23043')}
LEAVES={'16362': 0, '21625': 2, '21990': 3, '22147': 4, '23162': 6, '23177': 6, '23194': 6}
LEAF_INPUTS={'16362': (('16413', 'border', '7949', None),),
 '21625': (('21640', 'literal', '21486', 400),),
 '21990': (('22010', 'border', '7952', None),),
 '22147': (('22162', 'border', '7953', None),),
 '23162': (('23168', 'literal', '23123', 100),),
 '23177': (('23179', 'reference', '23135', None),
           ('23185', 'unwired', 'error', None),
           ('23191', 'read', '23171', None)),
 '23194': (('23204', 'unwired', 'opaque', None),
           ('23209', 'unwired', 'I32', None),
           ('23213', 'unwired', 'string', None),
           ('23232', 'unwired', 'U16', None),
           ('23236', 'return', '23177', '23188'))}
LEAF_OUTPUTS={'16362': (('16403', 'U32'),),
 '21625': (('21633', 'U32'),),
 '21990': (('22004', 'U32'),),
 '22147': (('22153', 'U32'),),
 '23162': (('23165', 'U32'),),
 '23177': (('23182', 'opaque'), ('23188', 'error')),
 '23194': (('23197', 'boolean'), ('23201', 'I32'), ('23217', 'string'), ('23226', 'error'), ('23229', 'string'))}
CONSUMED_OUTPUTS={'16362': (), '21625': (), '21990': (), '22147': (), '23162': (), '23177': ('23188',), '23194': ()}
REFERENCE_URIS={'23135': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}
STAGES=('7963', '18101', '21010', '21712', '22060', '22878', '23117')
REQUIRED=tuple(frozenset(x)for x in (('10838', '11019', '13611', '16177', '16362'),
 ('20410', '20420', '20437'),
 ('21625',),
 ('21773', '21826', '21967', '21990'),
 ('22098', '22115', '22138', '22147'),
 ('22951', '22959', '22985', '23005', '23043', '23076'),
 ('23162', '23171', '23177', '23194')))
CONSTANTS=((('7970', False), ('8484', True)),
 (('18873', True),),
 (('21486', 400),),
 (('21733', False),),
 (('22071', True),),
 (('22885', False), ('22900', False), ('22910', True), ('22921', False), ('22931', False)),
 (('23123', 100), ('23135', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS')))
BORDER_PATH=(('wire', '18551', '18551', '17947', '17956', '18564'),
 ('paired', '17947', '17956', '17961', '17957'),
 ('wire', '17947', '17961', '7929', '7941', '24452'),
 ('paired', '7929', '7941', '7949', '7942'),
 ('wire', '7929', '7949', '16362', '16413', '16596'),
 ('paired', '7929', '7941', '7952', '7942'),
 ('wire', '7929', '7952', '21990', '22010', '22028'),
 ('paired', '7929', '7941', '7953', '7942'),
 ('wire', '7929', '7953', '22147', '22162', '22179'))
BORDER_VALUES={'7949': 150, '7952': 150, '7953': 150}
CASE_UID='17947'
SEQUENCE_UID='7929'
EVENT_DATA_UID='17919'
TRUE_FRAME='17970'
FALSE_FRAME='17964'
NEWVAL_FACE='17939'
EVENT_INPUT_FACES=('17922',)
EVENT_UNUSED_FACES=('17925', '17929', '17933', '17936')
SEQUENCE_UNUSED_FACES=('7950', '7951', '7959', '7960')
OUTER_CONSTANT_UID='18551'
MAX_TOKENS=41
SUPPLIED_LITERAL_CARRIERS={'21733': False, '22885': False, '22900': False, '22921': False, '22931': False, '7970': False}
LIMITS=dict(execution_allowed=False,external_calls_executed=False,hardware_writes=False,native_runtime_equivalence=False,native_callee_equivalence=False,whole_event_equivalence=False,whole_vi_equivalence=False,native_default_qualified=False,native_ref_interpretation_qualified=False,native_task_reference_qualified=False,psp_delivery_qualified=False,wait_units_or_pulse_duration_qualified=False,snapshot_equality_qualified=False,scheduler_qualified=False,event_selection_qualified=False,event_acknowledgement_qualified=False,native_cluster_decode_qualified=False,native_literal_serializer_qualified=False)

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
def _literal(inputs,uid):
    v=_value(inputs,uid,'unresolved saved literal storage projection')
    if type(v)is not bool or v is not SUPPLIED_LITERAL_CARRIERS[uid]:raise ValueError('explicit exact bounded Boolean model projection required; native storage unknown')
    return v

def _bank(value,count,kind):
    if type(value)is not tuple or len(value)!=count:raise TypeError('explicit decoded tuple length'+str(count)+' required')
    if kind=='booleans' and any(type(v)is not bool for v in value):raise TypeError('exact Boolean carrier fields required')
def _binding(bindings,uid):
    r=_value(bindings,uid,'supplied reference binding');_exact(r,('constant_uid','saved_uri','native_ref'),'reference binding')
    if r['constant_uid']!=uid or r['saved_uri']!=REFERENCE_URIS[uid]:raise ValueError('matching saved constant/URI required')
    return r['native_ref']

def replay_event(new_value,schedule,*,snapshots,leaf_returns,unwired_inputs,reference_bindings,literal_inputs):
    """Direct selected body; finite tokens preserve source dependencies.

    Error values are routed by identity; they do not supply native success.
    StageComplete joins returned leaves regardless of supplied error status.
    Fresh reads remain independent. False never accesses body inputs.
    """
    if type(new_value)is not bool:raise TypeError('explicit Boolean NewVal required')
    r=dict(source_id=SOURCE_ID,event_uid=EVENT_UID,frame_uid=FRAME_UID,source_version=SOURCE_VERSION,
        scope='SUPPLIED_ACQ_FRAME17899_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
        event_data_consumed_ports=(NEWVAL_FACE,),event_data_unconsumed_input_ports=EVENT_INPUT_FACES,
        event_data_unconsumed_ports=EVENT_UNUSED_FACES,
        unconsumed_sequence_input_faces=SEQUENCE_UNUSED_FACES,
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid=EVENT_DATA_UID,terminal_uid=NEWVAL_FACE,value=new_value),
        dict(kind='constant',node_uid=OUTER_CONSTANT_UID,value=150),dict(kind='case',node_uid=CASE_UID,selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>MAX_TOKENS:raise ValueError('bounded tuple of inert source tokens required')
    border_values=BORDER_VALUES
    for path in BORDER_PATH:r['log'].append(dict(kind='border_transfer',source_path=path,value=150,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid=SEQUENCE_UID,stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:
            if uid in SUPPLIED_LITERAL_CARRIERS:v=_literal(literal_inputs,uid)
            r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS,supplied_storage_projection=uid in SUPPLIED_LITERAL_CARRIERS))
    enter(0)
    for token in schedule:
        if stage==len(STAGES):raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid=SEQUENCE_UID))
            stage+=1
            if stage<len(STAGES):enter(stage)
            continue
        if type(token)not in(Step,LeafCall,LeafReturn)or type(token.node_uid)is not str:raise TypeError('known inert token and exact source node UID required')
        uid=token.node_uid
        if type(token)is Step:
            if uid in done:raise ValueError('source node completes only once')
            if uid in READS:
                owner,bank,target,face,count,kind=READS[uid]
                if stage!=owner:raise ValueError('local read requires current saved stage')
                v=_value(snapshots,uid,'local snapshot');_bank(v,count,kind);values[uid]=v
                r['log'].append(dict(kind='local_read',node_uid=uid,terminal_uid=face,bank_index=bank,control_terminal_uid=target,value=v))
            elif uid in BUNDLES:
                owner,read,base,output,fields=BUNDLES[uid]
                if stage!=owner or read not in done:raise ValueError('bundle requires completed current saved snapshot')
                v=list(values[read]);inputs={base:values[read]};changes=[]
                for face,index,bit,literal in fields:
                    if literal in SUPPLIED_LITERAL_CARRIERS:bit=_literal(literal_inputs,literal)
                    v[index]=bit;inputs[face]=bit;changes.append(dict(terminal_uid=face,field_index=index,value=bit,constant_uid=literal))
                values[uid]=tuple(v);r['log'].append(dict(kind='bundle',node_uid=uid,input_ports=inputs,output_terminal_uid=output,assignments=changes,value=values[uid]))
            elif uid in WRITES:
                owner,bank,target,face,bundle=WRITES[uid]
                if stage!=owner or(bundle is not None and bundle not in done):raise ValueError('local write requires saved current bundle dependency')
                v=True if bundle is None else values[bundle];row=dict(kind='local_write',node_uid=uid,terminal_uid=face,bank_index=bank,control_terminal_uid=target,value=v)
                r['writes'].append(row);r['log'].append(row)
            else:raise ValueError('Step requires exact saved local/unbundle/bundle node')
            done.add(uid)
        elif type(token)is LeafCall:
            if uid not in LEAVES or stage!=LEAVES[uid]or uid in started:raise ValueError('one current saved leaf call required')
            inputs={};unwired=[]
            for face,kind,producer,port in LEAF_INPUTS[uid]:
                if kind=='unwired':
                    v=_value(unwired_inputs,face,'unwired leaf input');_typed(v,producer);unwired.append(face)
                elif kind=='return':
                    if producer not in done:raise ValueError('leaf requires wired producer supplied completion')
                    v=returned[producer][port]
                elif kind=='read':
                    if producer not in done:raise ValueError('PSP leaf requires separate fresh source snapshot')
                    v=values[producer]
                elif kind=='reference':v=_binding(reference_bindings,producer)
                elif kind=='border':v=border_values[producer]
                else:v=port
                inputs[face]=v
            started.add(uid);row=dict(kind='leaf_call',node_uid=uid,input_ports=inputs,input_port_order=tuple(x[0]for x in LEAF_INPUTS[uid]),
                unwired_input_ports=tuple(unwired),supplied_ref_interpretation=any(p[1]=='reference'for p in LEAF_INPUTS[uid]))
            r['leaf_calls'].append(row);r['log'].append(row)
        else:
            if uid not in LEAVES or stage!=LEAVES[uid]or uid not in started or uid in done:raise ValueError('leaf return requires one started current leaf')
            v=_value(leaf_returns,uid,'supplied leaf return');_exact(v,[face for face,kind in LEAF_OUTPUTS[uid]],'leaf return')
            for face,kind in LEAF_OUTPUTS[uid]:_typed(v[face],kind)
            returned[uid]=v;done.add(uid);row=dict(kind='leaf_return',node_uid=uid,output_ports=v,
                consumed_output_ports=CONSUMED_OUTPUTS[uid],success_does_not_gate_stage=True)
            r['leaf_returns'].append(row);r['log'].append(row)
    r['active_stage']=STAGES[stage]if stage<len(STAGES) else None
    r['pending_leaf_uids']=tuple(uid for uid in sorted(started)if uid not in done)
    r['remaining_node_uids']=tuple(sorted(REQUIRED[stage]-done))if stage<len(STAGES) else()
    r['selected_body_completed']=r['schedule_complete']=stage==len(STAGES)
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

def replay_saved_acq_event_17899(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None,literal_inputs=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>MAX_TOKENS:raise ValueError('bounded JSON token list required')
    classes={'step':Step,'leaf_call':LeafCall,'leaf_return':LeafReturn,'stage_complete':StageComplete};tokens=[]
    for row in rows:
        _exact(row,('kind','uid'),'JSON token')
        if type(row['kind'])is not str or row['kind']not in classes or type(row['uid'])is not str:raise ValueError('known JSON token and exact UID required')
        tokens.append(classes[row['kind']](row['uid']))
    known_unwired={face for plans in LEAF_INPUTS.values()for face,kind,producer,port in plans if kind=='unwired'}
    for key,allowed in(('snapshots',READS),('leaf_returns',LEAVES),('unwired_inputs',known_unwired),('reference_bindings',REFERENCE_URIS),('literal_inputs',SUPPLIED_LITERAL_CARRIERS)):
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
    return _json_tree(replay_event(new,tuple(tokens),snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=bindings,literal_inputs=payload['literal_inputs']))
