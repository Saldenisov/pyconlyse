"""Saved Acquisition caller routing from explicit external returns; Python3.4.

No initializer/Clear Errors/Clear Task call is executed. Reference tokens have
no native validity, and a returned error never proves initialization success.
"""
from collections import namedtuple
from .saved_xnode import ErrorValue

STAGES = (
    ('593', '1_ACQ_INIT_NI6602.vi', '383', '1250', ((21, 8),)),
    ('262', '1_ACQ_INIT_NI6071E.vi', '1532', '1526', ((23, 1), (24, 1))),
    ('500', '1_ACQ_INIT_DIO96.vi', '1416', '1410', ((22, 6),)),
    ('620', '1_ACQ_INIT_NI6703.vi', '1843', '1837', ((25, 4),)),
)
AI_ARGUMENTS = (('trigger_c1', '/1/PFI0'), ('trigger_c2', '/2/PFI0'),
                ('rate_hz', 5000.0), ('samples_per_channel', 10))
FALLBACK_ARGUMENTS = (('trigger_c1', '/1/20MHzTimebase'),
                      ('trigger_c2', '/2/20MHzTimebase'),
                      ('rate_hz', 5000.0), ('samples_per_channel', 10))
OpaqueReference = namedtuple('OpaqueReference', 'token')
InitializerFixture = namedtuple('InitializerFixture', 'tasks error_out')
CallerStep = namedtuple('CallerStep', 'node_uid operation error_in error_out arguments local_assignments')
CallerProjection = namedtuple('CallerProjection', 'steps next_read_error')
AiFallbackProjection = namedtuple('AiFallbackProjection', 'steps original_read_error sequence_local_306')
UNWIRED = namedtuple('UnwiredValue', 'connection')('unwired')


def route_initializer_values(fixtures, clear_returns, unwired):
    """Shared pure body; representation validation belongs to each typed facade.

    Both facades pass validated immutable fixtures. Objects are retained by
    identity; there is no callback, native operation or synthetic success.
    """
    steps = []
    error = unwired
    for fixture, (uid, name, clear_uid, unused_frame, banks) in zip(fixtures, STAGES):
        assignments = []
        offset = 0
        for bank, count in banks:
            refs = fixture.tasks[offset:offset + count]
            assignments.append((bank, refs[0] if count == 1 else refs))
            offset += count
        steps.append(CallerStep(uid, name, error, fixture.error_out,
                                AI_ARGUMENTS if uid == '262' else (), tuple(assignments)))
        error = fixture.error_out
        if error.status:
            returned = clear_returns[clear_uid]
            steps.append(CallerStep(clear_uid, 'Clear Errors.vi', error, returned, (), ()))
            error = returned
    return CallerProjection(tuple(steps), error)


def route_ai_test_values(read_error, fallback_result, clear_returns):
    """Shared error-dependent suffix. Original read error has a separate lane."""
    if not read_error.status:
        return AiFallbackProjection((), read_error, read_error)
    steps = []
    error = read_error
    for uid, operation, arguments in (
        ('2134', 'Clear Errors.vi', ()),
        ('4034', 'DAQmx Clear Task.vi', (('task_snapshot_bank', 23),)),
        ('7931', 'DAQmx Clear Task.vi', (('task_snapshot_bank', 24),)),
    ):
        steps.append(CallerStep(uid, operation, error, clear_returns[uid], arguments, ()))
        error = clear_returns[uid]
    error_out = fallback_result.error_out
    steps.append(CallerStep('1198', '1_ACQ_INIT_NI6071E.vi', error, error_out,
                   FALLBACK_ARGUMENTS, ((23, fallback_result.tasks[0]), (24, fallback_result.tasks[1]))))
    if error_out.status:
        steps.append(CallerStep('2268', 'Clear Errors.vi', error_out, clear_returns['2268'], (), ()))
        error_out = clear_returns['2268']
    return AiFallbackProjection(tuple(steps), read_error, error_out)


def require_error(error):
    if type(error) is not ErrorValue or type(error.status) is not bool or type(error.code) is not int or type(error.source) is not str:
        raise TypeError('explicit bool/int/str ErrorValue required')


def require_fixture(fixture, cardinality):
    if type(fixture) is not InitializerFixture or type(fixture.tasks) is not tuple:
        raise TypeError('immutable explicit initializer fixture required')
    require_error(fixture.error_out)
    if len(fixture.tasks) != cardinality:
        raise ValueError('caller task-output cardinality differs from saved source')
    if any(type(t) is not OpaqueReference or type(t.token) is not str or not t.token for t in fixture.tasks):
        raise TypeError('explicit opaque reference tokens required')


def require_clears(values, selected):
    if type(values) is not dict or set(values) != selected:
        raise ValueError('Clear Errors fixtures must match selected error arms exactly')
    for error in values.values():
        require_error(error)


def project_initializer_frame(fixtures, clear_returns):
    if type(fixtures) is not tuple or len(fixtures) != len(STAGES):
        raise TypeError('four ordered initializer fixtures required')
    for fixture, stage in zip(fixtures, STAGES):
        require_fixture(fixture, sum(count for unused_bank, count in stage[4]))
    selected = {stage[2] for fixture, stage in zip(fixtures, STAGES) if fixture.error_out.status}
    require_clears(clear_returns, selected)
    return route_initializer_values(fixtures, clear_returns, UNWIRED)


def project_ai_test_frame(read_error, fallback_result=None, clear_returns=None):
    require_error(read_error)
    if not read_error.status:
        if fallback_result is not None or clear_returns not in (None, {}):
            raise ValueError('no-error test read cannot consume fallback fixtures')
        return route_ai_test_values(read_error, None, None)
    require_fixture(fallback_result, 2)
    selected = {'2134', '4034', '7931'}
    if fallback_result.error_out.status:
        selected.add('2268')
    require_clears(clear_returns, selected)
    return route_ai_test_values(read_error, fallback_result, clear_returns)


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('exact replay fields required: ' + ','.join(fields))


def json_error(value):
    exact(value, ('status', 'code', 'source'))
    error = ErrorValue(value['status'], value['code'], value['source'])
    require_error(error)
    if not -(2 ** 31) <= error.code < 2 ** 31 or len(error.source) > 1024:
        raise ValueError('replay error storage limits exceeded')
    return error


def json_fixture(value):
    exact(value, ('tasks', 'error_out'))
    if type(value['tasks']) is not list or len(value['tasks']) > 8:
        raise ValueError('bounded opaque reference list required')
    if any(type(t) is not str or not 1 <= len(t) <= 128 for t in value['tasks']):
        raise ValueError('bounded nonempty opaque reference tokens required')
    return InitializerFixture(tuple(OpaqueReference(t) for t in value['tasks']), json_error(value['error_out']))


def json_clears(value):
    if type(value) is not dict or len(value) > 4:
        raise ValueError('bounded explicit Clear return dictionary required')
    return {key:json_error(error) for key,error in value.items()}


def encode_error(error):
    return dict(connection='unwired') if error is UNWIRED else dict(error._asdict())


def encode_step(step):
    def reference(value):
        return [t.token for t in value] if type(value) is tuple else value.token
    return dict(node_uid=step.node_uid, operation=step.operation, error_in=encode_error(step.error_in),
                error_out=encode_error(step.error_out), arguments=dict(step.arguments),
                local_assignments=[dict(bank=bank, references=reference(value)) for bank,value in step.local_assignments])


def replay_saved_initializer(payload):
    if type(payload) is not dict or payload.get('source_id') != 'APP-00':
        raise ValueError('APP-00 saved caller required')
    mode = payload.get('uid')
    if mode == '227':
        exact(payload, ('source_id', 'uid', 'fixtures', 'clear_returns'))
        if type(payload['fixtures']) is not list or len(payload['fixtures']) != 4:
            raise ValueError('four ordered JSON initializer fixtures required')
        result = project_initializer_frame(tuple(json_fixture(f) for f in payload['fixtures']), json_clears(payload['clear_returns']))
        outputs = dict(next_read_error=encode_error(result.next_read_error))
    elif mode == '133':
        exact(payload, ('source_id', 'uid', 'read_error', 'fallback_result', 'clear_returns'))
        fallback = None if payload['fallback_result'] is None else json_fixture(payload['fallback_result'])
        clears = None if payload['clear_returns'] is None else json_clears(payload['clear_returns'])
        result = project_ai_test_frame(json_error(payload['read_error']), fallback, clears)
        outputs = dict(original_read_error=encode_error(result.original_read_error),
                       sequence_local_306=encode_error(result.sequence_local_306))
    else:
        raise ValueError('saved frame UID must be227 or133')
    return dict(source_id='APP-00', uid=mode, steps=[encode_step(s) for s in result.steps], outputs=outputs,
                scope='SUPPLIED_RETURN_CALLER_ROUTING', external_calls_executed=False,
                execution_allowed=False, hardware_writes=False, reference_validity_qualified=False,
                whole_lifecycle_equivalence=False)
