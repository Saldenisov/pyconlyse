"""APP-17 Event5909/frame70866: supplied-boundary positional body projection.

Only the eight saved body nodes are projected. Native event delivery, reference
decoding, unwired error semantics, writer returns and sink completion are supplied
boundaries. No transport, callbacks, UI, scheduler or hardware executor exists.
"""
from collections import namedtuple
import math

SOURCE_ID = 'APP-17'
EVENT_UID = '5909'
FRAME_UID = '70866'
REFERENCE_LITERAL = 'ni.var.psp://localhost/SUPERVISION/C1011NI6602'
SINK_UIDS = ('59714', '70290', '70253')
BODY_NODE_UIDS = ('59714', '60452', '61621', '68378', '70253', '70272', '70290', '70885')
DEPENDENCIES = (('60452', '61621'), ('70885', '61621'), ('68378', '61621'),
                ('61621', '59714'), ('61621', '70290'), ('61621', '70253'), ('70272', '70253'))

EventDataReturn = namedtuple('EventDataReturn', 'event_type time control_reference old_value new_value')
WriterReturn = namedtuple('WriterReturn', 'reference_out error_out')
UnwiredInput = namedtuple('UnwiredInput', 'effective_value')
LocalRead = namedtuple('LocalRead', 'node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment = namedtuple('LocalAssignment', 'node_uid control_id saved_param_index saved_bank_uid data')
WriterCall = namedtuple('WriterCall', 'node_uid reference_constant_uid reference_literal reference_in '
                        'source_error_connection supplied_error_input data returned')
FrequencySlice = namedtuple('FrequencySlice', 'local_read event_return updated_cluster local_assignments '
                            'writer_call completed_sinks dependencies')


def require_u32(value):
    """Storage domain, not UI permitted choices, frequency unit or native policy."""
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError('Explicit U32 event NewVal required')


def require_snapshot(value):
    """Already decoded, ordered DBL fields; duplicate labels are never keys."""
    if type(value) is not tuple or len(value) != 33 or any(type(v) is not float for v in value):
        raise TypeError('Explicit tuple of 33 decoded DBL fields required')


def require_completion(value):
    if value is None:
        return
    if type(value) is not tuple or len(value) > 3:
        raise ValueError('Caller completion tuple or None required')
    if any(type(uid) is not str or uid not in SINK_UIDS for uid in value) or len(set(value)) != len(value):
        raise ValueError('Unique saved sink UID completion tuple required')


def project_frequency(local_snapshot, event_return, reference_in, unwired_error_input,
                      writer_return, completed_sinks=None):
    """Project all eight nodes; completion order is a separate caller assertion.

    Read60452 and EventDataNode70885 feed Bundle61621. Its two explicit field
    indices are3 and32. Constant68378 supplies4.0;70272 supplies a saved reference
    token whose native interpretation is opaque. Output61627 independently feeds
    both local writers and native writer70253. No returned writer output controls
    a local assignment. Unused event/writer output contents are never inspected.
    """
    require_snapshot(local_snapshot)
    if type(event_return) is not EventDataReturn:
        raise TypeError('Explicit five-slot EventDataReturn required')
    if type(unwired_error_input) is not UnwiredInput:
        raise TypeError('Explicit supplied UnwiredInput required')
    if type(writer_return) is not WriterReturn:
        raise TypeError('Explicit two-slot WriterReturn required')
    require_u32(event_return.new_value)
    require_completion(completed_sinks)
    fields = list(local_snapshot)
    fields[3] = float(event_return.new_value)
    fields[32] = 4.0
    updated = tuple(fields)
    read = LocalRead('60452', '38232', 163, '38230', local_snapshot)
    assignments = (
        LocalAssignment('59714', '38232', 163, '38230', updated),
        LocalAssignment('70290', '30288', 170, '30286', updated))
    call = WriterCall('70253', '70272', REFERENCE_LITERAL, reference_in,
                      'unwired', unwired_error_input.effective_value, updated, writer_return)
    return FrequencySlice(read, event_return, updated, assignments, call, completed_sinks, DEPENDENCIES)


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Exact saved SUP frequency fields required')


def _json_tree(value):
    """Bound inert JSON storage without interpreting any native leaf content."""
    budget = [1024]
    def visit(item, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > 8:
            raise ValueError('JSON frequency tree exceeds node/depth bounds')
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is int:
            if not -(2**63) <= item < 2**64:
                raise ValueError('JSON integer storage bound exceeded')
            return
        if kind is float:
            if not math.isfinite(item):
                raise ValueError('Finite JSON numbers required')
            return
        if kind is str:
            if len(item) > 4096:
                raise ValueError('JSON string storage bound exceeded')
            return
        if kind is list:
            if len(item) > 64:
                raise ValueError('JSON list storage bound exceeded')
            for child in item:
                visit(child, depth + 1)
            return
        if kind is dict:
            if len(item) > 64 or any(type(k) is not str or len(k) > 256 for k in item):
                raise ValueError('JSON object storage bound exceeded')
            for child in item.values():
                visit(child, depth + 1)
            return
        raise TypeError('Inert JSON values required')
    visit(value, 0)


def replay_saved_sup_frequency(payload):
    """Strict structural JSON adapter over the same core, with opaque leaf slots.

    Native return sub-values have already crossed the caller's JSON boundary.
    They are forwarded without decoding or testing status/default/reference data.
    A null completion value makes no completion claim; a list records only the
    caller's asserted prefix/order, never a source-imposed ordering of sinks.
    """
    _json_tree(payload)
    exact(payload, ('source_id', 'event_uid', 'frame_uid', 'local_reads', 'event_returns',
                    'references', 'unwired_inputs', 'writer_returns', 'completed_sinks'))
    if (payload['source_id'], payload['event_uid'], payload['frame_uid']) != (SOURCE_ID, EVENT_UID, FRAME_UID):
        raise ValueError('Exact APP-17 Event5909 frame70866 required')
    exact(payload['local_reads'], ('60452',))
    values = payload['local_reads']['60452']
    if type(values) is not list:
        raise TypeError('JSON list of 33 decoded DBL fields required')
    exact(payload['event_returns'], ('70885',))
    event = payload['event_returns']['70885']
    exact(event, ('70890', '70893', '71466', '71471', '71474'))
    exact(payload['references'], ('70272',))
    exact(payload['unwired_inputs'], ('70261',))
    exact(payload['writer_returns'], ('70253',))
    writer = payload['writer_returns']['70253']
    exact(writer, ('70258', '70264'))
    completion = payload['completed_sinks']
    if completion is not None and type(completion) is not list:
        raise TypeError('JSON completion list or null required')
    result = project_frequency(tuple(values), EventDataReturn(event['70890'], event['70893'], event['71466'],
        event['71471'], event['71474']), payload['references']['70272'],
        UnwiredInput(payload['unwired_inputs']['70261']), WriterReturn(writer['70258'], writer['70264']),
        tuple(completion) if completion is not None else None)
    assignments = {a.node_uid: dict(control_id=a.control_id, saved_param_index=a.saved_param_index,
        saved_bank_uid=a.saved_bank_uid, data=list(a.data)) for a in result.local_assignments}
    call = result.writer_call
    return dict(source_id=SOURCE_ID, event_uid=EVENT_UID, frame_uid=FRAME_UID,
        scope='SUPPLIED_SELECTED_SUP_FREQUENCY_BODY', body_node_uids=list(BODY_NODE_UIDS),
        local_read=dict(node_uid=result.local_read.node_uid, control_id=result.local_read.control_id,
            saved_param_index=result.local_read.saved_param_index, saved_bank_uid=result.local_read.saved_bank_uid,
            data=values),
        event_returns=event, projected_cluster=list(result.updated_cluster), local_assignments=assignments,
        writer_call=dict(node_uid=call.node_uid, reference_constant_uid=call.reference_constant_uid,
            saved_reference_literal=call.reference_literal, supplied_native_reference=call.reference_in,
            source_error_connection=call.source_error_connection, supplied_effective_unwired_error=call.supplied_error_input,
            data=list(call.data), supplied_returns=writer, returned_output_terminal_uids=['70258', '70264']),
        completed_sinks=completion, completion_is_caller_supplied=completion is not None,
        source_dependencies=[list(pair) for pair in result.dependencies], fanout_sink_uids=list(SINK_UIDS),
        fanout_order_qualified=False, writer_success_gates_local_assignments=False,
        event_selection_supplied=True, local_snapshot_supplied=True, native_leaf_returns_supplied=True,
        native_default_semantics_qualified=False, native_reference_decoding_qualified=False,
        native_coercion_qualified=False, native_cluster_cast_qualified=False, UI_permitted_values_qualified=False,
        psp_delivery_qualified=False, atomic_snapshot_qualified=False, native_runtime_equivalence=False,
        whole_event_equivalence=False, execution_allowed=False, external_calls_executed=False, hardware_writes=False)
