"""Original APP00/Event43/frame31552 direct bounded supplied-body replay.
Python3.4 stdlib. Source Case, five-stage Sequence, carrier/bundles/locals direct.
Native leaves never execute; supplied returns and completions remain boundaries.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='31552'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'33106': (0, 15, '5994', '33109', 32, 'booleans'),
 '33201': (1, 15, '5994', '33204', 32, 'booleans'),
 '33410': (2, 36, '71105', '33413', 29, 'booleans'),
 '33499': (3, 36, '71105', '33502', 29, 'booleans'),
 '33571': (3, 44, '66774', '33574', 77, 'booleans'),
 '33594': (3, 15, '5994', '33597', 32, 'booleans')}
BUNDLES={'33095': (0, '33106', '33100', '33097', (('33101', 20, True, '32941'),)),
 '33191': (1, '33201', '33196', '33193', (('33197', 20, False, '33175'),)),
 '33400': (2, '33410', '33405', '33402', (('33406', 16, False, '33322'),))}
WRITES={'33041': (0, 15, '5994', '33076', '33095'),
 '33124': (0, 35, '9101', '33130', None),
 '33185': (1, 15, '5994', '33188', '33191'),
 '33392': (2, 36, '71105', '33395', '33400')}
LEAVES={'33144': 0, '33509': 3, '33577': 3, '33600': 3, '33617': 3, '33985': 4}
LEAF_INPUTS={'33144': (('33149', 'border', '32881', None),),
 '33509': (('33512', 'reference', '33444', None),
           ('33561', 'unwired', 'error', None),
           ('33568', 'read', '33499', None)),
 '33577': (('33579', 'reference', '33462', None),
           ('33585', 'return', '33509', '33564'),
           ('33591', 'read', '33571', None)),
 '33600': (('33602', 'reference', '33481', None),
           ('33608', 'return', '33577', '33588'),
           ('33614', 'read', '33594', None)),
 '33617': (('33635', 'unwired', 'opaque', None),
           ('33659', 'unwired', 'I32', None),
           ('33753', 'unwired', 'string', None),
           ('33842', 'unwired', 'U16', None),
           ('33845', 'return', '33600', '33611')),
 '33985': (('34152', 'literal', '33898', 100),)}
LEAF_OUTPUTS={'33144': (('33146', 'U32'),),
 '33509': (('33544', 'opaque'), ('33564', 'error')),
 '33577': (('33582', 'opaque'), ('33588', 'error')),
 '33600': (('33605', 'opaque'), ('33611', 'error')),
 '33617': (('33626', 'boolean'), ('33631', 'I32'), ('33826', 'string'), ('33836', 'error'), ('33839', 'string')),
 '33985': (('34149', 'U32'),)}
CONSUMED_OUTPUTS={'33144': (), '33509': ('33564',), '33577': ('33588',), '33600': ('33611',), '33617': (), '33985': ()}
REFERENCE_URIS={'33444': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS',
 '33462': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS',
 '33481': 'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96'}
STAGES=('32931', '33169', '33217', '33438', '33886')
BORDER_PATH=(('wire', '34171', '34171', '32837', '32844', '34198'),
 ('paired', '32837', '32844', '32848', '32845'),
 ('wire', '32837', '32848', '32863', '32872', '34162'),
 ('paired', '32863', '32872', '32881', '32873'),
 ('wire', '32863', '32881', '33144', '33149', '33154'))
REQUIRED=tuple(frozenset(x)for x in (('33041', '33095', '33106', '33124', '33144'), ('33185', '33191', '33201'), ('33392', '33400', '33410'), ('33499', '33509', '33571', '33577', '33594', '33600', '33617'), ('33985',)))
CONSTANTS=((('32941', True), ('33016', True)), (('33175', False),), (('33322', False),), (('33444', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'), ('33462', 'ni.var.psp://10.20.30.2/SUPERVISION/EPS'), ('33481', 'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96')), (('33898', 100),))
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
    """Direct selected body; finite tokens preserve source dependencies.

    Error values are routed by identity; they do not supply native success.
    StageComplete joins returned leaves regardless of supplied error status.
    Fresh reads remain independent. False never accesses body inputs.
    """
    if type(new_value)is not bool:raise TypeError('explicit Boolean NewVal required')
    r=dict(source_id=SOURCE_ID,event_uid=EVENT_UID,frame_uid=FRAME_UID,source_version=SOURCE_VERSION,
        scope='SUPPLIED_ACQ_FRAME31552_BODY',new_value=new_value,selected_case_frame='32857'if new_value else'32851',
        event_data_consumed_ports=('32807',),event_data_unconsumed_input_ports=('32366',),
        event_data_unconsumed_ports=('32785','32788','32791','32794'),
        unconsumed_sequence_input_faces=('32900','32902','32903','32904'),
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid='32192',terminal_uid='32807',value=new_value),
        dict(kind='constant',node_uid='34171',value=150),dict(kind='case',node_uid='32837',selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>30:raise ValueError('bounded tuple of inert source tokens required')
    border_values={'32881':150}
    for path in BORDER_PATH:r['log'].append(dict(kind='border_transfer',source_path=path,value=150,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid='32863',stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS))
    enter(0)
    for token in schedule:
        if stage==5:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid='32863'))
            stage+=1
            if stage<5:enter(stage)
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
                unwired_input_ports=tuple(unwired),supplied_ref_interpretation=uid in('33509','33577','33600'))
            r['leaf_calls'].append(row);r['log'].append(row)
        else:
            if uid not in LEAVES or stage!=LEAVES[uid]or uid not in started or uid in done:raise ValueError('leaf return requires one started current leaf')
            v=_value(leaf_returns,uid,'supplied leaf return');_exact(v,[face for face,kind in LEAF_OUTPUTS[uid]],'leaf return')
            for face,kind in LEAF_OUTPUTS[uid]:_typed(v[face],kind)
            returned[uid]=v;done.add(uid);row=dict(kind='leaf_return',node_uid=uid,output_ports=v,
                consumed_output_ports=CONSUMED_OUTPUTS[uid],success_does_not_gate_stage=True)
            r['leaf_returns'].append(row);r['log'].append(row)
    r['active_stage']=STAGES[stage]if stage<5 else None
    r['pending_leaf_uids']=tuple(uid for uid in sorted(started)if uid not in done)
    r['remaining_node_uids']=tuple(sorted(REQUIRED[stage]-done))if stage<5 else()
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

def replay_saved_acq_event_31552(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>30:raise ValueError('bounded JSON token list required')
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
