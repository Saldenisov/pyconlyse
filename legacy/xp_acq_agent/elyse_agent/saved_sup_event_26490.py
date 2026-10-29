"""Provided-data projection of saved APP-17/5909/26490; never executes a VI.

Boolean literal decodes are hypothetical inputs. Sequence phase order records
source containers; it does not prove timing, scheduling, or write delivery.
Wait's unused output and all six unused event-data ports are never inspected.
"""
import json

SOURCE_ID = 'APP-17'
SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID = '5909'
FRAME_UID = '26490'
ORIGINAL_SHA256 = 'B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
QUALIFICATION_FLAGS = (
    'native_execution_qualified', 'native_storage_serializer_qualified',
    'native_default_policy_qualified', 'native_reference_validity_qualified',
    'native_wait_units_or_timing_qualified', 'native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified', 'native_atomic_snapshot_qualified',
    'native_primitive_coercion_qualified', 'whole_event_equivalence',
    'whole_VI_equivalence')
SINK_UIDS = ('19732', '22081', '21619')


def _literal_inputs(value):
    if type(value) is not dict or set(value) != {'20659', '21637'}:
        raise ValueError('LITERAL_INPUT_KEYS')
    if any(type(value[uid]) is not bool for uid in ('20659', '21637')):
        raise ValueError('LITERAL_INPUT_BOOLEAN')
    return value


def _completions(value):
    if type(value) not in (tuple, list):
        raise ValueError('COMPLETION_OBSERVATION_LIST')
    if any(type(uid) is not str or uid not in SINK_UIDS for uid in value):
        raise ValueError('COMPLETION_OBSERVATION_UID')
    if len(value) != len(set(value)):
        raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)


def project_event_26490(literal_inputs, wait_return=None, event_outputs=None,
                        completed_sinks=()):
    """Lower all selected business phases directly for explicit Boolean decodes.

    Completion observations may be any distinct subset/order. They are caller
    reports, not a source-feasible trace. No native output is dereferenced.
    """
    literals = _literal_inputs(literal_inputs)
    completion = _completions(completed_sinks)
    first = dict(node_uid='19732', phase_ordinal=0, source_container_uid='20201',
                 source_diagram_uid='20206', source_signal_uid='20666',
                 source_literal_uid='20659', source_literal_raw_hex='01',
                 terminal_uid='19749', explicit_paramIdx=132,
                 saved_FP_bank_uid='19944', control_terminal_uid='19961',
                 decoded_literal_is_hypothetical=True, value=literals['20659'])
    last = dict(node_uid='21619', phase_ordinal=2, source_container_uid='21238',
                source_diagram_uid='21245', source_signal_uid='21648',
                source_literal_uid='21637', source_literal_raw_hex='0000',
                terminal_uid='21627', explicit_paramIdx=132,
                saved_FP_bank_uid='19944', control_terminal_uid='19961',
                decoded_literal_is_hypothetical=True, value=literals['21637'])
    wait = dict(node_uid='22081', phase_ordinal=1, source_container_uid='21020',
                source_diagram_uid='21027', source_signal_uid='22724',
                literal_uid='22327', source_literal_raw_hex='000000C8',
                input_terminal_uid='22091', provided_data_U32_input=200,
                unused_output_terminal_uid='22087', supplied_unused_return=wait_return,
                native_units_and_timing_qualified=False)
    return dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION,
                event_uid=EVENT_UID, frame_uid=FRAME_UID,
                original_sha256=ORIGINAL_SHA256,
                source_sequence_uid='20194',
                source_phase_order=('20201', '21020', '21238'),
                source_assignments=(first, last), wait_observation=wait,
                unused_event_data_node_uid='26506',
                supplied_unused_event_outputs=event_outputs,
                completed_sinks=completion,
                completion_observations_are_feasible_trace=False,
                completion_observations_prove_success=False,
                original_native_execution=False, source_execution=False,
                native_storage_serializer_qualified=False,
                whole_event_equivalence=False, whole_VI_equivalence=False,
                actual_absent_structures=('Case', 'ForLoop', 'ErrorCase',
                                         'nMux', 'VariantToData', 'ArrayMaxMin',
                                         'InRangeAndCoerce', 'PSP writer'))


def _json_value(value, depth=0):
    """Bound JSON-facing opaque observations without interpreting their values."""
    if depth > 12:
        raise ValueError('JSON_DEPTH')
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -(2 ** 53 - 1) <= value <= 2 ** 53 - 1:
            raise ValueError('JSON_INTEGER_RANGE')
        return
    if type(value) is float:
        # JSON generic finite check; no source numeric coercion or native meaning.
        if value != value or value in (float('inf'), -float('inf')):
            raise ValueError('JSON_NONFINITE')
        return
    if type(value) is str:
        if len(value) > 4096:
            raise ValueError('JSON_STRING_SIZE')
        return
    if type(value) is list:
        if len(value) > 64:
            raise ValueError('JSON_ARRAY_SIZE')
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > 64 or any(type(k) is not str or len(k) > 128 for k in value):
            raise ValueError('JSON_OBJECT_SIZE_OR_KEY')
        for item in value.values():
            _json_value(item, depth + 1)
        return
    raise ValueError('JSON_TYPE')


def replay_saved_sup_event_26490(payload):
    required = {'source_id', 'source_version', 'event_uid', 'frame_uid',
                'literal_inputs', 'unqualified_boundaries'}
    optional = {'wait_return', 'event_outputs', 'completed_sinks'}
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - optional:
        raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) != (
            SOURCE_ID, SOURCE_VERSION, EVENT_UID, FRAME_UID):
        raise ValueError('SOURCE_ENTITY_IDENTITY')
    boundaries = payload['unqualified_boundaries']
    if type(boundaries) is not dict or set(boundaries) != set(QUALIFICATION_FLAGS):
        raise ValueError('UNQUALIFIED_BOUNDARY_KEYS')
    if any(boundaries[k] is not False for k in QUALIFICATION_FLAGS):
        raise ValueError('UNQUALIFIED_BOUNDARY_FALSE_REQUIRED')
    _json_value(payload)
    result = project_event_26490(payload['literal_inputs'], payload.get('wait_return'),
                                payload.get('event_outputs'), payload.get('completed_sinks', ()))
    # Transport roundtrip only; no opaque value becomes native source evidence.
    return json.loads(json.dumps(result, ensure_ascii=True, allow_nan=False))
