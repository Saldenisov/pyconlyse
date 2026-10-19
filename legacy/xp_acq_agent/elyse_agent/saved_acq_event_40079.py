"""Original APP00/Event43/frame40079 direct bounded hierarchical replay.
Python3.4 stdlib; original subVI/native leaves remain explicit supplied boundaries.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='40079'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'40206': (0, 15, '5994', '40209', 32, 'booleans'),
 '40277': (1, 15, '5994', '40280', 32, 'booleans'),
 '40355': (6, 15, '5994', '40358', 32, 'booleans'),
 '40415': (7, 15, '5994', '40418', 32, 'booleans'),
 '40520': (9, 44, '66774', '40523', 77, 'booleans'),
 '40544': (9, 36, '71105', '40547', 29, 'booleans'),
 '40617': (10, 36, '71105', '40620', 29, 'booleans')}
BUNDLES={'40196': (0, '40206', '40201', '40198', (('40202', 7, True, '40168'),)),
 '40267': (1, '40277', '40272', '40269', (('40273', 7, False, '40251'),)),
 '40345': (6, '40355', '40350', '40347', (('40351', 2, True, '40329'),)),
 '40405': (7, '40415', '40410', '40407', (('40411', 2, False, '40389'),)),
 '40507': (9,
           '40520',
           '40512',
           '40509',
           (('40513', 35, False, '40469'), ('40516', 32, True, '40479'), ('43525', 30, False, '40469'))),
 '40534': (9, '40544', '40539', '40536', (('40540', 10, False, '40489'),))}
WRITES={'40188': (0, 15, '5994', '40191', '40196'),
 '40212': (0, 35, '9101', '40215', None),
 '40261': (1, 15, '5994', '40264', '40267'),
 '40339': (6, 15, '5994', '40342', '40345'),
 '40399': (7, 15, '5994', '40402', '40405'),
 '40499': (9, 44, '66774', '40502', '40507'),
 '40526': (9, 36, '71105', '40529', '40534')}
LEAVES={'38600': 3,
 '40220': 0,
 '40311': 2,
 '40361': 6,
 '40451': 8,
 '40609': 10,
 '40623': 10,
 '40640': 10,
 '50176': 4,
 '50796': 3}
LEAF_INPUTS={'38600': (('45228', 'unwired', 'opaque', None),
           ('45233', 'unwired', 'opaque', None),
           ('45236', 'unwired', 'opaque', None),
           ('45240', 'unwired', 'opaque', None),
           ('45243', 'unwired', 'opaque', None),
           ('45247', 'unwired', 'opaque', None)),
 '40220': (('40225', 'border', '40152', None),),
 '40311': (('40316', 'literal', '40299', 29000),),
 '40361': (('40366', 'border', '40155', None),),
 '40451': (('40456', 'literal', '40439', 250),),
 '40609': (('40614', 'literal', '40579', 100),),
 '40623': (('40625', 'reference', '40591', None),
           ('40631', 'unwired', 'error', None),
           ('40637', 'read', '40617', None)),
 '40640': (('40649', 'unwired', 'opaque', None),
           ('40652', 'unwired', 'I32', None),
           ('40655', 'unwired', 'string', None),
           ('40667', 'unwired', 'U16', None),
           ('40670', 'return', '40623', '40634')),
 '50176': (('50185', 'literal', '50198', 1500),),
 '50796': (('50852', 'unwired', 'opaque', None),
           ('50860', 'unwired', 'I32', None),
           ('50873', 'unwired', 'string', None),
           ('50904', 'unwired', 'U16', None),
           ('50912', 'return', '38600', '45219'))}
LEAF_OUTPUTS={'38600': (('45219', 'error'),),
 '40220': (('40222', 'U32'),),
 '40311': (('40313', 'U32'),),
 '40361': (('40363', 'U32'),),
 '40451': (('40453', 'U32'),),
 '40609': (('40611', 'U32'),),
 '40623': (('40628', 'opaque'), ('40634', 'error')),
 '40640': (('40643', 'boolean'), ('40646', 'I32'), ('40658', 'string'), ('40661', 'error'), ('40664', 'string')),
 '50176': (('50182', 'U32'),),
 '50796': (('50836', 'boolean'), ('50844', 'I32'), ('50881', 'string'), ('50887', 'error'), ('50895', 'string'))}
CONSUMED_OUTPUTS={'38600': ('45219',),
 '40220': (),
 '40311': (),
 '40361': (),
 '40451': (),
 '40609': (),
 '40623': ('40634',),
 '40640': (),
 '50176': (),
 '50796': ()}
REFERENCE_URIS={'40591': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}
STAGES=('40162', '40245', '46840', '48404', '49054', '40293', '40323', '40383', '40432', '40463', '40573')
REQUIRED=tuple(frozenset(x)for x in (('40188', '40196', '40206', '40212', '40220'),
 ('40261', '40267', '40277'),
 ('40311',),
 ('38600', '50796'),
 ('50176',),
 (),
 ('40339', '40345', '40355', '40361'),
 ('40399', '40405', '40415'),
 ('40451',),
 ('40499', '40507', '40520', '40526', '40534', '40544'),
 ('40609', '40617', '40623', '40640')))
CONSTANTS=((('40168', True), ('40178', True)),
 (('40251', False),),
 (('40299', 29000),),
 (),
 (('50198', 1500),),
 (),
 (('40329', True),),
 (('40389', False),),
 (('40439', 250),),
 (('40469', False), ('40479', True), ('40489', False)),
 (('40579', 100), ('40591', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS')))
BORDER_PATH=(('wire', '40692', '40692', '40121', '40128', '40705'),
 ('paired', '40121', '40128', '40132', '40129'),
 ('wire', '40121', '40132', '40147', '40149', '40687'),
 ('paired', '40147', '40149', '40152', '40150'),
 ('wire', '40147', '40152', '40220', '40225', '40230'),
 ('paired', '40147', '40149', '40155', '40150'),
 ('wire', '40147', '40155', '40361', '40366', '40371'))
BORDER_VALUES={'40152': 150, '40155': 150}
MAIN_STAGES=('40162', '40245', '40293', '40323', '40383', '40432', '40463', '40573')
NESTED_STAGES=('46840', '48404', '49054')
NESTED_CONTAINERS=('46836', '48400', '49050')
PHASE_SEQUENCE_UIDS=('40147', '40147', '46815', '46815', '46815', '40147', '40147', '40147', '40147', '40147', '40147')
CASE_UID='40121'
SEQUENCE_UID='40147'
NESTED_SEQUENCE_UID='46815'
EVENT_DATA_UID='40097'
TRUE_FRAME='40141'
FALSE_FRAME='40135'
NEWVAL_FACE='40114'
EVENT_INPUT_FACES=('40099',)
EVENT_UNUSED_FACES=('40102', '40105', '40108', '40111')
SEQUENCE_UNUSED_FACES=('40153', '40154', '40156', '40157', '40158', '40159')
OUTER_CONSTANT_UID='40692'
MAX_TOKENS=51
SUPPLIED_LITERAL_CARRIERS={'40251': False, '40389': False, '40469': False, '40489': False}
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
        scope='SUPPLIED_ACQ_FRAME40079_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
        event_data_consumed_ports=(NEWVAL_FACE,),event_data_unconsumed_input_ports=EVENT_INPUT_FACES,
        event_data_unconsumed_ports=EVENT_UNUSED_FACES,
        unconsumed_sequence_output_faces=SEQUENCE_UNUSED_FACES,
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],completed_main_stages=[],completed_nested_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid=EVENT_DATA_UID,terminal_uid=NEWVAL_FACE,value=new_value),
        dict(kind='constant',node_uid=OUTER_CONSTANT_UID,value=150),dict(kind='case',node_uid=CASE_UID,selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>MAX_TOKENS:raise ValueError('bounded tuple of inert source tokens required')
    border_values=BORDER_VALUES
    for path in BORDER_PATH:r['log'].append(dict(kind='border_transfer',source_path=path,value=150,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid=SEQUENCE_UID,stage_uids=MAIN_STAGES))
    def enter(i):
        if STAGES[i]==NESTED_STAGES[0]:r['log'].append(dict(kind='sequence',node_uid=NESTED_SEQUENCE_UID,stage_uids=NESTED_STAGES,parent_frame_uid=MAIN_STAGES[2],container_uids=NESTED_CONTAINERS))
        for uid,v in CONSTANTS[i]:
            if uid in SUPPLIED_LITERAL_CARRIERS:v=_literal(literal_inputs,uid)
            r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS,supplied_storage_projection=uid in SUPPLIED_LITERAL_CARRIERS))
    enter(0)
    for token in schedule:
        if stage==len(STAGES):raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid)
            r['completed_nested_stages'if token.frame_uid in NESTED_STAGES else'completed_main_stages'].append(token.frame_uid)
            r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid=PHASE_SEQUENCE_UIDS[stage]))
            if token.frame_uid==NESTED_STAGES[-1]:r['log'].append(dict(kind='sequence_complete',node_uid=NESTED_SEQUENCE_UID,parent_frame_uid=MAIN_STAGES[2]))
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

def replay_saved_acq_event_40079(payload):
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
