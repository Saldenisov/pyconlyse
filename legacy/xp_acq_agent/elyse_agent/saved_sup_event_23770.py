"""Original APP17/5909/23770 supplied-data Case/Sequence projection.

Two independent reads feed two explicit field copies. Identified PSP, handler,
and Wait leaves supply observations; no callable or source execution occurs.
"""
import json
from collections import namedtuple

SOURCE_ID = 'APP-17'
SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID = '5909'
FRAME_UID = '23770'
ORIGINAL_SHA256 = 'B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
ErrorValue = namedtuple('ErrorValue', 'status code source_bytes')
LEAF_UIDS = ('78302', '78398', '78464', '78531', '78548')
SINK_UIDS = ('78280', '78302', '78398', '78464', '78509', '78531', '78548', '82122', '15517', '82078')
URI_BYTES = b'ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96'
UNQUALIFIED_FLAGS = (
    'native_execution_qualified', 'native_storage_serializer_qualified',
    'native_default_policy_qualified', 'native_reference_validity_qualified',
    'native_wait_units_or_timing_qualified', 'native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified', 'native_atomic_snapshot_qualified',
    'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified',
    'native_field_index_selection_qualified', 'native_String_encoding_qualified',
    'whole_event_equivalence', 'whole_VI_equivalence')
UNWIRED = {'78389': 'error', '78539': 'error', '78407': 'opaque', '78557': 'opaque',
           '78410': 'I32', '78561': 'I32', '78413': 'bytes', '78570': 'bytes',
           '78425': 'U16', '78594': 'U16'}
INPUT_ORDER = {'78302': ('78304', '78389', '78395'),
               '78398': ('78407', '78410', '78413', '78425', '78428'),
               '78464': ('78469',), '78531': ('78533', '78539', '78545'),
               '78548': ('78557', '78561', '78570', '78594', '78600')}


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
    elif kind == 'U16':
        _integer(value, 0, 65535, kind)
    return value


def _carrier(value):
    if type(value) is not tuple or len(value) != 40 or any(type(v) is not bool for v in value):
        raise ValueError('EXACT_40_BOOLEAN_TUPLE')
    return value


def _completions(value, active):
    if type(value) not in (tuple, list) or any(type(u) is not str or u not in active for u in value):
        raise ValueError('COMPLETION_OBSERVATION_DOMAIN')
    if len(value) != len(set(value)):
        raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)


def project_event_23770(new_value, local_reads, literal_inputs, reference_bindings,
                        native_boundaries, unwired_inputs, event_outputs=None, completed_sinks=()):
    """Direct arms/three phases for hypothetical supplied carriers and leaf outputs.

    No completion subset/order certifies source feasibility, success, delivery,
    elapsed time, or equality of independent C5 observations. Native leaves do
    not run. Bool literal decoding and field selection remain unqualified.
    """
    _typed(new_value, 'boolean')
    completion = _completions(completed_sinks, SINK_UIDS if new_value else ())
    result = dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION, event_uid=EVENT_UID, frame_uid=FRAME_UID,
        original_sha256=ORIGINAL_SHA256, source_case_uid='77922',
        selected_case_frame='78236' if new_value else '77941', source_NewVal_terminal_uid='77915',
        supplied_NewVal=new_value, sequence_uid='78242' if new_value else None,
        source_sequence_actual_diagram_uids=('78246', '78446', '78475') if new_value else (),
        local_reads=[], field_updates=[], local_assignments=[], leaf_observations=[], reference_bindings=[],
        supplied_unused_event_outputs=event_outputs, completed_sinks=completion,
        completion_observations_are_feasible_trace=False, completion_observations_prove_success=False,
        original_native_execution=False, source_execution=False, native_storage_serializer_qualified=False,
        native_field_index_selection_qualified=False, native_callee_equivalence_qualified=False,
        native_coercion_qualified=False, native_String_encoding_qualified=False,
        native_wait_units_or_timing_qualified=False, native_reference_validity_qualified=False,
        native_atomic_snapshot_qualified=False, whole_event_equivalence=False, whole_VI_equivalence=False,
        actual_absent_structures=('ForLoop', 'ErrorCase', 'VariantToData', 'ArrayMaxMin', 'InRangeAndCoerce'))
    if not new_value:
        return result
    _exact(local_reads, ('78286', '78515'), 'LOCAL_READ')
    first = _carrier(local_reads['78286'])
    second = _carrier(local_reads['78515'])
    _exact(literal_inputs, ('78270', '78499', '82173'), 'ACTIVE_LITERAL')
    for value in literal_inputs.values():
        _typed(value, 'boolean')
    _exact(reference_bindings, ('78252', '78481'), 'REFERENCE')
    for uid in ('78252', '78481'):
        _exact(reference_bindings[uid], ('stored_URI_bytes', 'native_reference'), 'REFERENCE_' + uid)
        if _bytes(reference_bindings[uid]['stored_URI_bytes']) != URI_BYTES:
            raise ValueError('EXACT_STORED_URI_PAYLOAD')
    _exact(native_boundaries, LEAF_UIDS, 'NATIVE_BOUNDARY')
    _exact(unwired_inputs, UNWIRED, 'UNWIRED_INPUT')
    for face, kind in UNWIRED.items():
        _typed(unwired_inputs[face], kind)
    supplied = {}
    for uid in LEAF_UIDS:
        _exact(native_boundaries[uid], ('outputs',), 'LEAF_' + uid)
        supplied[uid] = native_boundaries[uid]['outputs']
    for uid, ref, err in (('78302', '78307', '78392'), ('78531', '78536', '78542')):
        _exact(supplied[uid], (ref, err), 'WRITER_OUTPUT_' + uid)
        _typed(supplied[uid][err], 'error')
    # All outputs of the handlers and Wait are unused observations. Do not inspect them.
    def call(uid, phase, explicit):
        ports = {f: unwired_inputs[f] for f in INPUT_ORDER[uid] if f in UNWIRED}
        ports.update(explicit)
        _exact(ports, INPUT_ORDER[uid], 'CALL_' + uid)
        result['leaf_observations'].append(dict(node_uid=uid, sequence_phase=phase, inputs=ports,
            source_input_order=INPUT_ORDER[uid], supplied_outputs=supplied[uid],
            callee_or_native_executed=False, unused_outputs_are_uninterpreted=uid in ('78398', '78464', '78548')))
    def update(read, base, literal, mux, inface, outface, write, writeface, phase):
        carrier = base[:24] + (literal_inputs[literal],) + base[25:]
        result['local_reads'].append(dict(node_uid=read, explicit_paramIdx=26, control_terminal_uid='66821',
            value=base, independent_observation=True))
        result['field_updates'].append(dict(node_uid=mux, field_terminal_uid=inface,
            raw_flattened_field_index=24, raw_i_present=True, typed_position_path=(24,),
            field_label='24 DPB0 b82 Cmd Faraday 2 EN', literal_uid=literal, source_literal_raw_hex='01' if literal == '78270' else '0000',
            decoded_literal_is_hypothetical=True, aggregate_output_terminal_uid=outface, value=carrier,
            native_field_index_selection_qualified=False))
        result['local_assignments'].append(dict(node_uid=write, terminal_uid=writeface, sequence_phase=phase,
            explicit_paramIdx=26, control_terminal_uid='66821', value=carrier))
        return carrier
    c0 = update('78286', first, '78270', '78292', '78298', '78294', '78280', '78283', 0)
    for uid in ('78252', '78481'):
        result['reference_bindings'].append(dict(constant_uid=uid, stored_URI_bytes=URI_BYTES,
            native_reference=reference_bindings[uid]['native_reference'], native_reference_decoding_qualified=False))
    call('78302', 0, {'78304': reference_bindings['78252']['native_reference'], '78395': c0})
    call('78398', 0, {'78428': supplied['78302']['78392']})
    call('78464', 1, {'78469': 500})
    c2 = update('78515', second, '78499', '78521', '78527', '78523', '78509', '78512', 2)
    call('78531', 2, {'78533': reference_bindings['78481']['native_reference'], '78545': c2})
    call('78548', 2, {'78600': supplied['78531']['78542']})
    for node, terminal, bank, target in (('82122', '82131', 156, '23486'), ('15517', '82060', 10, '24427'), ('82078', '82087', 7, '31048')):
        result['local_assignments'].append(dict(node_uid=node, terminal_uid=terminal, sequence_phase=2,
            explicit_paramIdx=bank, control_terminal_uid=target, literal_uid='82173',
            source_literal_raw_hex='0000', decoded_literal_is_hypothetical=True, value=literal_inputs['82173']))
    result['provided_data_numeric_literals'] = {'78452': dict(raw_hex='000001F4', U32_value=500)}
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
    return _typed(ErrorValue(value['status'], value['code'], _json_bytes({'bytes_hex': value['source_hex']})), 'error')


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


def replay_saved_sup_event_23770(payload):
    required = {'source_id', 'source_version', 'event_uid', 'frame_uid', 'new_value', 'local_reads',
                'literal_inputs', 'reference_bindings', 'native_boundaries', 'unwired_inputs', 'unqualified_boundaries'}
    optional = {'event_outputs', 'completed_sinks'}
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - optional:
        raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) != (SOURCE_ID, SOURCE_VERSION, EVENT_UID, FRAME_UID):
        raise ValueError('SOURCE_ENTITY_IDENTITY')
    _exact(payload['unqualified_boundaries'], UNQUALIFIED_FLAGS, 'BOUNDARY')
    if any(value is not False for value in payload['unqualified_boundaries'].values()):
        raise ValueError('BOUNDARY_FALSE_REQUIRED')
    _encode(payload)  # Replay transport policy, not native carrier validation.
    new = _typed(payload['new_value'], 'boolean')
    if not new:
        return _encode(project_event_23770(new, None, None, None, None, None,
            event_outputs=payload.get('event_outputs'), completed_sinks=payload.get('completed_sinks', ())))
    reads = payload['local_reads']
    _exact(reads, ('78286', '78515'), 'LOCAL_READ')
    if any(type(value) is not list for value in reads.values()):
        raise ValueError('JSON_40_BOOLEAN_LIST')
    refs = payload['reference_bindings']
    _exact(refs, ('78252', '78481'), 'REFERENCE')
    decoded_refs = {}
    for uid, row in refs.items():
        _exact(row, ('stored_URI_bytes', 'native_reference'), 'REFERENCE_' + uid)
        decoded_refs[uid] = {'stored_URI_bytes': _json_bytes(row['stored_URI_bytes']), 'native_reference': row['native_reference']}
    leaves = payload['native_boundaries']
    _exact(leaves, LEAF_UIDS, 'NATIVE_BOUNDARY')
    decoded_leaves = {}
    for uid, row in leaves.items():
        _exact(row, ('outputs',), 'LEAF_' + uid)
        if uid in ('78302', '78531'):
            ref, err = ('78307', '78392') if uid == '78302' else ('78536', '78542')
            _exact(row['outputs'], (ref, err), 'WRITER_OUTPUT_' + uid)
            decoded_leaves[uid] = {'outputs': {ref: row['outputs'][ref], err: _json_error(row['outputs'][err])}}
        else:
            decoded_leaves[uid] = row
    uw = payload['unwired_inputs']
    _exact(uw, UNWIRED, 'UNWIRED_INPUT')
    decoded_uw = {uid: _json_error(value) if UNWIRED[uid] == 'error' else _json_bytes(value) if UNWIRED[uid] == 'bytes' else value for uid, value in uw.items()}
    return _encode(project_event_23770(new, {uid: tuple(v) for uid, v in reads.items()}, payload['literal_inputs'],
        decoded_refs, decoded_leaves, decoded_uw, event_outputs=payload.get('event_outputs'), completed_sinks=payload.get('completed_sinks', ())))


__all__ = ['project_event_23770', 'replay_saved_sup_event_23770', 'ErrorValue']
