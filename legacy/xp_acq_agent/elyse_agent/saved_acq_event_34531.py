"""Original APP00/Event43/frame34531 bounded direct ten-stage body.
Native/callee leaves explicitly supplied; absent indices and raw0000 values hypothetical.
Stdlib Python3.4; native/default/scheduler/whole equivalence unqualified.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='34531'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={'25217': (4, 15, '5994', '25266', 32, 'booleans'),
 '32017': (6, 15, '5994', '32020', 32, 'booleans'),
 '33251': (7, 15, '5994', '33254', 32, 'booleans'),
 '34742': (0, 15, '5994', '34751', 32, 'booleans'),
 '34957': (1, 15, '5994', '34966', 32, 'booleans'),
 '35075': (3, 15, '5994', '35078', 32, 'booleans'),
 '35509': (8, 44, '66774', '35512', 77, 'booleans'),
 '35533': (8, 36, '71105', '35536', 29, 'booleans'),
 '35614': (9, 36, '71105', '35617', 29, 'booleans')}
BUNDLES={'25168': (4, '25217', '25196', '25179', (('25197', 2, False, '25728'),)),
 '32007': (6, '32017', '32012', '32009', (('32013', 2, True, '32033'),)),
 '33241': (7, '33251', '33246', '33243', (('33247', 2, False, '33267'),)),
 '34714': (0, '34742', '34726', '34717', (('34732', None, True, '34627'),)),
 '34924': (1, '34957', '34940', '34931', (('34942', None, False, '34877'),)),
 '35065': (3, '35075', '35070', '35067', (('35071', 2, True, '35049'),)),
 '35487': (8,
           '35509',
           '35492',
           '35489',
           (('35493', 11, False, '35419'), ('35496', 8, True, '35429'), ('23461', 6, False, '32614'))),
 '35523': (8, '35533', '35528', '35525', (('35529', 2, False, '35459'),))}
WRITES={'25108': (4, 15, '5994', '25125', '25168'),
 '31999': (6, 15, '5994', '32002', '32007'),
 '33233': (7, 15, '5994', '33236', '33241'),
 '34688': (0, 15, '5994', '34697', '34714'),
 '34760': (0, 35, '9101', '34769', None),
 '34906': (1, 15, '5994', '34915', '34924'),
 '35059': (3, 15, '5994', '35062', '35065'),
 '35479': (8, 44, '66774', '35482', '35487'),
 '35515': (8, 36, '71105', '35518', '35523')}
LEAVES={'29271': 5, '32023': 6, '34786': 0, '35031': 2, '35081': 3, '35606': 9, '35620': 9, '35637': 9}
LEAF_INPUTS={'29271': (('29308', 'literal', '29319', 1000),),
 '32023': (('32028', 'border', '31996', None),),
 '34786': (('34798', 'border', '34602', None),),
 '35031': (('35036', 'literal', '35019', 1000),),
 '35081': (('35086', 'border', '34605', None),),
 '35606': (('35611', 'literal', '35576', 100),),
 '35620': (('35622', 'reference', '35588', None),
           ('35628', 'unwired', 'error', None),
           ('35634', 'read', '35614', None)),
 '35637': (('35646', 'unwired', 'opaque', None),
           ('35649', 'unwired', 'I32', None),
           ('35652', 'unwired', 'string', None),
           ('35664', 'unwired', 'U16', None),
           ('35667', 'return', '35620', '35631'))}
LEAF_OUTPUTS={'29271': (('29299', 'U32'),),
 '32023': (('32025', 'U32'),),
 '34786': (('34789', 'U32'),),
 '35031': (('35033', 'U32'),),
 '35081': (('35083', 'U32'),),
 '35606': (('35608', 'U32'),),
 '35620': (('35625', 'opaque'), ('35631', 'error')),
 '35637': (('35640', 'boolean'), ('35643', 'I32'), ('35655', 'string'), ('35658', 'error'), ('35661', 'string'))}
CONSUMED_OUTPUTS={'29271': (), '32023': (), '34786': (), '35031': (), '35081': (), '35606': (), '35620': ('35631',), '35637': ()}
REFERENCE_URIS={'35588': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}
STAGES=('34617', '34859', '35005', '35043', '25037', '29225', '31989', '33223', '35413', '35570')
REQUIRED=(('34688', '34714', '34742', '34760', '34786'),
 ('34906', '34924', '34957'),
 ('35031',),
 ('35059', '35065', '35075', '35081'),
 ('25108', '25168', '25217'),
 ('29271',),
 ('31999', '32007', '32017', '32023'),
 ('33233', '33241', '33251'),
 ('35479', '35487', '35509', '35515', '35523', '35533'),
 ('35606', '35614', '35620', '35637'))
CONSTANTS=((('34627', True), ('34660', True)),
 (('34877', False),),
 (('35019', 1000),),
 (('35049', True),),
 (('25728', False),),
 (('29319', 1000),),
 (('32033', True),),
 (('33267', False),),
 (('32614', False), ('35419', False), ('35429', True), ('35459', False)),
 (('35576', 100), ('35588', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS')))
BORDER_PATH=(('wire', '35689', '35689', '34571', '34578', '35702'),
 ('paired', '34571', '34578', '34582', '34579'),
 ('wire', '34571', '34582', '34597', '34599', '35684'),
 ('paired', '34597', '34599', '34602', '34600'),
 ('wire', '34597', '34602', '34786', '34798', '34814'),
 ('paired', '34597', '34599', '34605', '34600'),
 ('wire', '34597', '34605', '35081', '35086', '35091'),
 ('paired', '34597', '34599', '31996', '34600'),
 ('wire', '34597', '31996', '32023', '32028', '32043'))
BORDER_VALUES={'31996': 150, '34602': 150, '34605': 150}
CASE_UID='34571'
SEQUENCE_UID='34597'
EVENT_DATA_UID='34547'
TRUE_FRAME='34591'
FALSE_FRAME='34585'
NEWVAL_FACE='34564'
EVENT_INPUT_FACES=('34549',)
EVENT_UNUSED_FACES=('34552', '34555', '34558', '34561')
SEQUENCE_UNUSED_FACES=('34603', '34604', '25089', '29239', '33230', '34612', '34613')
OUTER_CONSTANT_UID='35689'
MAX_TOKENS=52
ABSENT_FIELD_INDICES={'34732': 0, '34942': 0}
SUPPLIED_LITERAL_CARRIERS={'25728': False, '32614': False, '33267': False, '34877': False, '35419': False, '35459': False}
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
        scope='SUPPLIED_ACQ_FRAME34531_BODY',new_value=new_value,selected_case_frame=TRUE_FRAME if new_value else FALSE_FRAME,
        event_data_consumed_ports=(NEWVAL_FACE,),event_data_unconsumed_input_ports=EVENT_INPUT_FACES,
        event_data_unconsumed_ports=EVENT_UNUSED_FACES,
        unconsumed_sequence_output_faces=SEQUENCE_UNUSED_FACES,
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid=EVENT_DATA_UID,terminal_uid=NEWVAL_FACE,value=new_value),
        dict(kind='constant',node_uid=OUTER_CONSTANT_UID,value=150),dict(kind='case',node_uid=CASE_UID,selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>MAX_TOKENS:raise ValueError('bounded tuple of inert source tokens required')
    r['log'].append(dict(kind='border_carrier',node_uid=OUTER_CONSTANT_UID,value=150,source_paths=BORDER_PATH,consumer_ports=BORDER_VALUES,native_forwarding_qualified=False))
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
                elif kind=='border':v=BORDER_VALUES[producer]
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

def replay_saved_acq_event_34531(payload):
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
