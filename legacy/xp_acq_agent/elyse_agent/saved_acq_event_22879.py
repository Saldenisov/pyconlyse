"""Bounded APP-00 Event43/frame22879 supplied-source-body replay, Python3.4.

Case, sequence, constants, local reads/writes and bundles are explicit.
Native leaves never execute. Their arguments, returns and completion are
supplied; the finite schedule gives one partial-order linearization only.
"""
from collections import namedtuple

SOURCE_ID = 'APP-00'
EVENT_UID = '43'
FRAME_UID = '22879'
SOURCE_VERSION = '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
SAVED_URI = 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'
STAGES = ('23304', '23392', '24497', '25430')
Step = namedtuple('Step', 'node_uid')
LeafCall = namedtuple('LeafCall', 'node_uid')
LeafReturn = namedtuple('LeafReturn', 'node_uid')
StageComplete = namedtuple('StageComplete', 'frame_uid')
ErrorValue = namedtuple('ErrorValue', 'status code source')

# Exact source identities; each raw gRefDCO has an explicit paramIdx.
READS = {
    '23351': (0, 15, '5994', '23354', 32),
    '23424': (1, 15, '5994', '23428', 32),
    '25058': (2, 36, '71105', '25263', 29),
    '24858': (2, 44, '66774', '24865', 77),
    '25526': (3, 36, '71105', '25553', 29),
}
BUNDLES = {
    '23340': (0, '23351', '23346', '23342', (('23347', 4, False, '23310'),)),
    '23414': (1, '23424', '23419', '23416', (('23420', 4, True, '23398'),)),
    '24908': (2, '25058', '25023', '25012', (('25029', 5, False, '24561'),)),
    '24619': (2, '24858', '24648', '24630',
              (('24655', 14, False, '24511'), ('24681', 17, True, '24536'),
               ('46337', 15, False, '24511'))),
}
WRITES = {
    '23331': (0, 15, '5994', '23334', '23340'),
    '23357': (0, 35, '9101', '23360', None),
    '23408': (1, 15, '5994', '23411', '23414'),
    '24872': (2, 36, '71105', '24883', '24908'),
    '24589': (2, 44, '66774', '24601', '24619'),
}
LEAVES = {'23365': 0, '25510': 3, '25625': 3, '25703': 3}
REQUIRED = (
    frozenset(('23351', '23340', '23331', '23357', '23365')),
    frozenset(('23424', '23414', '23408')),
    frozenset(('25058', '24908', '24872', '24858', '24619', '24589')),
    frozenset(('25526', '25625', '25703', '25510')),
)
CONSTANTS = (
    (('23310', False), ('23320', True)),
    (('23398', True),),
    (('24511', False), ('24536', True), ('24561', False)),
    (('25448', 100), ('25486', SAVED_URI)),
)
LIMITS = dict(execution_allowed=False, external_calls_executed=False,
    hardware_writes=False, native_runtime_equivalence=False,
    whole_event_equivalence=False, whole_vi_equivalence=False,
    native_default_qualified=False, native_ref_interpretation_qualified=False,
    psp_delivery_qualified=False, wait_units_or_pulse_duration_qualified=False,
    snapshot_equality_qualified=False, scheduler_qualified=False,
    event_selection_qualified=False, event_acknowledgement_qualified=False,
    native_cluster_decode_qualified=False)


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise TypeError(label + ' requires an explicit bounded integer')


def _error(value):
    if type(value) is not ErrorValue or type(value.status) is not bool or type(value.source) is not str:
        raise TypeError('explicit ErrorValue(status bool, code I32, source str) required')
    _integer(value.code, -2147483648, 2147483647, 'error code')


def _bank(value, count):
    if type(value) is not tuple or len(value) != count or any(type(bit) is not bool for bit in value):
        raise TypeError('explicit tuple of ' + str(count) + ' Boolean fields required')


def _exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(label + ' requires exact fields')


def _value(mapping, key, label):
    if type(mapping) is not dict or key not in mapping:
        raise ValueError(label + ' requires explicit source UID ' + key)
    return mapping[key]


def _outputs(uid, value):
    if uid in ('23365', '25510'):
        terminal = '23367' if uid == '23365' else '25512'
        _exact(value, (terminal,), 'Wait return')
        _integer(value[terminal], 0, 4294967295, 'Wait unused output')
    elif uid == '25625':
        _exact(value, ('25683', '25697'), 'PSP return')
        _error(value['25697'])
    else:
        _exact(value, ('25706', '25709', '25721', '25724', '25727'), 'handler return')
        if type(value['25706']) is not bool or type(value['25721']) is not str or type(value['25727']) is not str:
            raise TypeError('explicit handler Boolean/String outputs required')
        _integer(value['25709'], -2147483648, 2147483647, 'handler unused I32 output')
        _error(value['25724'])


def replay_event(new_value, schedule, *, snapshots, leaf_returns, unwired_inputs, reference_binding):
    """Replay selected Boolean arm and one supplied finite partial schedule.

    False returns before reading any body-input value. True consumes each
    snapshot/leaf result only at its token. Different reads of one saved
    bank remain independent. LeafCall starts an inert request; LeafReturn
    supplies completion. StageComplete joins all saved business nodes,
    without inspecting return success. Prefixes may end anywhere.
    """
    if type(new_value) is not bool:
        raise TypeError('explicit Boolean event NewVal required')
    result = dict(source_id=SOURCE_ID, event_uid=EVENT_UID, frame_uid=FRAME_UID,
        scope='SUPPLIED_ACQ_FRAME22879_BODY', source_version=SOURCE_VERSION, new_value=new_value,
        selected_case_frame='23275' if new_value else '23269',
        event_data_consumed_ports=('23211',),
        event_data_unconsumed_ports=('23173', '23181', '23190', '23200'),
        event_data_unconsumed_input_ports=('23164',),
        log=[], writes=[], leaf_calls=[], leaf_returns=[], completed_stages=[],
        active_stage=None, pending_leaf_uids=(), remaining_node_uids=(),
        selected_body_completed=not new_value, schedule_complete=not new_value)
    result.update(LIMITS)
    result['log'].extend((dict(kind='event_value', node_uid='23160', terminal_uid='23211', value=new_value),
                          dict(kind='constant', node_uid='25950', value=150),
                          dict(kind='case', node_uid='23245', selected_frame=result['selected_case_frame'])))
    if not new_value:
        return result
    if type(schedule) is not tuple or len(schedule) > 26:
        raise ValueError('bounded tuple of inert source-body tokens required')
    values, done, started, returned = {}, set(), set(), {}
    stage = 0
    result['log'].append(dict(kind='sequence', node_uid='23281', stage_uids=STAGES))

    def enter_stage(index):
        for uid, value in CONSTANTS[index]:
            result['log'].append(dict(kind='constant', node_uid=uid, value=value,
                saved_refnum_descriptor=uid == '25486'))

    enter_stage(0)
    for token in schedule:
        if stage == 4:
            raise ValueError('no token follows the completed selected body')
        if type(token) is StageComplete:
            if type(token.frame_uid) is not str or token.frame_uid != STAGES[stage]:
                raise ValueError('current saved sequence frame UID required')
            if not REQUIRED[stage] <= done:
                raise ValueError('stage completion requires every saved dependency and supplied leaf completion')
            result['completed_stages'].append(token.frame_uid)
            result['log'].append(dict(kind='stage_complete', frame_uid=token.frame_uid, sequence_uid='23281'))
            stage += 1
            if stage < 4:
                enter_stage(stage)
            continue
        if type(token) not in (Step, LeafCall, LeafReturn) or type(token.node_uid) is not str:
            raise TypeError('known inert token and exact source node UID required')
        uid = token.node_uid
        if type(token) is Step:
            if uid in done:
                raise ValueError('source node can complete only once')
            if uid in READS:
                owner, bank, target, terminal, count = READS[uid]
                if owner != stage:
                    raise ValueError('local read requires its current sequence frame')
                value = _value(snapshots, uid, 'local snapshot')
                _bank(value, count)
                values[uid] = value
                result['log'].append(dict(kind='local_read', node_uid=uid, terminal_uid=terminal,
                    bank_index=bank, control_terminal_uid=target, value=value))
            elif uid in BUNDLES:
                owner, read, base, output, assignments = BUNDLES[uid]
                if owner != stage or read not in done:
                    raise ValueError('bundle requires current frame and completed saved local read')
                copy = list(values[read])
                inputs = {base: values[read]}
                changes = []
                for field, index, bit, literal in assignments:
                    copy[index] = bit
                    inputs[field] = bit
                    changes.append(dict(terminal_uid=field, field_index=index,
                        constant_uid=literal, value=bit))
                values[uid] = tuple(copy)
                result['log'].append(dict(kind='bundle', node_uid=uid,
                    input_ports=inputs, output_terminal_uid=output,
                    assignments=changes, value=values[uid]))
            elif uid in WRITES:
                owner, bank, target, terminal, bundle = WRITES[uid]
                if owner != stage or (bundle is not None and bundle not in done):
                    raise ValueError('local write requires current frame and completed saved bundle')
                value = True if bundle is None else values[bundle]
                row = dict(kind='local_write', node_uid=uid, terminal_uid=terminal,
                    bank_index=bank, control_terminal_uid=target, value=value)
                result['writes'].append(row)
                result['log'].append(row)
            else:
                raise ValueError('Step requires a saved local or bundle node')
            done.add(uid)
        elif type(token) is LeafCall:
            if uid not in LEAVES or LEAVES[uid] != stage or uid in started:
                raise ValueError('one current saved native leaf call required')
            if uid in ('23365', '25510'):
                inputs = {'23370' if uid == '23365' else '25516': 150 if uid == '23365' else 100}
            elif uid == '25625':
                if '25526' not in done:
                    raise ValueError('PSP call requires its separate saved DPS read')
                _exact(reference_binding, ('constant_uid', 'saved_uri', 'native_ref'), 'supplied reference binding')
                if reference_binding['constant_uid'] != '25486' or reference_binding['saved_uri'] != SAVED_URI:
                    raise ValueError('matching saved Refnum constant/URI required')
                error = _value(unwired_inputs, '25694', 'PSP unwired error input')
                _error(error)
                inputs = {'25676': reference_binding['native_ref'], '25694': error, '25700': values['25526']}
            else:
                if '25625' not in done:
                    raise ValueError('handler call requires the wired supplied PSP error output')
                inputs = {uid_: _value(unwired_inputs, uid_, 'handler unwired input')
                          for uid_ in ('25712', '25715', '25718', '25765')}
                _integer(inputs['25715'], -2147483648, 2147483647, 'handler unwired I32')
                _integer(inputs['25765'], 0, 65535, 'handler unwired U16')
                if type(inputs['25718']) is not str:
                    raise TypeError('handler unwired String required')
                inputs['25887'] = returned['25625']['25697']
            row = dict(kind='leaf_call', node_uid=uid, input_ports=inputs,
                unwired_input_ports=('25694',) if uid == '25625' else
                    (('25712', '25715', '25718', '25765') if uid == '25703' else ()),
                supplied_ref_interpretation=uid == '25625')
            started.add(uid)
            result['leaf_calls'].append(row)
            result['log'].append(row)
        else:
            if uid not in LEAVES or LEAVES[uid] != stage or uid not in started or uid in done:
                raise ValueError('leaf return requires one started current native leaf')
            value = _value(leaf_returns, uid, 'native supplied return')
            _outputs(uid, value)
            returned[uid] = value
            done.add(uid)
            row = dict(kind='leaf_return', node_uid=uid, output_ports=value,
                consumed_output_ports=('25697',) if uid == '25625' else (),
                success_does_not_gate_stage=True)
            result['leaf_returns'].append(row)
            result['log'].append(row)
    result['active_stage'] = STAGES[stage] if stage < 4 else None
    result['pending_leaf_uids'] = tuple(uid for uid in sorted(started) if uid not in done)
    result['remaining_node_uids'] = tuple(sorted(REQUIRED[stage] - done)) if stage < 4 else ()
    result['selected_body_completed'] = stage == 4
    result['schedule_complete'] = stage == 4
    return result


def _json_error(value):
    _exact(value, ('status', 'code', 'source'), 'JSON error value')
    result = ErrorValue(value['status'], value['code'], value['source'])
    _error(result)
    return result


def _json_tree(value, depth=0):
    if depth > 32:
        raise ValueError('bounded JSON value nesting required')
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if value != value or value in (float('inf'), float('-inf')):
            raise ValueError('finite JSON number required')
        return value
    if type(value) is ErrorValue:
        return dict(status=value.status, code=value.code, source=value.source)
    if type(value) in (list, tuple):
        return [_json_tree(item, depth + 1) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _json_tree(item, depth + 1) for key, item in value.items()}
    raise TypeError('inert JSON value required')


def replay_saved_acq_event_22879(payload):
    """Exact JSON boundary; unselected False body values remain unaccessed.

    On True, maps allow known source keys; only tokens consuming those
    values decode them. Native references/Void values are supplied JSON
    representations, never native handles or native default assumptions.
    """
    _exact(payload, ('source_id', 'event_uid', 'frame_uid', 'new_value', 'schedule',
        'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'), 'JSON replay')
    if payload['source_id'] != SOURCE_ID or payload['event_uid'] != EVENT_UID or payload['frame_uid'] != FRAME_UID:
        raise ValueError('exact APP-00 Event43/frame22879 identity required')
    new_value = payload['new_value']
    if type(new_value) is not bool:
        raise TypeError('explicit Boolean event NewVal required')
    if not new_value:
        return _json_tree(replay_event(False, None, snapshots=None, leaf_returns=None,
            unwired_inputs=None, reference_binding=None))
    rows = payload['schedule']
    if type(rows) is not list or len(rows) > 26:
        raise ValueError('bounded JSON schedule list required')
    classes = {'step': Step, 'leaf_call': LeafCall, 'leaf_return': LeafReturn, 'stage_complete': StageComplete}
    schedule = []
    for row in rows:
        _exact(row, ('kind', 'uid'), 'JSON schedule token')
        if type(row['kind']) is not str or row['kind'] not in classes or type(row['uid']) is not str:
            raise ValueError('known JSON schedule token/source UID required')
        schedule.append(classes[row['kind']](row['uid']))
    for key, allowed in (('snapshots', READS), ('leaf_returns', LEAVES),
                         ('unwired_inputs', ('25694', '25712', '25715', '25718', '25765'))):
        value = payload[key]
        if type(value) is not dict or not set(value) <= set(allowed):
            raise ValueError('known source keys required in ' + key)
    snapshots, returns, unwired = {}, {}, {}
    binding = None
    for token in schedule:
        uid = token.frame_uid if type(token) is StageComplete else token.node_uid
        if type(token) is Step and uid in READS:
            value = _value(payload['snapshots'], uid, 'JSON snapshot')
            if type(value) is not list:
                raise TypeError('JSON snapshot list required')
            snapshots[uid] = tuple(value)
        elif type(token) is LeafReturn and uid in LEAVES:
            value = _value(payload['leaf_returns'], uid, 'JSON native supplied return')
            if type(value) is not dict:
                raise TypeError('JSON output-port map required')
            returns[uid] = dict(value)
            if uid == '25625':
                returns[uid]['25697'] = _json_error(_value(value, '25697', 'PSP error output'))
            elif uid == '25703':
                returns[uid]['25724'] = _json_error(_value(value, '25724', 'handler error output'))
            _json_tree(returns[uid])
        elif type(token) is LeafCall and uid == '25625':
            unwired['25694'] = _json_error(_value(payload['unwired_inputs'], '25694', 'PSP unwired error'))
            binding = _value(payload, 'reference_binding', 'JSON reference binding')
            _json_tree(binding)
        elif type(token) is LeafCall and uid == '25703':
            for terminal in ('25712', '25715', '25718', '25765'):
                unwired[terminal] = _json_tree(_value(payload['unwired_inputs'], terminal, 'handler unwired input'))
    return _json_tree(replay_event(new_value, tuple(schedule), snapshots=snapshots,
        leaf_returns=returns, unwired_inputs=unwired, reference_binding=binding))
