"""Original APP00/Event43/frame45123 bounded supplied-body replay, Python3.4.

Case, Sequence, positional unbundle/bundles and local access are direct.
Native/callee leaves never run. Every unwired argument, return and leaf
completion is supplied; no Clear Errors or DAQmx behavior is inferred.
"""
from collections import namedtuple

SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='45123'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
STAGES=('45203','45276','45385','45576')
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')

READS={
    '50001':(0,21,'944','50008',8,'opaque_refs'),
    '45333':(1,44,'66774','45336',77,'booleans'),
    '45357':(1,36,'71105','45360',29,'booleans'),
    '45445':(2,36,'71105','45448',29,'booleans'),
    '45469':(2,44,'66774','45472',77,'booleans'),
}
UNBUNDLES={'49179':(0,'50001','49185',(('49188',3),('51935',4)))}
BUNDLES={
    '45320':(1,'45333','45325','45322',(('45326',55,False,'45282'),('45329',52,True,'45292'))),
    '45347':(1,'45357','45352','45349',(('45353',18,False,'45302'),)),
}
WRITES={
    '45254':(0,35,'9101','45257',None),
    '45312':(1,44,'66774','45315','45320'),
    '45339':(1,36,'71105','45342','45347'),
}
LEAVES={'46267':0,'52872':0,'54874':0,'2548':0,'45451':2,'45475':2,'45515':2,'45594':3}
# (input terminal, wire producer kind, producer UID, producer face or value).
# Only leaf arguments are described by plans; business structure is direct.
LEAF_INPUTS={
    '46267':(('46274','unbundle','49179','49188'),
        ('46277','unwired','opaque',None),('46280','unwired','opaque',None),
        ('46283','unwired','opaque',None),('46289','unwired','opaque',None),
        ('46292','unwired','opaque',None),('46295','unwired','opaque',None),
        ('46298','unwired','opaque',None),('46301','unwired','opaque',None),
        ('46304','unwired','opaque',None),('46307','unwired','error',None),
        ('46310','unwired','opaque',None),('46313','unwired','opaque',None),('46316','unwired','opaque',None)),
    '52872':(('52882','unwired','opaque',None),('52885','unwired','opaque',None),
        ('52888','unwired','opaque',None),('52891','return','46267','46319'),
        ('52894','unwired','opaque',None),('52897','unwired','opaque',None),('52900','unwired','opaque',None)),
    '54874':(('54881','unbundle','49179','51935'),
        ('54884','unwired','opaque',None),('54887','unwired','opaque',None),
        ('54890','unwired','opaque',None),('54896','unwired','opaque',None),
        ('54899','unwired','opaque',None),('54902','unwired','opaque',None),
        ('54905','unwired','opaque',None),('54908','unwired','opaque',None),
        ('54911','unwired','opaque',None),('54914','return','52872','52879'),
        ('54917','unwired','opaque',None),('54920','unwired','opaque',None),('54923','unwired','opaque',None)),
    '2548':(('20494','unwired','opaque',None),('20501','unwired','opaque',None),
        ('20504','unwired','opaque',None),('20510','return','54874','54926'),
        ('20513','unwired','opaque',None),('20518','unwired','opaque',None),('20521','unwired','opaque',None)),
    '45451':(('45453','reference','45391',None),('45460','unwired','error',None),('45466','read','45445',None)),
    '45475':(('45477','reference','45409',None),('45483','return','45451','45463'),('45489','read','45469',None)),
    '45515':(('45524','unwired','opaque',None),('45527','unwired','I32',None),
        ('45530','unwired','string',None),('45542','unwired','U16',None),('45545','return','45475','45486')),
    '45594':(('45599','literal','45582',100),),
}
LEAF_OUTPUTS={
    '46267':(('46286','opaque'),('46319','error')),
    '52872':(('52879','error'),),
    '54874':(('54893','opaque'),('54926','error')),
    '2548':(('20485','error'),),
    '45451':(('45457','opaque'),('45463','error')),
    '45475':(('45480','opaque'),('45486','error')),
    '45515':(('45518','boolean'),('45521','I32'),('45533','string'),('45536','error'),('45539','string')),
    '45594':(('45596','U32'),),
}
CONSUMED_OUTPUTS={'46267':('46319',),'52872':('52879',),'54874':('54926',),'2548':(),
    '45451':('45463',),'45475':('45486',),'45515':(),'45594':()}
REFERENCE_URIS={'45391':'ni.var.psp://10.20.30.2/SUPERVISION/DPS',
                '45409':'ni.var.psp://10.20.30.2/SUPERVISION/EPS'}
REQUIRED=(frozenset(('50001','49179','46267','52872','54874','2548','45254')),
          frozenset(('45333','45320','45312','45357','45347','45339')),
          frozenset(('45445','45451','45469','45475','45515')),frozenset(('45594',)))
CONSTANTS=((('45220',True),),(('45282',False),('45292',True),('45302',False)),
           (('45391',REFERENCE_URIS['45391']),('45409',REFERENCE_URIS['45409'])),(('45582',100),))
LIMITS=dict(execution_allowed=False,external_calls_executed=False,hardware_writes=False,
    native_runtime_equivalence=False,native_callee_equivalence=False,whole_event_equivalence=False,
    whole_vi_equivalence=False,native_default_qualified=False,native_ref_interpretation_qualified=False,
    native_task_reference_qualified=False,psp_delivery_qualified=False,wait_units_or_pulse_duration_qualified=False,
    snapshot_equality_qualified=False,scheduler_qualified=False,event_selection_qualified=False,
    event_acknowledgement_qualified=False,native_cluster_decode_qualified=False)

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
        scope='SUPPLIED_ACQ_FRAME45123_BODY',new_value=new_value,selected_case_frame='45183'if new_value else'45177',
        event_data_consumed_ports=('45156',),event_data_unconsumed_input_ports=('45141',),
        event_data_unconsumed_ports=('45144','45147','45150','45153'),
        unconsumed_sequence_input_faces=('45194','45195','45196','45197'),
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid='45139',terminal_uid='45156',value=new_value),
        dict(kind='constant',node_uid='45611',value=150),dict(kind='case',node_uid='45163',selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>31:raise ValueError('bounded tuple of inert source tokens required')
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid='45189',stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS))
    enter(0)
    for token in schedule:
        if stage==4:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid='45189'))
            stage+=1
            if stage<4:enter(stage)
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
            elif uid in UNBUNDLES:
                owner,read,base,fields=UNBUNDLES[uid]
                if stage!=owner or read not in done:raise ValueError('unbundle requires completed saved task snapshot')
                outputs={face:values[read][index]for face,index in fields};values[uid]=outputs
                r['log'].append(dict(kind='unbundle',node_uid=uid,input_ports={base:values[read]},output_ports=outputs,
                    selections=[dict(terminal_uid=face,field_index=index)for face,index in fields]))
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
                elif kind=='unbundle':
                    if producer not in done:raise ValueError('DAQmx leaf requires direct task unbundle')
                    v=values[producer][port]
                elif kind=='read':
                    if producer not in done:raise ValueError('PSP leaf requires separate fresh source snapshot')
                    v=values[producer]
                elif kind=='reference':v=_binding(reference_bindings,producer)
                else:v=port
                inputs[face]=v
            started.add(uid);row=dict(kind='leaf_call',node_uid=uid,input_ports=inputs,input_port_order=tuple(x[0]for x in LEAF_INPUTS[uid]),
                unwired_input_ports=tuple(unwired),supplied_ref_interpretation=uid in('45451','45475'))
            r['leaf_calls'].append(row);r['log'].append(row)
        else:
            if uid not in LEAVES or stage!=LEAVES[uid]or uid not in started or uid in done:raise ValueError('leaf return requires one started current leaf')
            v=_value(leaf_returns,uid,'supplied leaf return');_exact(v,[face for face,kind in LEAF_OUTPUTS[uid]],'leaf return')
            for face,kind in LEAF_OUTPUTS[uid]:_typed(v[face],kind)
            returned[uid]=v;done.add(uid);row=dict(kind='leaf_return',node_uid=uid,output_ports=v,
                consumed_output_ports=CONSUMED_OUTPUTS[uid],success_does_not_gate_stage=True)
            r['leaf_returns'].append(row);r['log'].append(row)
    r['active_stage']=STAGES[stage]if stage<4 else None
    r['pending_leaf_uids']=tuple(uid for uid in sorted(started)if uid not in done)
    r['remaining_node_uids']=tuple(sorted(REQUIRED[stage]-done))if stage<4 else()
    r['selected_body_completed']=r['schedule_complete']=stage==4
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

def replay_saved_acq_event_45123(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>31:raise ValueError('bounded JSON token list required')
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
