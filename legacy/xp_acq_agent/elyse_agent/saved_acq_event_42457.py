"""Original APP00/Event43/frame42457 directly lowered bounded body.
Seven saved stages; native/callee leaves explicitly supplied, never called.
Two absent indices and seven storage projections are hypothetical caller bindings.
Stdlib Python3.4; native/default/scheduling/whole semantics remain open.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='42457'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'30243': (3, 17, '5074', '31548', 40, 'booleans'),
 '31683': (5, 44, '66774', '31897', 77, 'booleans'),
 '39762': (5, 17, '5074', '39765', 40, 'booleans'),
 '40872': (1, 9, '7379', '40899', 10, 'floats'),
 '40979': (1, 10, '7264', '40982', 10, 'floats'),
 '42602': (0, 9, '7379', '42605', 10, 'floats'),
 '42997': (4, 44, '66774', '43000', 77, 'booleans'),
 '43022': (4, 36, '71105', '43025', 29, 'booleans'),
 '43106': (5, 36, '71105', '43109', 29, 'booleans'),
 '51349': (0, 10, '7264', '51352', 10, 'floats')}
BUNDLES={'42583': (0,
           '42602',
           '42588',
           '42585',
           (('42589', None, 0.0, '40767'),
            ('47761', 1, 0.0, '40767'),
            ('47766', 2, 0.0, '40767'),
            ('47769', 3, 0.0, '40767'),
            ('47772', 4, 0.0, '40767'),
            ('47775', 5, 0.0, '40767'),
            ('47778', 6, 0.0, '40767'),
            ('47781', 7, 0.0, '40767'),
            ('47787', 9, 0.0, '40767'))),
 '42975': (4,
           '42997',
           '42980',
           '42977',
           (('42981', 65, False, '42907'),
            ('42984', 58, False, '42917'),
            ('42987', 64, False, '42927'),
            ('42990', 67, True, '42937'),
            ('42993', 61, False, '42957'))),
 '43011': (4, '43022', '43016', '43013', (('43017', 23, False, '42947'),)),
 '51315': (0,
           '51349',
           '51320',
           '51317',
           (('51321', None, 0.0, '40767'),
            ('1950', 1, 0.0, '40767'),
            ('31723', 3, 0.0, '40767'),
            ('31726', 4, 0.0, '40767'),
            ('31729', 5, 0.0, '40767'),
            ('31732', 6, 0.0, '40767'),
            ('31735', 7, 0.0, '40767'),
            ('31738', 8, 0.0, '40767'),
            ('31741', 9, 0.0, '40767'))),
 '8899': (3,
          '30243',
          '8914',
          '8905',
          (('8917', 9, False, '31686'),
           ('15638', 11, False, '31686'),
           ('17368', 15, False, '31686'),
           ('30231', 17, False, '31686'),
           ('32805', 21, False, '31686'),
           ('32819', 23, False, '31686'),
           ('32822', 25, False, '31686'),
           ('32825', 27, False, '31686'),
           ('32828', 29, False, '31686'),
           ('32831', 31, False, '31686'),
           ('44359', 32, False, '31686'),
           ('44364', 33, False, '31686'),
           ('44367', 34, False, '31686'),
           ('44370', 35, False, '31686'),
           ('44373', 36, False, '31686'),
           ('44376', 37, False, '31686'),
           ('44379', 38, False, '31686'),
           ('44382', 39, False, '31686')))}
WRITES={'1953': (3, 17, '5074', '8700', '8899'),
 '42565': (0, 9, '7379', '42568', '42583'),
 '42608': (0, 35, '9101', '42611', None),
 '42967': (4, 44, '66774', '42970', '42975'),
 '43003': (4, 36, '71105', '43006', '43011'),
 '51300': (0, 10, '7264', '51307', '51315')}
LEAVES={'31968': 5, '31985': 5, '39791': 5, '40868': 6, '40987': 1, '41020': 1, '41037': 1, '42649': 2, '43112': 5}
LEAF_INPUTS={'31968': (('31970', 'reference', '31950', None),
           ('31976', 'return', '43112', '43124'),
           ('31982', 'read', '31683', None)),
 '31985': (('32060', 'unwired', 'opaque', None),
           ('32064', 'unwired', 'I32', None),
           ('32067', 'unwired', 'string', None),
           ('32079', 'unwired', 'U16', None),
           ('32082', 'return', '31968', '31979')),
 '39791': (('39793', 'reference', '39773', None),
           ('39799', 'unwired', 'error', None),
           ('39805', 'read', '39762', None)),
 '40868': (('40877', 'literal', '40885', 200),),
 '40987': (('40996', 'unwired', 'opaque', None),
           ('40999', 'unwired', 'I32', None),
           ('41002', 'unwired', 'string', None),
           ('41014', 'unwired', 'U16', None),
           ('41017', 'return', '41037', '41048')),
 '41020': (('41022', 'reference', '40910', None),
           ('41028', 'unwired', 'error', None),
           ('41034', 'read', '40872', None)),
 '41037': (('41039', 'reference', '40930', None),
           ('41045', 'return', '41020', '41031'),
           ('41051', 'read', '40979', None)),
 '42649': (('42654', 'literal', '42636', 1000),),
 '43112': (('43114', 'reference', '43080', None),
           ('43121', 'return', '39791', '39802'),
           ('43127', 'read', '43106', None))}
LEAF_OUTPUTS={'31968': (('31973', 'opaque'), ('31979', 'error')),
 '31985': (('31998', 'boolean'), ('32055', 'I32'), ('32070', 'string'), ('32073', 'error'), ('32076', 'string')),
 '39791': (('39796', 'opaque'), ('39802', 'error')),
 '40868': (('40874', 'U32'),),
 '40987': (('40990', 'boolean'), ('40993', 'I32'), ('41005', 'string'), ('41008', 'error'), ('41011', 'string')),
 '41020': (('41025', 'opaque'), ('41031', 'error')),
 '41037': (('41042', 'opaque'), ('41048', 'error')),
 '42649': (('42651', 'U32'),),
 '43112': (('43118', 'opaque'), ('43124', 'error'))}
CONSUMED_OUTPUTS={'31968': ('31979',),
 '31985': (),
 '39791': ('39802',),
 '40868': (),
 '40987': (),
 '41020': ('41031',),
 '41037': ('41048',),
 '42649': (),
 '43112': ('43124',)}
REFERENCE_URIS={'31950': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS',
 '39773': 'ni.var.psp://10.20.30.2/SUPERVISION/C3_OUT_DIO96',
 '40910': 'ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703',
 '40930': 'ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703',
 '43080': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}
STAGES=('42539', '39882', '35750', '1926', '42901', '41314', '44333')
REQUIRED=(('42565', '42583', '42602', '42608', '51300', '51315', '51349'),
 ('40872', '40979', '40987', '41020', '41037'),
 ('42649',),
 ('1953', '30243', '8899'),
 ('42967', '42975', '42997', '43003', '43011', '43022'),
 ('31683', '31968', '31985', '39762', '39791', '43106', '43112'),
 ('40868',))
CONSTANTS=((('40767', 0.0), ('42555', True)),
 (('40910', 'ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703'), ('40930', 'ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703')),
 (('42636', 1000),),
 (('31686', False),),
 (('42907', False), ('42917', False), ('42927', False), ('42937', True), ('42947', False), ('42957', False)),
 (('31950', 'ni.var.psp://10.20.30.2/SUPERVISION/EPS'),
  ('39773', 'ni.var.psp://10.20.30.2/SUPERVISION/C3_OUT_DIO96'),
  ('43080', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS')),
 (('40885', 200),))
CASE_UID='42497'
SEQUENCE_UID='42523'
EVENT_DATA_UID='42473'
TRUE_FRAME='42517'
FALSE_FRAME='42511'
NEWVAL_FACE='42490'
EVENT_INPUT_FACES=('42475',)
EVENT_UNUSED_FACES=('42478', '42481', '42484', '42487')
SEQUENCE_UNUSED_FACES=('42528', '39889', '35757', '1946', '42535', '41321', '44340')
OUTER_CONSTANT_UID='43183'
MAX_TOKENS=46
ABSENT_FIELD_INDICES={'42589': 0, '51321': 0}
SUPPLIED_LITERAL_CARRIERS={'31686': False, '40767': 0.0, '42907': False, '42917': False, '42927': False, '42947': False, '42957': False}
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
        scope='SUPPLIED_ACQ_FRAME42457_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
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
    r['log'].append(dict(kind='unused_outer_carrier',node_uid=OUTER_CONSTANT_UID,value=150,case_faces=('42504','42508'),sequence_input_face='42525',unused_sequence_faces=SEQUENCE_UNUSED_FACES,native_forwarding_qualified=False))
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

def replay_saved_acq_event_42457(payload):
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
