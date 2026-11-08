"""Original APP17/5909/56943 supplied-data Case/Sequence projection.

Two independent reads feed two explicit field copies. Identified PSP, handler,
and Wait leaves supply observations; no callable or source execution occurs.
"""
import json
from collections import namedtuple

SOURCE_ID = 'APP-17'
SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID = '5909'
FRAME_UID = '56943'
ORIGINAL_SHA256 = 'B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
ErrorValue = namedtuple('ErrorValue', 'status code source_bytes')
LEAF_UIDS = ('62647', '62674', '62840', '62956', '62975')
SINK_UIDS = ('62619', '62647', '62674', '62840', '62931', '62956', '62975', '72697', '72654', '72689')
URI_BYTES = b'ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96'
UNQUALIFIED_FLAGS = (
    'native_execution_qualified', 'native_storage_serializer_qualified',
    'native_default_policy_qualified', 'native_reference_validity_qualified',
    'native_wait_units_or_timing_qualified', 'native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified', 'native_atomic_snapshot_qualified',
    'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified',
    'native_field_index_selection_qualified', 'native_String_encoding_qualified',
    'whole_event_equivalence', 'whole_VI_equivalence')
UNWIRED = {'62660': 'error', '62965': 'error', '62688': 'opaque', '62985': 'opaque',
           '62696': 'I32', '62989': 'I32', '62699': 'bytes', '62992': 'bytes',
           '62754': 'U16', '63017': 'U16'}
INPUT_ORDER = {'62647': ('62649', '62660', '62667'),
               '62674': ('62688', '62696', '62699', '62754', '62763'),
               '62840': ('62865',), '62956': ('62958', '62965', '62972'),
               '62975': ('62985', '62989', '62992', '63017', '63023')}


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


def project_event_56943(new_value, local_reads, literal_inputs, reference_bindings,
                        native_boundaries, unwired_inputs, event_outputs=None, completed_sinks=()):
    """Direct arms/three phases for hypothetical supplied carriers and leaf outputs.

    No completion subset/order certifies source feasibility, success, delivery,
    elapsed time, or equality of independent C5 observations. Native leaves do
    not run. Bool literal decoding and field selection remain unqualified.
    """
    _typed(new_value, 'boolean')
    completion = _completions(completed_sinks, SINK_UIDS if new_value else ())
    result = dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION, event_uid=EVENT_UID, frame_uid=FRAME_UID,
        original_sha256=ORIGINAL_SHA256, source_case_uid='57006',
        selected_case_frame='62568' if new_value else '57045', source_NewVal_terminal_uid='56998',
        supplied_NewVal=new_value, sequence_uid='62574' if new_value else None,
        source_sequence_actual_diagram_uids=('62578', '62813', '62872') if new_value else (),
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
    _exact(local_reads, ('62631', '62938'), 'LOCAL_READ')
    first = _carrier(local_reads['62631'])
    second = _carrier(local_reads['62938'])
    _exact(literal_inputs, ('62607', '62918', '72708'), 'ACTIVE_LITERAL')
    for value in literal_inputs.values():
        _typed(value, 'boolean')
    _exact(reference_bindings, ('62584', '62881'), 'REFERENCE')
    for uid in ('62584', '62881'):
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
    for uid, ref, err in (('62647', '62652', '62663'), ('62956', '62962', '62969')):
        _exact(supplied[uid], (ref, err), 'WRITER_OUTPUT_' + uid)
        _typed(supplied[uid][err], 'error')
    # All outputs of the handlers and Wait are unused observations. Do not inspect them.
    def call(uid, phase, explicit):
        ports = {f: unwired_inputs[f] for f in INPUT_ORDER[uid] if f in UNWIRED}
        ports.update(explicit)
        _exact(ports, INPUT_ORDER[uid], 'CALL_' + uid)
        result['leaf_observations'].append(dict(node_uid=uid, sequence_phase=phase, inputs=ports,
            source_input_order=INPUT_ORDER[uid], supplied_outputs=supplied[uid],
            callee_or_native_executed=False, unused_outputs_are_uninterpreted=uid in ('62674', '62840', '62975')))
    def update(read, base, literal, mux, inface, outface, write, writeface, phase):
        carrier = base[:25] + (literal_inputs[literal],) + base[26:]
        result['local_reads'].append(dict(node_uid=read, explicit_paramIdx=26, control_terminal_uid='66821',
            value=base, independent_observation=True))
        result['field_updates'].append(dict(node_uid=mux, field_terminal_uid=inface,
            raw_flattened_field_index=25, raw_i_present=True, typed_position_path=(25,),
            field_label='25 DPB1 b80 Cmd Faraday 3 EN', literal_uid=literal, source_literal_raw_hex='01' if literal == '62607' else '0000',
            decoded_literal_is_hypothetical=True, aggregate_output_terminal_uid=outface, value=carrier,
            native_field_index_selection_qualified=False))
        result['local_assignments'].append(dict(node_uid=write, terminal_uid=writeface, sequence_phase=phase,
            explicit_paramIdx=26, control_terminal_uid='66821', value=carrier))
        return carrier
    c0 = update('62631', first, '62607', '62637', '62643', '62639', '62619', '62628', 0)
    for uid in ('62584', '62881'):
        result['reference_bindings'].append(dict(constant_uid=uid, stored_URI_bytes=URI_BYTES,
            native_reference=reference_bindings[uid]['native_reference'], native_reference_decoding_qualified=False))
    call('62647', 0, {'62649': reference_bindings['62584']['native_reference'], '62667': c0})
    call('62674', 0, {'62763': supplied['62647']['62663']})
    call('62840', 1, {'62865': 500})
    c2 = update('62938', second, '62918', '62945', '62952', '62947', '62931', '62935', 2)
    call('62956', 2, {'62958': reference_bindings['62881']['native_reference'], '62972': c2})
    call('62975', 2, {'63023': supplied['62956']['62969']})
    for node, terminal, bank, target in (('72697', '72700', 156, '23486'), ('72654', '72669', 10, '24427'), ('72689', '72692', 7, '31048')):
        result['local_assignments'].append(dict(node_uid=node, terminal_uid=terminal, sequence_phase=2,
            explicit_paramIdx=bank, control_terminal_uid=target, literal_uid='72708',
            source_literal_raw_hex='0000', decoded_literal_is_hypothetical=True, value=literal_inputs['72708']))
    result['provided_data_numeric_literals'] = {'62820': dict(raw_hex='000001F4', U32_value=500)}
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


def replay_saved_sup_event_56943(payload):
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
        return _encode(project_event_56943(new, None, None, None, None, None,
            event_outputs=payload.get('event_outputs'), completed_sinks=payload.get('completed_sinks', ())))
    reads = payload['local_reads']
    _exact(reads, ('62631', '62938'), 'LOCAL_READ')
    if any(type(value) is not list for value in reads.values()):
        raise ValueError('JSON_40_BOOLEAN_LIST')
    refs = payload['reference_bindings']
    _exact(refs, ('62584', '62881'), 'REFERENCE')
    decoded_refs = {}
    for uid, row in refs.items():
        _exact(row, ('stored_URI_bytes', 'native_reference'), 'REFERENCE_' + uid)
        decoded_refs[uid] = {'stored_URI_bytes': _json_bytes(row['stored_URI_bytes']), 'native_reference': row['native_reference']}
    leaves = payload['native_boundaries']
    _exact(leaves, LEAF_UIDS, 'NATIVE_BOUNDARY')
    decoded_leaves = {}
    for uid, row in leaves.items():
        _exact(row, ('outputs',), 'LEAF_' + uid)
        if uid in ('62647', '62956'):
            ref, err = ('62652', '62663') if uid == '62647' else ('62962', '62969')
            _exact(row['outputs'], (ref, err), 'WRITER_OUTPUT_' + uid)
            decoded_leaves[uid] = {'outputs': {ref: row['outputs'][ref], err: _json_error(row['outputs'][err])}}
        else:
            decoded_leaves[uid] = row
    uw = payload['unwired_inputs']
    _exact(uw, UNWIRED, 'UNWIRED_INPUT')
    decoded_uw = {uid: _json_error(value) if UNWIRED[uid] == 'error' else _json_bytes(value) if UNWIRED[uid] == 'bytes' else value for uid, value in uw.items()}
    return _encode(project_event_56943(new, {uid: tuple(v) for uid, v in reads.items()}, payload['literal_inputs'],
        decoded_refs, decoded_leaves, decoded_uw, event_outputs=payload.get('event_outputs'), completed_sinks=payload.get('completed_sinks', ())))


__all__ = ['project_event_56943', 'replay_saved_sup_event_56943', 'ErrorValue']
