"""Saved APP-00 final frame246 partial-order routing; no physical close calls.

Every returned error is supplied. A completed call node does not establish
resource-close success. The uninitialized PSP error register needs a seed.
"""
from collections import namedtuple
from .saved_initializer import OpaqueReference, UNWIRED, require_error, json_error, exact, encode_error

VARIABLES = (
    'C1NI6071E','C2NI6071E','C3_IN_DIO96','C3_OUT_DIO96','C4_IN_DIO96','C4_OUT_DIO96',
    'C5_IN_DIO96','C5_OUT_DIO96','C6NI6703','C7NI6703','C8NI6703','C9NI6703','C1011NI6602',
    'C12NI1409','DPC','DPS','EPC','EPS','VAM-A','VAD','VAM-S','VDD','VDM-A','VDM-S','VTA','VTL','VTS',
)
FIXED_PSP_TAGS=tuple('ni.var.psp://10.20.30.2/SUPERVISION/'+name for name in VARIABLES)
TPG_BRANCHES={51:('61121','68680'),52:('66474','67965')}
PSP_HANDLER='88'
CleanupEvent=namedtuple('CleanupEvent','kind argument')
CleanupState=namedtuple('CleanupState','psp_error_seed psp_error_after psp_index tpg_errors handlers stop_reset stop_after frame_returned')
CleanupPlan=namedtuple('CleanupPlan','event node_uid diagram_uid operation iteration task_in error_in arguments')
CleanupCall=namedtuple('CleanupCall','plan returned_error')
CleanupResult=namedtuple('CleanupResult','state calls')


def begin_cleanup(psp_error_seed,stop_before):
    """Typed facades supply validated errors and Boolean snapshot."""
    return CleanupState(psp_error_seed,psp_error_seed,0,(),(),False,stop_before,False)


def cleanup_ready(state):
    return (state.psp_index==len(FIXED_PSP_TAGS) and {b for b,e in state.tpg_errors}==set(TPG_BRANCHES)
            and set(state.handlers)=={PSP_HANDLER}|{row[1] for row in TPG_BRANCHES.values()} and state.stop_reset)


def plan_cleanup_step(state,event,sessions,unwired):
    """Validate wired precedence and expose an inert call descriptor, never call it."""
    if state.frame_returned:
        raise ValueError('cleanup trace ends at frame return')
    if type(event) is not CleanupEvent:
        raise TypeError('known inert cleanup token required')
    kind,arg=event
    if kind=='psp_close':
        if type(arg) is not int or arg!=state.psp_index or arg>=len(FIXED_PSP_TAGS):
            raise ValueError('next fixed PSP close index required')
        return CleanupPlan(event,'536','1760','close_variable_reference',arg,unwired,state.psp_error_after,
                           (('variable_uri',FIXED_PSP_TAGS[arg]),('reference_source','fixed_uri_tag')))
    if kind=='tpg_close':
        if type(arg) is not int or arg not in TPG_BRANCHES or arg in dict(state.tpg_errors):
            raise ValueError('one known TPG branch per cleanup required')
        return CleanupPlan(event,TPG_BRANCHES[arg][0],'246','tpg300_close',None,sessions[arg-51],unwired,
                           (('input_local_bank',arg),('error_connection','unwired')))
    if kind=='handler':
        if arg in state.handlers:
            raise ValueError('one handler return per branch required')
        if arg==PSP_HANDLER:
            if state.psp_index!=len(FIXED_PSP_TAGS):
                raise ValueError('PSP handler requires all 27 close-node returns')
            error=state.psp_error_after
        else:
            branches=[bank for bank,row in TPG_BRANCHES.items() if row[1]==arg]
            if len(branches)!=1 or branches[0] not in dict(state.tpg_errors):
                raise ValueError('known handler requires its TPG close return')
            error=dict(state.tpg_errors)[branches[0]]
        return CleanupPlan(event,arg,'246','simple_error_handler',None,unwired,error,
                           (('mode_connection','unwired'),('outputs_connection','unused')))
    if kind=='stop_reset':
        if arg is not None:
            raise ValueError('stop reset has no argument')
        if state.stop_reset:
            raise ValueError('one local30 reset per cleanup required')
    elif kind=='frame_returned':
        if arg is not None:
            raise ValueError('frame return has no argument')
        if not cleanup_ready(state):
            raise ValueError('all cleanup branches must return')
    else:
        raise TypeError('known inert cleanup token required')
    return CleanupPlan(event,None,'246',None,None,unwired,unwired,())


def commit_cleanup_step(state,plan,returned_error):
    """Commit only the supplied node return; handler outputs never enter register."""
    kind,arg=plan.event
    if kind=='psp_close':
        return state._replace(psp_index=state.psp_index+1,psp_error_after=returned_error)
    if kind=='tpg_close':
        return state._replace(tpg_errors=state.tpg_errors+((arg,returned_error),))
    if kind=='handler':
        return state._replace(handlers=state.handlers+(arg,))
    if kind=='stop_reset':
        return state._replace(stop_reset=True,stop_after=False)
    return state._replace(frame_returned=True)


def project_cleanup(schedule,psp_error_seed,tpg_sessions,stop_before,returned_errors):
    require_error(psp_error_seed)
    if type(stop_before) is not bool:
        raise TypeError('explicit Boolean stop snapshot required')
    if type(schedule) is not tuple or any(type(e) is not CleanupEvent for e in schedule):
        raise TypeError('immutable inert cleanup schedule required')
    if type(tpg_sessions) is not tuple or len(tpg_sessions)!=2 or any(
            type(t) is not OpaqueReference or type(t.token) is not str or not t.token for t in tpg_sessions):
        raise TypeError('two explicit opaque TPG session fixtures required')
    if type(returned_errors) is not dict:
        raise TypeError('explicit return dictionary required')
    for value in returned_errors.values():
        require_error(value)
    state=begin_cleanup(psp_error_seed,stop_before)
    calls=[]
    used=set()
    for event in schedule:
        plan=plan_cleanup_step(state,event,tpg_sessions,UNWIRED)
        returned=None
        if plan.operation is not None:
            key=(plan.node_uid,plan.iteration)
            if key not in returned_errors:
                raise ValueError('explicit selected node return required')
            returned=returned_errors[key]
            used.add(key)
            calls.append(CleanupCall(plan,returned))
        state=commit_cleanup_step(state,plan,returned)
    if used!=set(returned_errors):
        raise ValueError('returned fixtures must match selected call nodes exactly')
    return CleanupResult(state,tuple(calls))


def json_event(value):
    if type(value) is not dict:
        raise ValueError('exact inert event dictionary required')
    kind=value.get('kind')
    if kind in ('stop_reset','frame_returned'):
        exact(value,('kind',))
        return CleanupEvent(kind,None)
    field='index' if kind=='psp_close' else 'bank' if kind=='tpg_close' else 'node_uid' if kind=='handler' else None
    if field is None:
        raise ValueError('known cleanup event kind required')
    exact(value,('kind',field))
    argument=value[field]
    if kind=='handler' and type(argument) is not str:
        raise ValueError('handler UID requires string')
    return CleanupEvent(kind,argument)


def encode_call(call):
    plan=call.plan
    task=dict(connection='unwired') if plan.task_in is UNWIRED else dict(token=plan.task_in.token)
    return dict(node_uid=plan.node_uid,diagram_uid=plan.diagram_uid,operation=plan.operation,
                iteration=plan.iteration,task_in=task,error_in=encode_error(plan.error_in),
                arguments=dict(plan.arguments),returned_error=encode_error(call.returned_error))


def replay_saved_cleanup(payload):
    exact(payload,('source_id','uid','outer_joined','stop_before','psp_error_seed','tpg_sessions','schedule','returned_errors'))
    if payload['source_id']!='APP-00' or payload['uid']!='246':
        raise ValueError('APP-00 final frame246 required')
    if payload['outer_joined'] is not True:
        raise ValueError('explicit supplied outer-join completion required')
    sessions=payload['tpg_sessions']
    if type(sessions) is not list or len(sessions)!=2 or any(type(t) is not str or not 1<=len(t)<=128 for t in sessions):
        raise ValueError('two bounded opaque session tokens required')
    schedule=payload['schedule']
    if type(schedule) is not list or len(schedule)>34:
        raise ValueError('bounded inert schedule required')
    returned=payload['returned_errors']
    if type(returned) is not list or len(returned)>32:
        raise ValueError('bounded explicit returned-error list required')
    returns={}
    for row in returned:
        exact(row,('node_uid','iteration','error'))
        if type(row['node_uid']) is not str or row['iteration'] is not None and type(row['iteration']) is not int:
            raise ValueError('exact node/iteration return identity required')
        key=(row['node_uid'],row['iteration'])
        if key in returns:
            raise ValueError('duplicate return identity')
        returns[key]=json_error(row['error'])
    result=project_cleanup(tuple(json_event(e) for e in schedule),json_error(payload['psp_error_seed']),
                           tuple(OpaqueReference(t) for t in sessions),payload['stop_before'],returns)
    state=result.state
    return dict(source_id='APP-00',uid='246',scope='SUPPLIED_RETURN_CLEANUP_ROUTING',
            outputs=dict(psp_error_seed=encode_error(state.psp_error_seed),psp_error_after=encode_error(state.psp_error_after),
                returned_psp_close_nodes=state.psp_index,returned_tpg_close_nodes=sorted(b for b,e in state.tpg_errors),
                returned_handlers=sorted(state.handlers),stop_reset=state.stop_reset,stop_after=state.stop_after,
                frame_ready=cleanup_ready(state),frame_returned=state.frame_returned),
            calls=[encode_call(c) for c in result.calls],outer_join_supplied=True,
            execution_allowed=False,hardware_writes=False,external_calls_executed=False,
            resource_close_success_qualified=False,reference_validity_qualified=False,whole_lifecycle_equivalence=False)
