"""Bounded APP-00 Event43/frame26012 supplied-source-body replay, Python3.4.

Case, sequence, constants, local reads/writes and bundles are explicit.
Native leaves never execute. Their arguments, returns and completion are
supplied; the finite schedule gives one partial-order linearization only.
"""
from collections import namedtuple

SOURCE_ID = 'APP-00'
EVENT_UID = '43'
FRAME_UID = '26012'
SOURCE_VERSION = '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
SAVED_URI = 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'
STAGES = ('26246', '26330', '26962', '27900')
Step = namedtuple('Step', 'node_uid')
LeafCall = namedtuple('LeafCall', 'node_uid')
LeafReturn = namedtuple('LeafReturn', 'node_uid')
StageComplete = namedtuple('StageComplete', 'frame_uid')
ErrorValue = namedtuple('ErrorValue', 'status code source')

# Exact source identities; each raw gRefDCO has an explicit paramIdx.
READS = {
    '26290': (0, 15, '5994', '26293', 32),
    '26900': (1, 15, '5994', '26917', 32),
    '27807': (2, 36, '71105', '27823', 29),
    '27587': (2, 44, '66774', '27596', 77),
    '28294': (3, 36, '71105', '28303', 29),
}
BUNDLES = {
    '26280': (0, '26290', '26285', '26282', (('26286', 6, False, '26252'),)),
    '26577': (1, '26900', '26683', '26584', (('26684', 6, True, '26336'),)),
    '27650': (2, '27807', '27793', '27742', (('27794', 7, False, '27244'),)),
    '27544': (2, '27587', '27562', '27551',
              (('27568', 20, False, '26980'), ('27577', 23, True, '27089'),
               ('47743', 21, False, '26980'))),
}
WRITES = {
    '26272': (0, 15, '5994', '26275', '26280'),
    '26296': (0, 35, '9101', '26299', None),
    '26356': (1, 15, '5994', '26466', '26577'),
    '27605': (2, 36, '71105', '27614', '27650'),
    '27523': (2, 44, '66774', '27532', '27544'),
}
LEAVES = {'26304': 0, '28273': 3, '28312': 3, '28364': 3}
REQUIRED = (
    frozenset(('26290', '26280', '26272', '26296', '26304')),
    frozenset(('26900', '26577', '26356')),
    frozenset(('27807', '27650', '27605', '27587', '27544', '27523')),
    frozenset(('28294', '28312', '28364', '28273')),
)
CONSTANTS = (
    (('26252', False), ('26262', True)),
    (('26336', True),),
    (('26980', False), ('27089', True), ('27244', False)),
    (('27919', 100), ('27965', SAVED_URI)),
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
    if uid in ('26304', '28273'):
        terminal = '26306' if uid == '26304' else '28276'
        _exact(value, (terminal,), 'Wait return')
        _integer(value[terminal], 0, 4294967295, 'Wait unused output')
    elif uid == '28312':
        _exact(value, ('28328', '28346'), 'PSP return')
        _error(value['28346'])
    else:
        _exact(value, ('28373', '28382', '28418', '28427', '28436'), 'handler return')
        if type(value['28373']) is not bool or type(value['28418']) is not str or type(value['28436']) is not str:
            raise TypeError('explicit handler Boolean/String outputs required')
        _integer(value['28382'], -2147483648, 2147483647, 'handler unused I32 output')
        _error(value['28427'])


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
        scope='SUPPLIED_ACQ_FRAME26012_BODY', source_version=SOURCE_VERSION, new_value=new_value,
        selected_case_frame='26229' if new_value else '26217',
        event_data_consumed_ports=('26127',),
        event_data_unconsumed_ports=('26096', '26100', '26109', '26118'),
        event_data_unconsumed_input_ports=('26088',),
        log=[], writes=[], leaf_calls=[], leaf_returns=[], completed_stages=[],
        active_stage=None, pending_leaf_uids=(), remaining_node_uids=(),
        selected_body_completed=not new_value, schedule_complete=not new_value)
    result.update(LIMITS)
    result['log'].extend((dict(kind='event_value', node_uid='26082', terminal_uid='26127', value=new_value),
                          dict(kind='constant', node_uid='28521', value=150),
                          dict(kind='case', node_uid='26159', selected_frame=result['selected_case_frame'])))
    if not new_value:
        return result
    if type(schedule) is not tuple or len(schedule) > 26:
        raise ValueError('bounded tuple of inert source-body tokens required')
    values, done, started, returned = {}, set(), set(), {}
    stage = 0
    result['log'].append(dict(kind='sequence', node_uid='26235', stage_uids=STAGES))

    def enter_stage(index):
        for uid, value in CONSTANTS[index]:
            result['log'].append(dict(kind='constant', node_uid=uid, value=value,
                saved_refnum_descriptor=uid == '27965'))

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
            result['log'].append(dict(kind='stage_complete', frame_uid=token.frame_uid, sequence_uid='26235'))
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
            if uid in ('26304', '28273'):
                inputs = {'26309' if uid == '26304' else '28285': 150 if uid == '26304' else 100}
            elif uid == '28312':
                if '28294' not in done:
                    raise ValueError('PSP call requires its separate saved DPS read')
                _exact(reference_binding, ('constant_uid', 'saved_uri', 'native_ref'), 'supplied reference binding')
                if reference_binding['constant_uid'] != '27965' or reference_binding['saved_uri'] != SAVED_URI:
                    raise ValueError('matching saved Refnum constant/URI required')
                error = _value(unwired_inputs, '28337', 'PSP unwired error input')
                _error(error)
                inputs = {'28319': reference_binding['native_ref'], '28337': error, '28355': values['28294']}
            else:
                if '28312' not in done:
                    raise ValueError('handler call requires the wired supplied PSP error output')
                inputs = {uid_: _value(unwired_inputs, uid_, 'handler unwired input')
                          for uid_ in ('28391', '28400', '28409', '28445')}
                _integer(inputs['28400'], -2147483648, 2147483647, 'handler unwired I32')
                _integer(inputs['28445'], 0, 65535, 'handler unwired U16')
                if type(inputs['28409']) is not str:
                    raise TypeError('handler unwired String required')
                inputs['28454'] = returned['28312']['28346']
            row = dict(kind='leaf_call', node_uid=uid, input_ports=inputs,
                unwired_input_ports=('28337',) if uid == '28312' else
                    (('28391', '28400', '28409', '28445') if uid == '28364' else ()),
                supplied_ref_interpretation=uid == '28312')
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
                consumed_output_ports=('28346',) if uid == '28312' else (),
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


def replay_saved_acq_event_26012(payload):
    """Exact JSON boundary; unselected False body values remain unaccessed.

    On True, maps allow known source keys; only tokens consuming those
    values decode them. Native references/Void values are supplied JSON
    representations, never native handles or native default assumptions.
    """
    _exact(payload, ('source_id', 'event_uid', 'frame_uid', 'new_value', 'schedule',
        'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'), 'JSON replay')
    if payload['source_id'] != SOURCE_ID or payload['event_uid'] != EVENT_UID or payload['frame_uid'] != FRAME_UID:
        raise ValueError('exact APP-00 Event43/frame26012 identity required')
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
                         ('unwired_inputs', ('28337', '28391', '28400', '28409', '28445'))):
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
            if uid == '28312':
                returns[uid]['28346'] = _json_error(_value(value, '28346', 'PSP error output'))
            elif uid == '28364':
                returns[uid]['28427'] = _json_error(_value(value, '28427', 'handler error output'))
            _json_tree(returns[uid])
        elif type(token) is LeafCall and uid == '28312':
            unwired['28337'] = _json_error(_value(payload['unwired_inputs'], '28337', 'PSP unwired error'))
            binding = _value(payload, 'reference_binding', 'JSON reference binding')
            _json_tree(binding)
        elif type(token) is LeafCall and uid == '28364':
            for terminal in ('28391', '28400', '28409', '28445'):
                unwired[terminal] = _json_tree(_value(payload['unwired_inputs'], terminal, 'handler unwired input'))
    return _json_tree(replay_event(new_value, tuple(schedule), snapshots=snapshots,
        leaf_returns=returns, unwired_inputs=unwired, reference_binding=binding))
