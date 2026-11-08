"""Original APP00/Event43/frame48846 direct bounded supplied-body replay.
Python3.4 stdlib. Source Case/five-stage Sequence/carrier/bundles/locals direct.
Native leaves never execute; supplied returns and completions remain boundaries.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='48846'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'35726': (3, 36, '71105', '35736', 29, 'booleans'),
 '47280': (3, 44, '66774', '47283', 77, 'booleans'),
 '47323': (3, 15, '5994', '47326', 32, 'booleans'),
 '54039': (0, 15, '5994', '54042', 32, 'booleans'),
 '54110': (1, 15, '5994', '54113', 32, 'booleans'),
 '54186': (2, 44, '66774', '54189', 77, 'booleans'),
 '54210': (2, 36, '71105', '54213', 29, 'booleans')}
BUNDLES={'54029': (0, '54039', '54034', '54031', (('54035', 18, True, '54001'),)),
 '54100': (1, '54110', '54105', '54102', (('54106', 18, False, '54084'),)),
 '54170': (2, '54186', '54175', '54172', (('54176', 49, False, '54132'), ('54179', 45, True, '54142'))),
 '54200': (2, '54210', '54205', '54202', (('54206', 15, False, '54152'),))}
WRITES={'54021': (0, 15, '5994', '54024', '54029'),
 '54045': (0, 35, '9101', '54048', None),
 '54094': (1, 15, '5994', '54097', '54100'),
 '54162': (2, 44, '66774', '54165', '54170'),
 '54192': (2, 36, '71105', '54195', '54200')}
LEAVES={'54053': 0, '47263': 3, '47306': 3, '47349': 3, '47366': 3, '50582': 4}
LEAF_INPUTS={'54053': (('54058', 'border', '53989', None),),
 '47263': (('47265', 'reference', '47245', None),
           ('47271', 'unwired', 'error', None),
           ('47277', 'read', '35726', None)),
 '47306': (('47308', 'reference', '47290', None),
           ('47314', 'return', '47263', '47274'),
           ('47320', 'read', '47280', None)),
 '47349': (('47351', 'reference', '47333', None),
           ('47357', 'return', '47306', '47317'),
           ('47363', 'read', '47323', None)),
 '47366': (('47375', 'unwired', 'opaque', None),
           ('47378', 'unwired', 'I32', None),
           ('47381', 'unwired', 'string', None),
           ('47393', 'unwired', 'U16', None),
           ('47396', 'return', '47349', '47360')),
 '50582': (('50592', 'literal', '50809', 100),)}
LEAF_OUTPUTS={'54053': (('54055', 'U32'),),
 '47263': (('47268', 'opaque'), ('47274', 'error')),
 '47306': (('47311', 'opaque'), ('47317', 'error')),
 '47349': (('47354', 'opaque'), ('47360', 'error')),
 '47366': (('47369', 'boolean'), ('47372', 'I32'), ('47384', 'string'), ('47387', 'error'), ('47390', 'string')),
 '50582': (('50585', 'U32'),)}
CONSUMED_OUTPUTS={'54053': (), '47263': ('47274',), '47306': ('47317',), '47349': ('47360',), '47366': (), '50582': ()}
REFERENCE_URIS={'47245': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS',
 '47290': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS',
 '47333': 'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96'}
STAGES=('53995', '54078', '54126', '54238', '50555')
BORDER_PATH=(('wire', '54357', '54357', '53958', '53965', '54370'),
 ('paired', '53958', '53965', '53969', '53966'),
 ('wire', '53958', '53969', '53984', '53986', '54352'),
 ('paired', '53984', '53986', '53989', '53987'),
 ('wire', '53984', '53989', '54053', '54058', '54063'))
REQUIRED=tuple(frozenset(x)for x in (('54021', '54029', '54039', '54045', '54053'), ('54094', '54100', '54110'), ('54162', '54170', '54186', '54192', '54200', '54210'), ('35726', '47263', '47280', '47306', '47323', '47349', '47366'), ('50582',)))
CONSTANTS=((('54001', True), ('54011', True)), (('54084', False),), (('54132', False), ('54142', True), ('54152', False)), (('47245', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'), ('47290', 'ni.var.psp://10.20.30.2/SUPERVISION/EPS'), ('47333', 'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96')), (('50809', 100),))
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
        scope='SUPPLIED_ACQ_FRAME48846_BODY',new_value=new_value,selected_case_frame='53978'if new_value else'53972',
        event_data_consumed_ports=('53951',),event_data_unconsumed_input_ports=('48864',),
        event_data_unconsumed_ports=('48867','48870','48873','48876'),
        unconsumed_sequence_input_faces=('53990','53991','53992','50574'),
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid='48862',terminal_uid='53951',value=new_value),
        dict(kind='constant',node_uid='54357',value=150),dict(kind='case',node_uid='53958',selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>33:raise ValueError('bounded tuple of inert source tokens required')
    border_values={'53989':150}
    for path in BORDER_PATH:r['log'].append(dict(kind='border_transfer',source_path=path,value=150,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid='53984',stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS))
    enter(0)
    for token in schedule:
        if stage==5:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid='53984'))
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
                unwired_input_ports=tuple(unwired),supplied_ref_interpretation=any(p[1]=='reference'for p in LEAF_INPUTS[uid]))
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

def replay_saved_acq_event_48846(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>33:raise ValueError('bounded JSON token list required')
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
