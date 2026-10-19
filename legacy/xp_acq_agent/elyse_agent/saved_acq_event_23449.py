"""Bounded APP-00 Event43/frame23449 supplied-source-body replay, Python3.4.

Case, sequence, constants, local reads/writes and bundles are explicit.
Native leaves never execute. Their arguments, returns and completion are
supplied; the finite schedule gives one partial-order linearization only.
"""
from collections import namedtuple

SOURCE_ID = 'APP-00'
EVENT_UID = '43'
FRAME_UID = '23449'
SOURCE_VERSION = '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5'
SAVED_URI = 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'
STAGES = ('31017', '31192', '31360', '31482')
Step = namedtuple('Step', 'node_uid')
LeafCall = namedtuple('LeafCall', 'node_uid')
LeafReturn = namedtuple('LeafReturn', 'node_uid')
StageComplete = namedtuple('StageComplete', 'frame_uid')
ErrorValue = namedtuple('ErrorValue', 'status code source')

# Exact source identities; each raw gRefDCO has an explicit paramIdx.
READS = {
    '31100': (0, 15, '5994', '31103', 32),
    '31258': (1, 15, '5994', '31308', 32),
    '31454': (2, 36, '71105', '31457', 29),
    '31423': (2, 44, '66774', '31430', 77),
    '31526': (3, 36, '71105', '31529', 29),
}
BUNDLES = {
    '31090': (0, '31100', '31095', '31092', (('31096', 17, False, '31035'),)),
    '31243': (1, '31258', '31253', '31245', (('31254', 17, True, '31198'),)),
    '31444': (2, '31454', '31449', '31446', (('31450', 9, False, '31386'),)),
    '31404': (2, '31423', '31411', '31406',
              (('31412', 26, False, '31366'), ('31415', 29, True, '31376'),
               ('49149', 27, False, '31366'))),
}
WRITES = {
    '31082': (0, 15, '5994', '31085', '31090'),
    '31106': (0, 35, '9101', '31109', None),
    '31237': (1, 15, '5994', '31240', '31243'),
    '31433': (2, 36, '71105', '31438', '31444'),
    '31396': (2, 44, '66774', '31399', '31404'),
}
LEAVES = {'31114': 0, '31518': 3, '31532': 3, '41569': 3}
REQUIRED = (
    frozenset(('31100', '31090', '31082', '31106', '31114')),
    frozenset(('31258', '31243', '31237')),
    frozenset(('31454', '31444', '31433', '31423', '31404', '31396')),
    frozenset(('31526', '31532', '41569', '31518')),
)
CONSTANTS = (
    (('31035', False), ('31064', True)),
    (('31198', True),),
    (('31366', False), ('31376', True), ('31386', False)),
    (('31488', 100), ('31500', SAVED_URI)),
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
    if uid in ('31114', '31518'):
        terminal = '31116' if uid == '31114' else '31520'
        _exact(value, (terminal,), 'Wait return')
        _integer(value[terminal], 0, 4294967295, 'Wait unused output')
    elif uid == '31532':
        _exact(value, ('31537', '31543'), 'PSP return')
        _error(value['31543'])
    else:
        _exact(value, ('41572', '41575', '41587', '41590', '41593'), 'handler return')
        if type(value['41572']) is not bool or type(value['41587']) is not str or type(value['41593']) is not str:
            raise TypeError('explicit handler Boolean/String outputs required')
        _integer(value['41575'], -2147483648, 2147483647, 'handler unused I32 output')
        _error(value['41590'])


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
        scope='SUPPLIED_ACQ_FRAME23449_BODY', source_version=SOURCE_VERSION, new_value=new_value,
        selected_case_frame='30965' if new_value else '30947',
        event_data_consumed_ports=('30776',),
        event_data_unconsumed_ports=('23471', '23476', '30637', '30668'),
        event_data_unconsumed_input_ports=('23467',),
        log=[], writes=[], leaf_calls=[], leaf_returns=[], completed_stages=[],
        active_stage=None, pending_leaf_uids=(), remaining_node_uids=(),
        selected_body_completed=not new_value, schedule_complete=not new_value)
    result.update(LIMITS)
    result['log'].extend((dict(kind='event_value', node_uid='23465', terminal_uid='30776', value=new_value),
                          dict(kind='constant', node_uid='41621', value=150),
                          dict(kind='case', node_uid='30860', selected_frame=result['selected_case_frame'])))
    if not new_value:
        return result
    if type(schedule) is not tuple or len(schedule) > 26:
        raise ValueError('bounded tuple of inert source-body tokens required')
    values, done, started, returned = {}, set(), set(), {}
    stage = 0
    result['log'].append(dict(kind='sequence', node_uid='30983', stage_uids=STAGES))

    def enter_stage(index):
        for uid, value in CONSTANTS[index]:
            result['log'].append(dict(kind='constant', node_uid=uid, value=value,
                saved_refnum_descriptor=uid == '31500'))

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
            result['log'].append(dict(kind='stage_complete', frame_uid=token.frame_uid, sequence_uid='30983'))
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
            if uid in ('31114', '31518'):
                inputs = {'31130' if uid == '31114' else '31523': 150 if uid == '31114' else 100}
            elif uid == '31532':
                if '31526' not in done:
                    raise ValueError('PSP call requires its separate saved DPS read')
                _exact(reference_binding, ('constant_uid', 'saved_uri', 'native_ref'), 'supplied reference binding')
                if reference_binding['constant_uid'] != '31500' or reference_binding['saved_uri'] != SAVED_URI:
                    raise ValueError('matching saved Refnum constant/URI required')
                error = _value(unwired_inputs, '31540', 'PSP unwired error input')
                _error(error)
                inputs = {'31534': reference_binding['native_ref'], '31540': error, '31546': values['31526']}
            else:
                if '31532' not in done:
                    raise ValueError('handler call requires the wired supplied PSP error output')
                inputs = {uid_: _value(unwired_inputs, uid_, 'handler unwired input')
                          for uid_ in ('41578', '41581', '41584', '41596')}
                _integer(inputs['41581'], -2147483648, 2147483647, 'handler unwired I32')
                _integer(inputs['41596'], 0, 65535, 'handler unwired U16')
                if type(inputs['41584']) is not str:
                    raise TypeError('handler unwired String required')
                inputs['41599'] = returned['31532']['31543']
            row = dict(kind='leaf_call', node_uid=uid, input_ports=inputs,
                unwired_input_ports=('31540',) if uid == '31532' else
                    (('41578', '41581', '41584', '41596') if uid == '41569' else ()),
                supplied_ref_interpretation=uid == '31532')
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
                consumed_output_ports=('31543',) if uid == '31532' else (),
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


def replay_saved_acq_event_23449(payload):
    """Exact JSON boundary; unselected False body values remain unaccessed.

    On True, maps allow known source keys; only tokens consuming those
    values decode them. Native references/Void values are supplied JSON
    representations, never native handles or native default assumptions.
    """
    _exact(payload, ('source_id', 'event_uid', 'frame_uid', 'new_value', 'schedule',
        'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'), 'JSON replay')
    if payload['source_id'] != SOURCE_ID or payload['event_uid'] != EVENT_UID or payload['frame_uid'] != FRAME_UID:
        raise ValueError('exact APP-00 Event43/frame23449 identity required')
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
                         ('unwired_inputs', ('31540', '41578', '41581', '41584', '41596'))):
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
            if uid == '31532':
                returns[uid]['31543'] = _json_error(_value(value, '31543', 'PSP error output'))
            elif uid == '41569':
                returns[uid]['41590'] = _json_error(_value(value, '41590', 'handler error output'))
            _json_tree(returns[uid])
        elif type(token) is LeafCall and uid == '31532':
            unwired['31540'] = _json_error(_value(payload['unwired_inputs'], '31540', 'PSP unwired error'))
            binding = _value(payload, 'reference_binding', 'JSON reference binding')
            _json_tree(binding)
        elif type(token) is LeafCall and uid == '41569':
            for terminal in ('41578', '41581', '41584', '41596'):
                unwired[terminal] = _json_tree(_value(payload['unwired_inputs'], terminal, 'handler unwired input'))
    return _json_tree(replay_event(new_value, tuple(schedule), snapshots=snapshots,
        leaf_returns=returns, unwired_inputs=unwired, reference_binding=binding))
