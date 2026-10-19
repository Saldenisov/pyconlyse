"""Original APP00/Event43/frame43634 direct bounded supplied-body replay.
Python3.4 stdlib only. Case/Sequence/bundles/local writes are direct.
Native leaves never run; all returns, unwired inputs and completion supplied.
"""
from collections import namedtuple
SOURCE_ID='APP-00'
EVENT_UID='43'
FRAME_UID='43634'
SOURCE_VERSION='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
STAGES=('43712','43785','43894','44089')
Step=namedtuple('Step','node_uid')
LeafCall=namedtuple('LeafCall','node_uid')
LeafReturn=namedtuple('LeafReturn','node_uid')
StageComplete=namedtuple('StageComplete','frame_uid')
ErrorValue=namedtuple('ErrorValue','status code source')
READS={
 '43757':(0,15,'5994','43760',32,'booleans'),
 '43842':(1,44,'66774','43845',77,'booleans'),
 '43866':(1,36,'71105','43869',29,'booleans'),
 '43956':(2,36,'71105','43959',29,'booleans'),
 '43979':(2,44,'66774','43982',77,'booleans'),
 '44002':(2,15,'5994','44005',32,'booleans'),
}
BUNDLES={
 '43746':(0,'43757','43752','43749',(('43753',29,False,'43718'),)),
 '43829':(1,'43842','43834','43831',(('43835',42,True,'43791'),('43838',39,False,'43801'))),
 '43856':(1,'43866','43861','43858',(('43862',14,False,'43811'),)),
}
WRITES={
 '43738':(0,15,'5994','43741','43746'),
 '43763':(0,35,'9101','43766',None),
 '43821':(1,44,'66774','43824','43829'),
 '43848':(1,36,'71105','43851','43856'),
}
LEAVES={'43962':2,'43985':2,'44008':2,'44025':2,'44107':3}
LEAF_INPUTS={
 '43962':(('43964','reference','43902',None),('43970','unwired','error',None),('43976','read','43956',None)),
 '43985':(('43987','reference','43920',None),('43993','return','43962','43973'),('43999','read','43979',None)),
 '44008':(('44010','reference','43938',None),('44016','return','43985','43996'),('44022','read','44002',None)),
 '44025':(('44034','unwired','opaque',None),('44037','unwired','I32',None),('44040','unwired','string',None),('44052','unwired','U16',None),('44055','return','44008','44019')),
 '44107':(('44112','literal','44095',100),),
}
LEAF_OUTPUTS={
 '43962':(('43967','opaque'),('43973','error')),
 '43985':(('43990','opaque'),('43996','error')),
 '44008':(('44013','opaque'),('44019','error')),
 '44025':(('44028','boolean'),('44031','I32'),('44043','string'),('44046','error'),('44049','string')),
 '44107':(('44109','U32'),),
}
CONSUMED_OUTPUTS={'43962':('43973',),'43985':('43996',),'44008':('44019',),'44025':(),'44107':()}
REFERENCE_URIS={'43902':'ni.var.psp://10.20.30.2/SUPERVISION/DPS','43920':'ni.var.psp://10.20.30.2/SUPERVISION/EPS','43938':'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96'}
REQUIRED=(frozenset(('43757','43746','43738','43763')),frozenset(('43842','43829','43821','43866','43856','43848')),frozenset(('43956','43979','44002','43962','43985','44008','44025')),frozenset(('44107',)))
CONSTANTS=((('43718',False),('43728',True)),(('43791',True),('43801',False),('43811',False)),(('43902',REFERENCE_URIS['43902']),('43920',REFERENCE_URIS['43920']),('43938',REFERENCE_URIS['43938'])),(('44095',100),))
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
        scope='SUPPLIED_ACQ_FRAME43634_BODY',new_value=new_value,selected_case_frame='43695'if new_value else'43689',
        event_data_consumed_ports=('43668',),event_data_unconsumed_input_ports=('43653',),
        event_data_unconsumed_ports=('43656','43659','43662','43665'),
        unconsumed_sequence_input_faces=('43706','43707','43708','43709'),
        log=[],writes=[],leaf_calls=[],leaf_returns=[],completed_stages=[],active_stage=None,
        pending_leaf_uids=(),remaining_node_uids=(),selected_body_completed=not new_value,schedule_complete=not new_value)
    r.update(LIMITS)
    r['log'].extend((dict(kind='event_value',node_uid='43651',terminal_uid='43668',value=new_value),
        dict(kind='constant',node_uid='44124',value=150),dict(kind='case',node_uid='43675',selected_frame=r['selected_case_frame'])))
    if not new_value:return r
    if type(schedule)is not tuple or len(schedule)>27:raise ValueError('bounded tuple of inert source tokens required')
    values,done,started,returned={},set(),set(),{};stage=0
    r['log'].append(dict(kind='sequence',node_uid='43701',stage_uids=STAGES))
    def enter(i):
        for uid,v in CONSTANTS[i]:r['log'].append(dict(kind='constant',node_uid=uid,value=v,saved_refnum_descriptor=uid in REFERENCE_URIS))
    enter(0)
    for token in schedule:
        if stage==4:raise ValueError('no token after completed body')
        if type(token)is StageComplete:
            if type(token.frame_uid)is not str or token.frame_uid!=STAGES[stage]:raise ValueError('current saved stage UID required')
            if not REQUIRED[stage]<=done:raise ValueError('all source nodes and supplied leaf returns required before stage completion')
            r['completed_stages'].append(token.frame_uid);r['log'].append(dict(kind='stage_complete',frame_uid=token.frame_uid,sequence_uid='43701'))
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
                else:v=port
                inputs[face]=v
            started.add(uid);row=dict(kind='leaf_call',node_uid=uid,input_ports=inputs,input_port_order=tuple(x[0]for x in LEAF_INPUTS[uid]),
                unwired_input_ports=tuple(unwired),supplied_ref_interpretation=uid in('43962','43985','44008'))
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

def replay_saved_acq_event_43634(payload):
    """Exact inert JSON adapter; False does not access unselected body values."""
    _exact(payload,('source_id','source_version','event_uid','frame_uid','new_value','schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'),'JSON replay')
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('exact saved source/version/body identity required')
    new=payload['new_value']
    if type(new)is not bool:raise TypeError('explicit Boolean NewVal required')
    if not new:return _json_tree(replay_event(False,None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None))
    rows=payload['schedule']
    if type(rows)is not list or len(rows)>27:raise ValueError('bounded JSON token list required')
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
