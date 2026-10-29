"""APP-17 Event5909/frame73301: three supplied selector body projections.

Saved literals and positional dataflow are projected in Python. Event delivery,
local snapshot, native reference/error/writer leaves and sink completion remain
caller-supplied. No PSP, UI, scheduler, callback or hardware executor exists.
"""
from collections import namedtuple
import math

SOURCE_ID = 'APP-17'
SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID = '5909'
FRAME_UID = '73301'
REFERENCE_LITERAL = 'ni.var.psp://localhost/SUPERVISION/C9NI6703'
SINK_UIDS = ('13401', '73345', '73369')
BODY_NODE_UIDS = ('13401', '72261', '73320', '72281', '73345', '73353', '73359',
                  '73369', '73386', '82079', '82191', '82140', '82237')
DEPENDENCIES = (('73320', '82079'), ('82079', '72261'), ('72281', '72261'),
                ('72261', '13401'), ('82079', '73359'), ('73353', '73359'),
                ('73359', '73345'), ('73359', '73369'), ('73386', '73369'))
GAINS = (2.126, 8.98, 5.553)
CASE_FRAMES = ('82124', '82176', '82226')
GAIN_CONSTANT_UIDS = ('82140', '82191', '82237')

EventDataReturn = namedtuple('EventDataReturn', 'event_type time control_reference old_value new_value')
WriterReturn = namedtuple('WriterReturn', 'reference_out error_out')
UnwiredInput = namedtuple('UnwiredInput', 'effective_value')
LocalRead = namedtuple('LocalRead', 'node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment = namedtuple('LocalAssignment', 'node_uid control_id saved_param_index saved_bank_uid data')
WriterCall = namedtuple('WriterCall', 'node_uid reference_constant_uid reference_literal reference_in '
                        'source_error_connection supplied_error_input data returned')
PositionT3Slice = namedtuple('PositionT3Slice', 'local_read event_return selector case_frame_uid gain_constant_uid '
                      'selected_gain multiplied_value updated_cluster local_assignments writer_call '
                      'completed_sinks dependencies')


def require_selector(value):
    if type(value) is not int or value not in (0, 1, 2):
        raise ValueError('Explicit saved selector 0, 1 or 2 required; default case unqualified')


def require_snapshot(value):
    if type(value) is not tuple or len(value) != 10 or any(type(v) is not float for v in value):
        raise TypeError('Explicit tuple of 10 decoded DBL fields required')


def require_completion(value):
    if value is None:
        return
    if type(value) is not tuple or len(value) > 3:
        raise ValueError('Caller completion tuple or None required')
    if any(type(uid) is not str or uid not in SINK_UIDS for uid in value) or len(set(value)) != len(value):
        raise ValueError('Unique saved sink UID completion tuple required')


def project_position_t3(local_snapshot, event_return, reference_in, unwired_error_input,
                 writer_return, completed_sinks=None):
    """Select saved DBL, multiply by10.0 and replace carrier ordinal6.

    Selector is supplied EventData73320 NewVal73337. Case82079 supplies gain
    independently to Bundle73359 field6 and Multiply72261;10.0 comes from72281.
    Multiply writes scalar13401; Bundle fans out to73345 and73369. Native writer
    returns never gate either assignment. Completion order has no source claim.
    """
    require_snapshot(local_snapshot)
    if type(event_return) is not EventDataReturn:
        raise TypeError('Explicit five-slot EventDataReturn required')
    if type(unwired_error_input) is not UnwiredInput:
        raise TypeError('Explicit supplied UnwiredInput required')
    if type(writer_return) is not WriterReturn:
        raise TypeError('Explicit two-slot WriterReturn required')
    require_selector(event_return.new_value)
    require_completion(completed_sinks)
    selector = event_return.new_value
    gain = GAINS[selector]
    multiplied = 10.0 * gain
    fields = list(local_snapshot)
    fields[6] = gain
    updated = tuple(fields)
    read = LocalRead('73353', '66941', 25, '66939', local_snapshot)
    assignments = (LocalAssignment('13401', '30877', 19, '30875', multiplied),
                   LocalAssignment('73345', '66941', 25, '66939', updated))
    call = WriterCall('73369', '73386', REFERENCE_LITERAL, reference_in, 'unwired',
                      unwired_error_input.effective_value, updated, writer_return)
    return PositionT3Slice(read, event_return, selector, CASE_FRAMES[selector], GAIN_CONSTANT_UIDS[selector],
                     gain, multiplied, updated, assignments, call, completed_sinks,
                     DEPENDENCIES + ((GAIN_CONSTANT_UIDS[selector], '82079'),))


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Exact saved SUP position T3 fields required')


def _json_tree(value):
    """Bound inert supplied JSON without interpreting native leaf content."""
    budget = [1024]
    def visit(item, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > 8:
            raise ValueError('JSON position T3 tree exceeds node/depth bounds')
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


def replay_saved_sup_position_t3(payload):
    """Exact source sites; native JSON leaves are already decoded by caller."""
    _json_tree(payload)
    exact(payload, ('source_id', 'event_uid', 'frame_uid', 'local_reads', 'event_returns',
                    'references', 'unwired_inputs', 'writer_returns', 'completed_sinks'))
    if (payload['source_id'], payload['event_uid'], payload['frame_uid']) != (SOURCE_ID, EVENT_UID, FRAME_UID):
        raise ValueError('Exact APP-17 Event5909 frame73301 required')
    exact(payload['local_reads'], ('73353',))
    values = payload['local_reads']['73353']
    if type(values) is not list:
        raise TypeError('JSON list of 10 decoded DBL fields required')
    exact(payload['event_returns'], ('73320',))
    event = payload['event_returns']['73320']
    exact(event, ('73325', '73328', '73331', '73334', '73337'))
    exact(payload['references'], ('73386',))
    exact(payload['unwired_inputs'], ('73377',))
    exact(payload['writer_returns'], ('73369',))
    writer = payload['writer_returns']['73369']
    exact(writer, ('73374', '73380'))
    completion = payload['completed_sinks']
    if completion is not None and type(completion) is not list:
        raise TypeError('JSON completion list or null required')
    result = project_position_t3(tuple(values), EventDataReturn(event['73325'], event['73328'], event['73331'],
        event['73334'], event['73337']), payload['references']['73386'], UnwiredInput(payload['unwired_inputs']['73377']),
        WriterReturn(writer['73374'], writer['73380']), tuple(completion) if completion is not None else None)
    assignments = {a.node_uid: dict(control_id=a.control_id, saved_param_index=a.saved_param_index,
        saved_bank_uid=a.saved_bank_uid, data=list(a.data) if type(a.data) is tuple else a.data)
        for a in result.local_assignments}
    call = result.writer_call
    return dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION, event_uid=EVENT_UID, frame_uid=FRAME_UID,
        scope='SUPPLIED_SELECTED_SUP_POSITION_T3_BODY', body_node_uids=list(BODY_NODE_UIDS),
        selected_case_frame_uid=result.case_frame_uid, selected_gain_constant_uid=result.gain_constant_uid,
        selector=result.selector, selected_gain=result.selected_gain, multiplied_value=result.multiplied_value,
        local_read=dict(node_uid=result.local_read.node_uid, control_id=result.local_read.control_id,
            saved_param_index=result.local_read.saved_param_index, saved_bank_uid=result.local_read.saved_bank_uid, data=values),
        event_returns=event, projected_cluster=list(result.updated_cluster), local_assignments=assignments,
        writer_call=dict(node_uid=call.node_uid, reference_constant_uid=call.reference_constant_uid,
            saved_reference_literal=call.reference_literal, supplied_native_reference=call.reference_in,
            source_error_connection=call.source_error_connection, supplied_effective_unwired_error=call.supplied_error_input,
            data=list(call.data), supplied_returns=writer, returned_output_terminal_uids=['73374', '73380']),
        completed_sinks=completion, completion_is_caller_supplied=completion is not None,
        source_dependencies=[list(pair) for pair in result.dependencies], fanout_sink_uids=list(SINK_UIDS),
        fanout_order_qualified=False, writer_success_gates_local_assignments=False,
        event_selection_supplied=True, local_snapshot_supplied=True, native_leaf_returns_supplied=True,
        native_default_semantics_qualified=False, native_reference_decoding_qualified=False,
        native_coercion_qualified=False, native_cluster_cast_qualified=False, UI_permitted_values_qualified=False,
        case_default_qualified=False, units_qualified=False, native_float_bitwise_equivalence=False,
        psp_delivery_qualified=False, atomic_snapshot_qualified=False, event_queue_selection_qualified=False,
        native_runtime_equivalence=False, whole_event_equivalence=False, whole_VI_equivalence=False,
        execution_allowed=False, external_calls_executed=False, hardware_writes=False)
