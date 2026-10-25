"""Real manual-approval consumption with temporary files and fake Tango only."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.web.test_acq_control_api import setup_api, request_command, ROOT, writes
from tests.web._hardware_authorization_test_support import simulate_hardware_authorization_service_acl
from tests.web import test_acq_control_api as control_tests


NONCE = 'a' * 64


@pytest.fixture
def approval_setup(setup_api, tmp_path, monkeypatch, request):
    api = control_tests.api
    from hardware_authorization import authorize_runtime_operation
    monkeypatch.setattr(api, 'authorize_runtime_operation', authorize_runtime_operation)
    sync = getattr(request, 'param', None) == 'sync'
    command = request_command(operation='counter_timing.set', value=dict(counter=0, delay_us=1.25, width_us=3.5)) if sync else request_command(operation='ht_voltage.set', value=6.7)
    value_schema = dict(type='object', required=['counter', 'delay_us', 'width_us'], additionalProperties=False,
        properties={'counter': {'type': 'integer', 'minimum': 0, 'maximum': 7},
                    'delay_us': {'type': 'number', 'minimum': 0, 'maximum': 2147483647 / 20.0},
                    'width_us': {'type': 'number', 'minimum': 0, 'maximum': 2147483647 / 20.0}}) if sync else {'type': 'number', 'minimum': 0, 'maximum': 20}
    intent = api.hardware_intent(command)
    root = tmp_path / 'external-approval-fixture'
    root.mkdir()
    policy_path = root / 'policy.json'
    approval_dir, consumed_dir = root / 'approvals', root / 'consumed'
    approval_dir.mkdir()
    consumed_dir.mkdir()
    policy = dict(version=1, subjects={'operator-test': {'roles': ['operator']}},
        roles={'operator': {intent.route_id: ['execute']}}, operations=[dict(
            method='POST', route_id=intent.route_id, action='execute', targets=list(intent.targets), roles=['operator'],
            args=dict(type='object', required=list(intent.args), additionalProperties=False, properties={
                'operation': {'type': 'string', 'enum': [command['operation']]},
                'value': value_schema,
                'session_id': {'type': 'string', 'min_length': 32, 'max_length': 32, 'pattern': '^[0-9a-f]{32}$'},
                'expected_revision': {'type': 'integer', 'minimum': 0, 'maximum': 2**53 - 1},
            }))])
    policy_path.write_text(json.dumps(policy), encoding='utf-8')
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'true')
    monkeypatch.setenv('PYCONLYSE_HARDWARE_POLICY_PATH', str(policy_path))
    monkeypatch.setenv('PYCONLYSE_HARDWARE_APPROVAL_DIR', str(approval_dir))
    monkeypatch.setenv('PYCONLYSE_HARDWARE_CONSUMED_DIR', str(consumed_dir))
    simulate_hardware_authorization_service_acl(monkeypatch, policy_path=policy_path,
        approval_dir=approval_dir, consumed_dir=consumed_dir)

    def approve(**changes):
        now = datetime.now(timezone.utc)
        value = dict(version=1, subject='operator-test', role='operator', method=intent.method,
            route_id=intent.route_id, action=intent.action, targets=list(intent.targets), args=intent.args,
            nonce=NONCE, approved_by='offline test fixture', hardware_safe=True,
            issued_at=now.isoformat(), expires_at=(now + timedelta(minutes=2)).isoformat())
        value.update(changes)
        (approval_dir / (NONCE + '.json')).write_text(json.dumps(value), encoding='utf-8')

    def submit(request=None, nonce=NONCE):
        headers = dict(setup_api[2])
        if nonce is not None:
            headers['X-PYCONLYSE-HARDWARE-APPROVAL'] = nonce
        return setup_api[1].post(ROOT + '/commands', json=request or command, headers=headers)

    return setup_api, command, intent, consumed_dir, approve, submit


def test_jwt_and_boolean_confirmation_without_approval_cannot_touch_journal_or_tango(approval_setup):
    setup, command, intent, consumed, approve, submit = approval_setup
    response = submit(nonce=None)
    assert response.status_code == 428, response.json
    assert response.json['code'] == 'hardware_approval_required'
    assert response.json['schema_version'] == 1
    assert response.json['receipt'] == dict(command_id=command['command_id'],
        session_id=command['session_id'], operation=command['operation'], outcome='REJECTED',
        hardware_acknowledged=False, automatic_retry=False, dispatch_attempted=False,
        error=response.json['error'])
    assert setup[4] == []
    assert not Path(setup[0].config['ELYSE_CONTROL_STATE_DB']).exists()
    assert not list(consumed.iterdir())


def test_development_mode_does_not_bypass_acquisition_manual_approval(approval_setup, monkeypatch):
    setup, command, intent, consumed, approve, submit = approval_setup
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    response = submit(nonce=None)
    assert response.status_code == 428, response.json
    assert setup[4] == []
    assert not Path(setup[0].config['ELYSE_CONTROL_STATE_DB']).exists()


def test_missing_external_policy_is_rejected_before_journal_or_tango(approval_setup, monkeypatch):
    setup, command, intent, consumed, approve, submit = approval_setup
    monkeypatch.delenv('PYCONLYSE_HARDWARE_POLICY_PATH')
    response = submit()
    assert response.status_code == 403, response.json
    assert setup[4] == []
    assert not Path(setup[0].config['ELYSE_CONTROL_STATE_DB']).exists()


def test_optional_false_cannot_downgrade_required_production_authorization(approval_setup):
    from hardware_authorization import authorize_runtime_operation, AuthorizationError
    setup, command, intent, consumed, approve, submit = approval_setup
    with pytest.raises(AuthorizationError) as error:
        authorize_runtime_operation(intent, None, subject='operator-test', required=False)
    assert error.value.status_code == 428
    assert setup[4] == []


@pytest.mark.parametrize('field,value', [
    ('value', 6.8), ('session_id', 'c' * 32), ('expected_revision', 8),
    ('operation', 'faraday_1.en_pulse'),
])
def test_approval_is_bound_to_numeric_target_operation_boot_and_revision(approval_setup, field, value):
    setup, command, intent, consumed, approve, submit = approval_setup
    args = dict(intent.args, **{field: value})
    approve(args=args)
    response = submit()
    assert response.status_code == 409, response.json
    assert response.json['receipt']['command_id'] == command['command_id']
    assert response.json['receipt']['dispatch_attempted'] is False
    assert setup[4] == []
    assert not Path(setup[0].config['ELYSE_CONTROL_STATE_DB']).exists()
    assert not list(consumed.iterdir())


def test_valid_one_use_approval_is_consumed_before_exact_tango_intent_and_cannot_be_reused(approval_setup):
    setup, command, intent, consumed, approve, submit = approval_setup
    approve()
    first = submit()
    assert first.status_code == 200, first.json
    assert writes(setup) == [('command', 'ExecuteCommand', command)]
    assert len(list(consumed.iterdir())) == 1
    before = list(setup[4])
    again = submit(dict(command, command_id='c' * 32))
    assert again.status_code == 409, again.json
    assert setup[4] == before


def test_predispatch_rejection_does_not_clear_existing_unknown_server_history(approval_setup):
    setup, command, intent, consumed, approve, submit = approval_setup
    from tests.web import test_acq_control_api as control_tests
    api = control_tests.api
    previous = dict(command, command_id='d' * 32)
    with setup[0].app_context():
        db = api._database()
        try:
            db.execute('INSERT INTO commands VALUES (?,?,?)', (previous['command_id'],
                json.dumps(previous), json.dumps(api._receipt(previous, 'INDETERMINATE'))))
        finally:
            db.close()
    response = submit(nonce=None)
    assert response.status_code == 428
    assert response.json['receipt']['command_id'] == command['command_id']
    assert setup[4] == []
    with setup[0].app_context():
        assert api._history() == [api._receipt(previous, 'INDETERMINATE')]


def test_wrong_target_or_expired_approval_fails_without_any_tango_access(approval_setup):
    setup, command, intent, consumed, approve, submit = approval_setup
    approve(targets=[{'device': 'other/device', 'command': 'ExecuteCommand'}])
    assert submit().status_code == 409
    assert setup[4] == []
    now = datetime.now(timezone.utc)
    approve(issued_at=(now - timedelta(minutes=3)).isoformat(), expires_at=(now - timedelta(seconds=1)).isoformat())
    assert submit().status_code == 409
    assert setup[4] == []
    assert not list(consumed.iterdir())


@pytest.mark.parametrize('approval_setup', ['sync'], indirect=True)
@pytest.mark.parametrize('field,value', [('counter', 1), ('delay_us', 2.), ('width_us', 4.)])
def test_sync_approval_binds_each_nested_parameter_before_any_journal_or_tango(approval_setup, field, value):
    setup, command, intent, consumed, approve, submit = approval_setup
    approve(args=dict(intent.args, value=dict(command['value'], **{field: value})))
    response = submit()
    assert response.status_code == 409, response.json
    assert response.json['receipt']['dispatch_attempted'] is False
    assert setup[4] == [] and not list(consumed.iterdir())
    assert not Path(setup[0].config['ELYSE_CONTROL_STATE_DB']).exists()


@pytest.mark.parametrize('approval_setup', ['sync'], indirect=True)
def test_sync_exact_pair_consumes_one_external_approval_and_cannot_replay(approval_setup):
    setup, command, intent, consumed, approve, submit = approval_setup
    approve()
    response = submit()
    assert response.status_code == 200, response.json
    assert writes(setup) == [('command', 'ExecuteCommand', command)]
    assert len(list(consumed.iterdir())) == 1
    calls = list(setup[4])
    assert submit(dict(command, command_id='c' * 32)).status_code == 409
    assert setup[4] == calls
