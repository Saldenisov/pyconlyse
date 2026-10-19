"""Original APP00/Event43/frame38732 bounded source-owned projection.
Six directly lowered saved Sequence stages; native leaves supplied, never called.
Two absent raw indices and four unresolved literal-storage projections explicit.
Stdlib Python3.4; no native/default/scheduler/whole equivalence.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='38732'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'38883': (0, 9, '7379', '38886', 10, 'floats'),
 '38959': (0, 10, '7264', '38965', 10, 'floats'),
 '39043': (1, 9, '7379', '39049', 10, 'floats'),
 '39059': (1, 10, '7264', '39067', 10, 'floats'),
 '39636': (3, 44, '66774', '39645', 77, 'booleans'),
 '39698': (3, 36, '71105', '39708', 29, 'booleans'),
 '39855': (4, 36, '71105', '39858', 29, 'booleans'),
 '39878': (4, 44, '66774', '39881', 77, 'booleans')}
BUNDLES={'38849': (0,
           '38883',
           '38854',
           '38851',
           (('38855', None, 0.0, '38829'),
            ('38858', 1, 0.0, '38829'),
            ('38861', 2, 0.0, '38829'),
            ('38864', 3, 0.0, '38829'),
            ('38867', 4, 0.0, '38829'),
            ('38870', 5, 0.0, '38829'),
            ('38873', 6, 0.0, '38829'),
            ('38876', 7, 0.0, '38829'),
            ('38879', 9, 0.0, '38829'))),
 '38905': (0,
           '38959',
           '38910',
           '38907',
           (('38911', None, 0.0, '38829'),
            ('38914', 1, 0.0, '38829'),
            ('38917', 3, 0.0, '38829'),
            ('38920', 4, 0.0, '38829'),
            ('38927', 6, 0.0, '38829'),
            ('38937', 7, 0.0, '38829'),
            ('38950', 8, 0.0, '38829'),
            ('38954', 9, 0.0, '38829'))),
 '39579': (3,
           '39636',
           '39594',
           '39585',
           (('38848', 59, False, '42005'),
            ('39624', 64, False, '39475'),
            ('39629', 61, True, '39529'))),
 '39675': (3, '39698', '39682', '39678', (('39688', 21, False, '39502'),))}
WRITES={'38841': (0, 9, '7379', '38844', '38849'),
 '38889': (0, 35, '9101', '38892', None),
 '38897': (0, 10, '7264', '38900', '38905'),
 '39559': (3, 44, '66774', '39564', '39579'),
 '39654': (3, 36, '71105', '39663', '39675')}
LEAVES={'39076': 1, '39140': 1, '39162': 1, '39266': 2, '39861': 4, '39885': 4, '39904': 4, '39983': 5}
LEAF_INPUTS={'39076': (('39097', 'unwired', 'opaque', None),
           ('39106', 'unwired', 'I32', None),
           ('39115', 'unwired', 'string', None),
           ('39131', 'unwired', 'U16', None),
           ('39134', 'return', '39162', '39176')),
 '39140': (('39144', 'reference', '38993', None),
           ('39150', 'unwired', 'error', None),
           ('39158', 'read', '39043', None)),
 '39162': (('39164', 'reference', '39011', None),
           ('39171', 'return', '39140', '39153'),
           ('39180', 'read', '39059', None)),
 '39266': (('39273', 'literal', '39241', 1000),),
 '39861': (('39863', 'reference', '39778', None),
           ('39869', 'unwired', 'error', None),
           ('39875', 'read', '39855', None)),
 '39885': (('39888', 'reference', '39813', None),
           ('39895', 'return', '39861', '39872'),
           ('39901', 'read', '39878', None)),
 '39904': (('39913', 'unwired', 'opaque', None),
           ('39916', 'unwired', 'I32', None),
           ('39919', 'unwired', 'string', None),
           ('39931', 'unwired', 'U16', None),
           ('39934', 'return', '39885', '39898')),
 '39983': (('39988', 'literal', '39971', 200),)}
LEAF_OUTPUTS={'39076': (('39083', 'boolean'),
           ('39087', 'I32'),
           ('39122', 'string'),
           ('39125', 'error'),
           ('39128', 'string')),
 '39140': (('39147', 'opaque'), ('39153', 'error')),
 '39162': (('39167', 'opaque'), ('39176', 'error')),
 '39266': (('39269', 'U32'),),
 '39861': (('39866', 'opaque'), ('39872', 'error')),
 '39885': (('39892', 'opaque'), ('39898', 'error')),
 '39904': (('39907', 'boolean'),
           ('39910', 'I32'),
           ('39922', 'string'),
           ('39925', 'error'),
           ('39928', 'string')),
 '39983': (('39985', 'U32'),)}
CONSUMED_OUTPUTS={'39076': (),
 '39140': ('39153',),
 '39162': ('39176',),
 '39266': (),
 '39861': ('39872',),
 '39885': ('39898',),
 '39904': (),
 '39983': ()}
REFERENCE_URIS={'38993': 'ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703',
 '39011': 'ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703',
 '39778': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS',
 '39813': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS'}
STAGES=('38812', '38987', '39227', '39387', '39743', '39965')
REQUIRED=(('38841', '38849', '38883', '38889', '38897', '38905', '38959'),
 ('39043', '39059', '39076', '39140', '39162'),
 ('39266',),
 ('39559', '39579', '39636', '39654', '39675', '39698'),
 ('39855', '39861', '39878', '39885', '39904'),
 ('39983',))
CONSTANTS=((('38818', True), ('38829', 0.0)),
 (('38993', 'ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703'),
  ('39011', 'ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703')),
 (('39241', 1000),),
 (('39475', False), ('39502', False), ('39529', True), ('42005', False)),
 (('39778', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'),
  ('39813', 'ni.var.psp://10.20.30.2/SUPERVISION/EPS')),
 (('39971', 200),))
CASE_UID='38772'
SEQUENCE_UID='38798'
EVENT_DATA_UID='38748'
TRUE_FRAME='38792'
FALSE_FRAME='38786'
NEWVAL_FACE='38765'
EVENT_INPUT_FACES=('38750',)
EVENT_UNUSED_FACES=('38753', '38756', '38759', '38762')
SEQUENCE_UNUSED_FACES=('38803', '38804', '38805', '38807', '38808', '38809')
OUTER_CONSTANT_UID='40001'
MAX_TOKENS=39
ABSENT_FIELD_INDICES={'38855': 0, '38911': 0}
SUPPLIED_LITERAL_CARRIERS={'38829': 0.0, '39475': False, '39502': False, '42005': False}
REQUIRED=tuple(frozenset(x)for x in REQUIRED)
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
def _field_index(bindings,face):
    v=_value(bindings,face,'unresolved saved field projection')
    if type(v)is not int or v!=ABSENT_FIELD_INDICES[face]:raise ValueError('explicit bounded model-index projection required; native default unknown')
    return v

def _literal(inputs,uid):
    v=_value(inputs,uid,'unresolved saved literal storage projection');expected=SUPPLIED_LITERAL_CARRIERS[uid]
    if type(v)is not type(expected)or v!=expected or(type(v)is float and repr(v)!='0.0'):raise ValueError('explicit exact bounded model literal projection required')
    return v

def _bank(value,count,kind):
    if type(value)is not tuple or len(value)!=count:raise TypeError('explicit decoded tuple length'+str(count)+' required')
    if kind=='booleans' and any(type(v)is not bool for v in value):raise TypeError('exact Boolean carrier fields required')
    if kind=='floats'and any(type(v)is not float or v!=v or v in(float('inf'),float('-inf'))for v in value):raise TypeError('exact finite decoded DBL carrier fields required')
def _binding(bindings,uid):
    r=_value(bindings,uid,'supplied reference binding');_exact(r,('constant_uid','saved_uri','native_ref'),'reference binding')
    if r['constant_uid']!=uid or r['saved_uri']!=REFERENCE_URIS[uid]:raise ValueError('matching saved constant/URI required')
    return r['native_ref']

def replay_event(new_value,schedule,*,snapshots,leaf_returns,unwired_inputs,reference_bindings,field_index_bindings,literal_inputs):
    """Direct selected body; finite tokens preserve source dependencies.

    Error values are routed by identity; they do not supply native success.
    StageComplete joins returned leaves regardless of supplied error status.
    Fresh reads remain independent. False never accesses body inputs.
    """
    if type(new_value)is not bool:raise TypeError('explicit Boolean NewVal required')
    r=dict(source_id=SOURCE_ID,event_uid=EVENT_UID,frame_uid=FRAME_UID,source_version=SOURCE_VERSION,
        scope='SUPPLIED_ACQ_FRAME38732_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
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
    r['log'].append(dict(kind='unused_outer_carrier',node_uid='40001',value=150,case_faces=('38779','38783'),sequence_input_face='38800',unused_sequence_faces=SEQUENCE_UNUSED_FACES,native_forwarding_qualified=False))
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid=SEQUENCE_UID,stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:
            if uid in SUPPLIED_LITERAL_CARRIERS:v=_literal(literal_inputs,uid)
            r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS,supplied_storage_projection=uid in SUPPLIED_LITERAL_CARRIERS))
    enter(0)
    for token in schedule:
        if stage==6:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid=SEQUENCE_UID))
            stage+=1
            if stage<6:enter(stage)
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
                    if index is None:index=_field_index(field_index_bindings,face)
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
    r['active_stage']=STAGES[stage]if stage<6 else None
    r['pending_leaf_uids']=tuple(uid for uid in sorted(started)if uid not in done)
    r['remaining_node_uids']=tuple(sorted(REQUIRED[stage]-done))if stage<6 else()
    r['selected_body_completed']=r['schedule_complete']=stage==6
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

def replay_saved_acq_event_38732(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings','field_index_bindings','literal_inputs'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None,field_index_bindings=None,literal_inputs=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>MAX_TOKENS:raise ValueError('bounded JSON token list required')
    classes={'step':Step,'leaf_call':LeafCall,'leaf_return':LeafReturn,'stage_complete':StageComplete};tokens=[]
    for row in rows:
        _exact(row,('kind','uid'),'JSON token')
        if type(row['kind'])is not str or row['kind']not in classes or type(row['uid'])is not str:raise ValueError('known JSON token and exact UID required')
        tokens.append(classes[row['kind']](row['uid']))
    known_unwired={face for plans in LEAF_INPUTS.values()for face,kind,producer,port in plans if kind=='unwired'}
    for key,allowed in(('snapshots',READS),('leaf_returns',LEAVES),('unwired_inputs',known_unwired),('reference_bindings',REFERENCE_URIS),('field_index_bindings',ABSENT_FIELD_INDICES),('literal_inputs',SUPPLIED_LITERAL_CARRIERS)):
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
    return _json_tree(replay_event(new,tuple(tokens),snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=bindings,field_index_bindings=payload['field_index_bindings'],literal_inputs=payload['literal_inputs']))
