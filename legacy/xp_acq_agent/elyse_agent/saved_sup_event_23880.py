"""Saved APP17/5909/23880 provided-data Case body; no driver/VI execution.

Decoded Boolean storage selects a hypothetical Case arm. Identified FW102x and
handler leaves supply individual returns. No callee/structure callback runs.
"""
import json
from collections import namedtuple

SOURCE_ID = 'APP-17'
SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID = '5909'
FRAME_UID = '23880'
ORIGINAL_SHA256 = 'B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
ErrorValue = namedtuple('ErrorValue', 'status code source_bytes')
LEAF_UIDS = ('17431', '17485', '17531', '17574', '17627', '28756', '17666')
SINK_UIDS = LEAF_UIDS + ('30337', '34747')
SERIAL_BYTES = b'ASRL2::INSTR'
UNQUALIFIED_FLAGS = (
    'native_execution_qualified', 'native_storage_serializer_qualified',
    'native_default_policy_qualified', 'native_reference_validity_qualified',
    'native_wait_units_or_timing_qualified', 'native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified', 'native_atomic_snapshot_qualified',
    'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified',
    'native_String_encoding_qualified', 'whole_event_equivalence', 'whole_VI_equivalence')
OUTPUTS = {
    '17431': (('17440', 'error'), ('17453', 'opaque')),
    '17485': (('17491', 'error'), ('17500', 'opaque')),
    '17531': (('17534', 'error'), ('17540', 'I32'), ('17543', 'opaque')),
    '17574': (('17577', 'error'), ('17584', 'bytes'), ('17587', 'opaque')),
    '17627': (('17630', 'error'),)}
UNWIRED = {
    '17444': 'opaque', '17449': 'opaque', '17456': 'opaque', '17459': 'opaque',
    '17462': 'opaque', '17468': 'error', '17471': 'boolean',
    '17494': 'opaque', '17497': 'opaque', '17507': 'opaque', '17510': 'opaque',
    '17513': 'opaque', '17516': 'opaque', '17522': 'opaque',
    '17537': 'opaque', '17546': 'opaque', '17549': 'opaque', '17552': 'opaque',
    '17555': 'opaque', '17562': 'opaque', '17568': 'opaque',
    '17580': 'opaque', '17598': 'opaque', '17604': 'opaque', '17608': 'opaque',
    '17611': 'opaque', '17617': 'U32', '17620': 'I32',
    '17633': 'opaque', '17636': 'opaque', '17639': 'opaque', '17642': 'opaque',
    '17645': 'opaque', '17648': 'opaque', '17651': 'opaque', '17657': 'opaque', '17660': 'opaque',
    '28771': 'opaque', '28776': 'I32', '28779': 'bytes', '28791': 'U16'}
INPUTS = {
    '17431': ('17444', '17449', '17456', '17459', '17462', '17465', '17468', '17471', '17475', '17478'),
    '17485': ('17494', '17497', '17507', '17510', '17513', '17516', '17519', '17522', '17525', '17528'),
    '17531': ('17537', '17546', '17549', '17552', '17555', '17558', '17562', '17568', '17571'),
    '17574': ('17580', '17598', '17604', '17608', '17611', '17614', '17617', '17620', '17624'),
    '17627': ('17633', '17636', '17639', '17642', '17645', '17648', '17651', '17654', '17657', '17660', '17663'),
    '28756': ('28771', '28776', '28779', '28791', '28794'),
    '17666': ('17677',)}


def _exact(value, keys, why):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(why + '_KEYS')


def _integer(value, lo, hi, why):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(why + '_EXACT_INTEGER_RANGE')
    return value


def _bytes(value):
    if type(value) is not bytes or len(value) > 4096:
        raise ValueError('EXPLICIT_BOUNDED_BYTES')
    return value


def _typed(value, kind):
    if kind == 'error':
        if type(value) is not ErrorValue or type(value.status) is not bool:
            raise ValueError('EXPLICIT_ERROR_VALUE')
        _integer(value.code, -(2 ** 31), 2 ** 31 - 1, 'ERROR_CODE')
        _bytes(value.source_bytes)
    elif kind == 'bytes':
        _bytes(value)
    elif kind == 'boolean':
        if type(value) is not bool:
            raise ValueError('EXACT_BOOLEAN')
    elif kind == 'I32':
        _integer(value, -(2 ** 31), 2 ** 31 - 1, kind)
    elif kind == 'U32':
        _integer(value, 0, 2 ** 32 - 1, kind)
    elif kind == 'U16':
        _integer(value, 0, 65535, kind)
    return value


def _completions(value, active):
    if type(value) not in (tuple, list) or any(type(u) is not str or u not in active for u in value):
        raise ValueError('COMPLETION_OBSERVATION_DOMAIN')
    if len(value) != len(set(value)):
        raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)


def project_event_23880(literal_inputs, local_reads, native_boundaries, unwired_inputs,
                        event_outputs=None, completed_sinks=()):
    """Direct saved arms and exact port routing for explicit hypothetical carriers.

    False touches only decoded25668 and completion metadata. True evaluates
    source dependencies directly, independent of errors; supplied completion
    subsets/order do not certify feasible schedules, success, or delivery.
    """
    if (type(literal_inputs) is not dict or not set(literal_inputs) <= {'25668', '17326', '17367'}
            or '25668' not in literal_inputs or type(literal_inputs['25668']) is not bool):
        raise ValueError('EXPLICIT_DECODED_SELECTOR_LITERAL_25668')
    selected = literal_inputs['25668']
    completion = _completions(completed_sinks, SINK_UIDS if selected else ())
    result = dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION, event_uid=EVENT_UID, frame_uid=FRAME_UID,
                  original_sha256=ORIGINAL_SHA256, source_case_uid='24546',
                  selected_case_frame='25142' if selected else '25108', supplied_decoded_selector=selected,
                  selector_literal_uid='25668', selector_literal_raw_hex='0000',
                  selector_literal_interpretation_is_hypothetical=True,
                  local_reads=[], local_assignments=[], leaf_observations=[],
                  supplied_unused_event_outputs=event_outputs, completed_sinks=completion,
                  completion_observations_are_feasible_trace=False, completion_observations_prove_success=False,
                  original_native_execution=False, source_execution=False, native_storage_serializer_qualified=False,
                  native_callee_equivalence_qualified=False, native_coercion_qualified=False,
                  native_String_encoding_qualified=False, native_wait_units_or_timing_qualified=False,
                  whole_event_equivalence=False, whole_VI_equivalence=False,
                  actual_absent_structures=('Sequence', 'ForLoop', 'ErrorCase', 'nMux', 'VariantToData',
                                           'ArrayMaxMin', 'InRangeAndCoerce', 'PSP writer'))
    if not selected:
        return result
    _exact(literal_inputs, ('25668', '17326', '17367'), 'ACTIVE_LITERAL')
    _typed(literal_inputs['17326'], 'boolean')
    if _bytes(literal_inputs['17367']) != SERIAL_BYTES:
        raise ValueError('EXACT_SUPPLIED_STORED_STRING_PAYLOAD_17367')
    _exact(local_reads, ('31193',), 'LOCAL_READ')
    position = _typed(local_reads['31193'], 'U16')
    _exact(native_boundaries, LEAF_UIDS, 'NATIVE_BOUNDARY')
    _exact(unwired_inputs, UNWIRED, 'UNWIRED_INPUT')
    for uid, kind in UNWIRED.items():
        _typed(unwired_inputs[uid], kind)
    supplied = {}
    for uid in LEAF_UIDS:
        _exact(native_boundaries[uid], ('outputs',), 'LEAF_' + uid)
        supplied[uid] = native_boundaries[uid]['outputs']
        if uid in OUTPUTS:
            _exact(supplied[uid], (f for f, kind in OUTPUTS[uid]), 'OUTPUT_' + uid)
            for face, kind in OUTPUTS[uid]:
                _typed(supplied[uid][face], kind)
        # Handler and Wait outputs are unused opaque observations, never dereferenced.
    result['local_reads'].append(dict(node_uid='31193', terminal_uid='31203', explicit_paramIdx=143,
                                     control_terminal_uid='22692', value=position,
                                     source_type='NumUInt16', target_callee_type='NumInt32',
                                     native_coercion_qualified=False))
    def call(uid, explicit):
        ports = {face: unwired_inputs[face] for face in INPUTS[uid] if face in UNWIRED}
        ports.update(explicit)
        _exact(ports, INPUTS[uid], 'CALL_' + uid)
        result['leaf_observations'].append(dict(node_uid=uid, inputs=ports, source_input_order=INPUTS[uid],
            supplied_outputs=supplied[uid], callee_or_native_executed=False,
            unused_outputs_are_uninterpreted=uid in ('28756', '17666')))
    call('17431', {'17465': literal_inputs['17326'], '17475': 9600, '17478': literal_inputs['17367']})
    call('17485', {'17519': supplied['17431']['17440'], '17525': position, '17528': supplied['17431']['17453']})
    call('17531', {'17558': supplied['17485']['17491'], '17571': supplied['17485']['17500']})
    result['local_assignments'].append(dict(node_uid='34747', terminal_uid='34757', explicit_paramIdx=90,
                                          control_terminal_uid='17257', value=supplied['17531']['17540']))
    call('17574', {'17614': supplied['17531']['17534'], '17624': supplied['17531']['17543']})
    result['local_assignments'].append(dict(node_uid='30337', terminal_uid='30348', explicit_paramIdx=89,
                                          control_terminal_uid='17229', value=supplied['17574']['17584']))
    call('17627', {'17654': supplied['17574']['17577'], '17663': supplied['17574']['17587']})
    call('28756', {'28794': supplied['17627']['17630']})
    call('17666', {'17677': 50})
    result['provided_data_numeric_literals'] = {'17349': dict(raw_hex='00002580', I32_value=9600),
                                               '17388': dict(raw_hex='00000032', U32_value=50)}
    return result


def _hex(value):
    return ''.join('{:02X}'.format(b) for b in value)


def _json_bytes(value):
    _exact(value, ('bytes_hex',), 'BYTE_CARRIER')
    text = value['bytes_hex']
    if type(text) is not str or len(text) > 8192 or len(text) % 2 or any(c not in '0123456789ABCDEF' for c in text):
        raise ValueError('CANONICAL_BOUNDED_BYTE_HEX')
    return bytes.fromhex(text)


def _json_error(value):
    _exact(value, ('status', 'code', 'source_hex'), 'ERROR_CARRIER')
    source = _json_bytes({'bytes_hex': value['source_hex']})
    return _typed(ErrorValue(value['status'], value['code'], source), 'error')


def _encode(value, depth=0):
    if depth > 16:
        raise ValueError('JSON_DEPTH')
    if type(value) is ErrorValue:
        return dict(status=value.status, code=value.code, source_hex=_hex(value.source_bytes))
    if type(value) is bytes:
        return {'bytes_hex': _hex(_bytes(value))}
    if value is None or type(value) in (bool, str, int):
        if type(value) is str and len(value) > 8192:
            raise ValueError('JSON_STRING_SIZE')
        if type(value) is int and abs(value) > 2 ** 53 - 1:
            raise ValueError('JSON_INTEGER_RANGE')
        return value
    if type(value) is float:
        if value != value or value in (float('inf'), -float('inf')):
            raise ValueError('JSON_NONFINITE')
        return value
    if type(value) in (list, tuple):
        if len(value) > 64:
            raise ValueError('JSON_LIST_SIZE')
        return [_encode(item, depth + 1) for item in value]
    if type(value) is dict and len(value) <= 64 and all(type(k) is str and len(k) <= 128 for k in value):
        return {k: _encode(v, depth + 1) for k, v in value.items()}
    raise ValueError('JSON_INERT_VALUE')


def replay_saved_sup_event_23880(payload):
    required = {'source_id', 'source_version', 'event_uid', 'frame_uid', 'literal_inputs',
                'local_reads', 'native_boundaries', 'unwired_inputs', 'unqualified_boundaries'}
    optional = {'event_outputs', 'completed_sinks'}
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - optional:
        raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) != (
            SOURCE_ID, SOURCE_VERSION, EVENT_UID, FRAME_UID):
        raise ValueError('SOURCE_ENTITY_IDENTITY')
    _exact(payload['unqualified_boundaries'], UNQUALIFIED_FLAGS, 'BOUNDARY')
    if any(value is not False for value in payload['unqualified_boundaries'].values()):
        raise ValueError('BOUNDARY_FALSE_REQUIRED')
    _encode(payload)  # Generic transport bounds, no native interpretation.
    literals = payload['literal_inputs']
    if (type(literals) is not dict or not set(literals) <= {'25668', '17326', '17367'}
            or '25668' not in literals or type(literals['25668']) is not bool):
        raise ValueError('EXPLICIT_DECODED_SELECTOR_LITERAL_25668')
    if not literals['25668']:
        return _encode(project_event_23880(literals, None, None, None,
                        payload.get('event_outputs'), payload.get('completed_sinks', ())))
    _exact(literals, ('25668', '17326', '17367'), 'ACTIVE_LITERAL')
    literals = dict(literals)
    literals['17367'] = _json_bytes(literals['17367'])
    native = {}
    _exact(payload['native_boundaries'], LEAF_UIDS, 'NATIVE_BOUNDARY')
    for uid in LEAF_UIDS:
        row = payload['native_boundaries'][uid]
        _exact(row, ('outputs',), 'LEAF_' + uid)
        outputs = row['outputs']
        if uid in OUTPUTS:
            _exact(outputs, (face for face, kind in OUTPUTS[uid]), 'OUTPUT_' + uid)
            outputs = dict(outputs)
            for face, kind in OUTPUTS[uid]:
                if kind == 'error':
                    outputs[face] = _json_error(outputs[face])
                elif kind == 'bytes':
                    outputs[face] = _json_bytes(outputs[face])
        native[uid] = {'outputs': outputs}
    _exact(payload['unwired_inputs'], UNWIRED, 'UNWIRED_INPUT')
    unwired = dict(payload['unwired_inputs'])
    for face, kind in UNWIRED.items():
        if kind == 'error':
            unwired[face] = _json_error(unwired[face])
        elif kind == 'bytes':
            unwired[face] = _json_bytes(unwired[face])
    return _encode(project_event_23880(literals, payload['local_reads'], native, unwired,
                   payload.get('event_outputs'), payload.get('completed_sinks', ())))
