"""Saved stop-local transitions;Python3.4 supplied traces,no scheduler/PSP."""
from collections import namedtuple

RUNTIME_LOOPS=('47483','59483','20601','203','102')
ERROR_SITES={
    '28682':('20601',(('43027',30,True),('43040',45,True))),
    '40346':('203',(('50011',30,True),('50019',45,True))),
    '40205':('102',(('85095',30,False),('68231',45,False))),
}
STOP_RESETS={'post_init':((45,False),(46,False)),
    'controlled_complete':((46,True),(47,False)),'final_cleanup':((30,False),)}
STOP_FIELDS={30:'stop',45:'tcp_ed',46:'emergency_stop',47:'general_stop'}
StopMemory=namedtuple('StopMemory','stop tcp_ed emergency_stop general_stop')
StopResetProjection=namedtuple('StopResetProjection','independent_assignments after')
NextIteration=namedtuple('NextIteration','loop_uid')
SuppliedStopChange=namedtuple('SuppliedStopChange','value')
ErrorArmEntry=namedtuple('ErrorArmEntry','selector_uid')
LocalAssignment=namedtuple('LocalAssignment','node_uid')
StopLocalRead=namedtuple('StopLocalRead','loop_uid')
BodyCompleted=namedtuple('BodyCompleted','loop_uid')
OuterTcpRead=namedtuple('OuterTcpRead','')
IterationDecision=namedtuple('IterationDecision','loop_uid iteration sampled_stop')
RuntimeStopTrace=namedtuple('RuntimeStopTrace','stop_after tcp_after decisions exited_loops next_iteration_ready inflight_loops pending_snapshots outer_tcp_snapshot')


def project_stop_reset(stage,before):
    if type(stage) is not str or stage not in STOP_RESETS:
        raise ValueError('Known saved reset stage required')
    if type(before) is not StopMemory or any(type(value) is not bool for value in before):
        raise TypeError('Four explicit Boolean StopMemory fields required')
    assignments=STOP_RESETS[stage]
    after=before._replace(**{STOP_FIELDS[bank]:value for bank,value in assignments})
    return StopResetProjection(assignments,after)


def replay_runtime(schedule, *, stop_before, tcp_before):
    """Consume explicit partial-order tokens across any finite fixture trace.

    All five first iterations are available after runtime-frame entry. A
    False completed condition only enables a supplied NextIteration token;
    it does not schedule it. A True condition makes that loop absorbing.
    Error arms may recur in later iterations. Both writes must finish before
    their owner body completes; their relative order is unspecified. Other
    loops may keep captured values even after the shared stop flag changes.

    No fairness, external-call completion, next-iteration latency, restart
    semantics or physical stop is inferred. I32 loop-index overflow is outside
    this model. A trace may end with unfinished calls/assignments.
    """
    if type(stop_before) is not bool or type(tcp_before) is not bool:
        raise TypeError("explicit Boolean stop/TCP snapshots required")
    stop, tcp = stop_before, tcp_before
    status = dict.fromkeys(RUNTIME_LOOPS, "inflight")
    iteration = dict.fromkeys(RUNTIME_LOOPS, 0)
    entered, assigned, snapshots = set(), set(), {}
    snapshot_order = []
    decisions = []
    outer = None
    writers = {
        node: (case, owner, bank, value)
        for case, (owner, writes) in ERROR_SITES.items()
        for node, bank, value in writes
    }

    def open_body(loop):
        if loop not in status or status[loop] != "inflight":
            raise ValueError("known inflight runtime body required")

    for item in schedule:
        if outer is not None:
            raise ValueError("runtime trace ends at the outer TCP read")
        if type(item) is NextIteration:
            loop = item.loop_uid
            if loop not in status or status[loop] != "next":
                raise ValueError("next iteration requires a completed False condition")
            if iteration[loop] == 2147483647:
                raise ValueError("I32 loop-index overflow is not qualified")
            iteration[loop] += 1
            status[loop] = "inflight"
            for case, (owner, writes) in ERROR_SITES.items():
                if owner == loop:
                    entered.discard(case)
                    assigned.difference_update(node for node, _, _ in writes)
        elif type(item) is ErrorArmEntry:
            case = item.selector_uid
            if case not in ERROR_SITES or case in entered:
                raise ValueError(
                    "one known error arm entry per owner iteration required"
                )
            open_body(ERROR_SITES[case][0])
            entered.add(case)
        elif type(item) is LocalAssignment:
            node = item.node_uid
            if node not in writers or node in assigned:
                raise ValueError(
                    "one known local assignment per owner iteration required"
                )
            case, owner, bank, value = writers[node]
            open_body(owner)
            if case not in entered:
                raise ValueError("local assignment requires its error arm entry")
            assigned.add(node)
            if bank == 30:
                stop = value
            else:
                tcp = value
        elif type(item) is StopLocalRead:
            loop = item.loop_uid
            open_body(loop)
            if loop in snapshots:
                raise ValueError("one stop snapshot per runtime iteration required")
            snapshots[loop] = stop
            snapshot_order.append(loop)
        elif type(item) is BodyCompleted:
            loop = item.loop_uid
            open_body(loop)
            if loop not in snapshots:
                raise ValueError("body completion requires a condition snapshot")
            required = {
                node
                for case in entered
                if ERROR_SITES[case][0] == loop
                for node, _, _ in ERROR_SITES[case][1]
            }
            if not required <= assigned:
                raise ValueError("entered error-arm writes must finish with their body")
            captured = snapshots.pop(loop)
            snapshot_order.remove(loop)
            decisions.append(IterationDecision(loop, iteration[loop], captured))
            status[loop] = "exited" if captured else "next"
        elif type(item) is SuppliedStopChange:
            if type(item.value) is not bool:
                raise TypeError("explicit external Boolean stop snapshot required")
            stop = item.value
        elif type(item) is OuterTcpRead:
            if any(value != "exited" for value in status.values()):
                raise ValueError(
                    "outer TCP read requires all five runtime loops to exit"
                )
            outer = tcp
        else:
            raise TypeError("known inert multi-iteration token required")
    return RuntimeStopTrace(
        stop,
        tcp,
        tuple(decisions),
        tuple(loop for loop in RUNTIME_LOOPS if status[loop] == "exited"),
        tuple(loop for loop in RUNTIME_LOOPS if status[loop] == "next"),
        tuple(loop for loop in RUNTIME_LOOPS if status[loop] == "inflight"),
        tuple((loop, iteration[loop], value) for loop in snapshot_order for value in (snapshots[loop],)),
        outer,
    )


TOKEN_FIELDS={'error_arm':(ErrorArmEntry,'selector_uid'),'assignment':(LocalAssignment,'node_uid'),
    'read_stop':(StopLocalRead,'loop_uid'),'body_completed':(BodyCompleted,'loop_uid'),
    'next_iteration':(NextIteration,'loop_uid'),'supplied_stop_change':(SuppliedStopChange,'value')}


def replay_saved_stop(payload):
    if type(payload) is not dict or payload.get('source_id')!='APP-00':
        raise ValueError('APP-00 stop replay required')
    facet=payload.get('facet')
    if facet=='reset':
        if set(payload)!=set(('source_id','facet','stage','before')):
            raise ValueError('Exact reset replay fields required')
        value=payload['before']
        if type(value) is not dict or set(value)!=set(StopMemory._fields):
            raise ValueError('Four explicit stop memory fields required')
        result=project_stop_reset(payload['stage'],StopMemory(**value))
        output=dict(independent_assignments=list(result.independent_assignments),after=dict(result.after._asdict()))
    elif facet=='runtime_trace':
        if set(payload)!=set(('source_id','facet','stop_before','tcp_before','schedule')):
            raise ValueError('Exact runtime trace fields required')
        rows=payload['schedule']
        if type(rows) is not list or len(rows)>10000:
            raise ValueError('Bounded explicit token schedule required')
        schedule=[]
        for row in rows:
            if type(row) is not dict or type(row.get('kind')) is not str:
                raise ValueError('Explicit token object required')
            kind=row['kind']
            if kind=='outer_tcp_read':
                if set(row)!=set(('kind',)):raise ValueError('Exact outer read token required')
                schedule.append(OuterTcpRead())
            elif kind in TOKEN_FIELDS:
                cls,key=TOKEN_FIELDS[kind]
                if set(row)!=set(('kind',key)):raise ValueError('Exact token fields required')
                schedule.append(cls(row[key]))
            else:raise ValueError('Unknown replay token')
        result=replay_runtime(schedule,stop_before=payload['stop_before'],tcp_before=payload['tcp_before'])
        output=dict(result._asdict());output['decisions']=[dict(d._asdict()) for d in result.decisions]
    else:raise ValueError('Known saved stop facet required')
    output.update(source_id='APP-00',facet=facet,scope='SUPPLIED_STOP_LOCAL_TRANSITIONS',
        body_completion_and_error_arm_entry_supplied=True,execution_allowed=False,external_calls_executed=False,
        hardware_writes=False,scheduler_or_fairness_qualified=False,psp_delivery_qualified=False,
        native_default_qualified=False,atomic_local_pairs_qualified=False,physical_stop_qualified=False,
        transport_epoch_qualified=False,whole_lifecycle_equivalence=False)
    return output
