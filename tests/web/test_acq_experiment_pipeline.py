"""Operator intents across Flask/Tango/HTTP/one owner; all equipment is fake.

Only private loopback sockets and temporary journals are used. The fixture's
software EPS and command images do not qualify physical feedback or permits.
"""
import json
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from tests.web.test_acq_control_api import api, ROOT, setup_api
from tests.unit.test_acq_control_release import normal_sample
from DeviceServers.control.elyse_acq.control_client import ControlClient, ControlBridge
from DeviceServers.control.elyse_acq.control_runtime_health import INPUT_BANKS
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, control_identity
from legacy.xp_acq_control.elyse_agent.acquisition_remote import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    # Explicit fake manual approval; real approval consumption is tested apart.
    monkeypatch.setattr(api, 'authorize_runtime_operation', lambda *args, **kwargs: True)
    effects, created = [], []

    class FakeCards:
        resource_count = 0
        control_profile = 'extended_ht_stop'
        ht_feedback_verified = stage_controls_verified = ht_controls_verified = True
        focal_controls_verified = counter_controls_verified = ht_voltage_controls_verified = True
        beamline_controls_verified = True
        counter_timing_controls_verified = True
        focal_command = SimpleNamespace(resources_verified=True)
        procedure = None

        def __init__(self):
            self.eps, self.dps = [False] * 77, [False] * 29
            self.command_kv, self.revision, self.fail_operation = 6.6, 1, None
            self.started_counters = [0, 1, 2, 5, 6, 7]
            self.commanded_counter_ticks = {}
            created.append(self)

        @property
        def ht_sequence_state(self):
            return dict(current_command_kv=self.command_kv, command_known=True,
                        supply_sequence_completed=self.eps[45], pulses_sequence_completed=self.eps[52])

        def effect(self, name, value=None):
            effects.append((name, value, threading.get_ident()))
            if name == self.fail_operation:
                raise IOError('Injected source pulse outcome unknown; never replay')

        def get_software_state(self):
            return dict(revision=self.revision, EPS=tuple(self.eps), DPS=tuple(self.dps))

        def initialize(self, cancel, startup_confirmed=False):
            assert startup_confirmed
            self.resource_count = 1
            self.effect('initialize-fake-cards')

        def general_start(self, cancel, operator_confirmed=False):
            assert operator_confirmed
            self.effect('general')
            self.eps[8] = True
            self.revision += 1

        def execute_stage(self, operation, cancel, operator_confirmed=False):
            assert operator_confirmed
            self.effect(operation)
            field = {'chauffage.start': 14, 'prema.start': 20, 'focales.start': 32,
                     'relays_ht.start': 26, 'alimentation_ht.start': 45,
                     'modulator_impulse.start': 52}.get(operation)
            if field is not None:
                self.eps[field] = True
            if operation == 'alimentation_ht.stop':
                self.eps[45] = False
            if operation == 'modulator_impulse.stop':
                self.eps[52] = False
            self.revision += 1

        def set_ht_voltage(self, value, cancel, operator_confirmed=False):
            assert operator_confirmed
            self.effect('ht_voltage.set', value)
            self.command_kv = value

        def configure_sync_parameters(self, value, cancel, operator_confirmed=False):
            assert operator_confirmed and value['counter'] in self.started_counters
            self.effect('counter_timing.set', dict(value))
            self.commanded_counter_ticks[value['counter']] = dict(initial_delay_ticks=25, low_ticks=25, high_ticks=70)

        def execute_impulsion(self, operation, cancel, operator_confirmed=False):
            return self.execute_stage(operation, cancel, operator_confirmed)

        def general_stop(self, operator_confirmed=False):
            assert operator_confirmed
            self.effect('general.stop')
            self.eps = [False] * 77
            self.revision += 1

        def read_snapshot(self, cancel):
            sample = normal_sample()
            for name, (kind, device, count) in INPUT_BANKS.items():
                bank = sample['banks'].setdefault(name, dict(values=[False if kind == 'digital_input' else 0.] * count))
                bank.update(kind=kind, device=device)
                if kind == 'analog_input':
                    bank['legacy_scaled_values'] = list(bank['values'])
            sample['commanded_analog_logical'] = {'C9NI6703': [self.command_kv] + [0.] * 9}
            sample['stage_state'] = dict(software_status_valid=True,
                local_banks={'EPS': list(self.eps), 'DPS': list(self.dps)})
            return sample

        def close(self):
            self.effect('close-fake-cards')
            self.resource_count = 0

    identity = control_identity()
    guard = OwnershipMarker(str(tmp_path / 'fake.ownership'), identity['session_id'], identity['build_id'])
    runtime = AcquisitionControlRuntime(FakeCards, remote_enabled=True, cooling_polarity_verified=True,
        identity=identity, recovery_guard=guard, period=.02)
    # Routing/serialization test: virtual lease clock avoids wall-time load
    # flakiness. Separate tests exercise real/deterministic lease expiry.
    lease_clock = [1000.]
    runtime.broker.clock = lambda: lease_clock[0]
    issue_lease = runtime.broker.issue_lease_nonblocking
    def route_fixture_lease(**kwargs):
        # This fixture verifies routing, not the intentional no-lease result
        # when a concurrent owner holds the lock. Pin that scheduling point;
        # expiry, lifecycle, identity and capacity checks still run unchanged.
        # Production non-waiting admission is covered by its dedicated suites.
        with runtime._lock:
            return issue_lease(**kwargs)
    monkeypatch.setattr(runtime.broker, 'issue_lease_nonblocking', route_fixture_lease)
    server = ControlHTTPServer(('127.0.0.1', 0), runtime, b'r' * 32, b'w' * 32)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02), daemon=True)
    bridge = ControlBridge(ControlClient(b'r' * 32, b'w' * 32, enabled=True,
        host='127.0.0.1', port=server.server_port))

    class FakeTango:
        def set_timeout_millis(self, value):
            pass
        def read_attribute(self, name):
            bridge.poll_once()
            value = bridge.snapshot()
            # This transport fixture has no real dual-mode publisher.
            value['runtime']['telemetry_delivery'] = dict(source_mode='PYTHON_NATIVE')
            return SimpleNamespace(has_failed=False, value=json.dumps(value))
        def command_inout(self, name, encoded):
            assert name == 'ExecuteCommand'
            return json.dumps(bridge.client.submit(json.loads(encoded)))

    def proxy(device):
        assert device == api.DEVICE
        return FakeTango()
    monkeypatch.setattr(api.tango_gateway, 'create_device_proxy', proxy)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY='test-only-experiment-pipeline-secret-000000000',
        ELYSE_CONTROL_STATE_DB=str(tmp_path / 'commands.sqlite3'), ELYSE_ACQUISITION_SOURCE='xp_control')
    JWTManager(app)
    app.register_blueprint(api.api)
    with app.app_context():
        token = create_access_token(identity='fake-experiment-operator')
    client = app.test_client()
    headers = {'Authorization': 'Bearer ' + token}

    def until(predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        snapshot = runtime.snapshot()
        raise AssertionError('Fake owner did not reach expected state: ' + str({
            key: snapshot.get(key) for key in ('state', 'error', 'current_operation', 'ht_sequence_state')}))

    def ready():
        until(lambda: runtime.snapshot()['state'] == 'RUNNING' and not runtime.snapshot()['stale'])

    def submit(operation, value=None, command_id=None):
        # Advance between fake operator decisions so unused observation leases
        # expire rather than filling the bounded pool under a frozen clock.
        lease_clock[0] += 3.
        view = client.get(ROOT).json
        assert view['source_selected'], view
        return client.post(ROOT + '/commands', headers=headers, json=dict(command_id=command_id or uuid4().hex,
            session_id=view['session_id'], expected_revision=view['revision'],
            operation=operation, operator_confirmed=True, value=value))

    runtime.start()
    thread.start()
    try:
        assert not effects
        runtime.initialize(startup_confirmed=True)
        ready()
        result = submit('modulator.general.start')
        assert result.json['receipt']['outcome'] == 'QUEUED', result.json
        until(lambda: runtime.snapshot()['general_cooling_ready'] and runtime.snapshot()['state'] == 'RUNNING')
        ready()
        yield SimpleNamespace(runtime=runtime, cards=created[0], effects=effects,
            client=client, headers=headers, submit=submit, ready=ready, until=until)
    finally:
        runtime.request_shutdown(electrical_off_confirmed=True)
        runtime.join(3)
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_full_mock_operator_sequence_scalar_ht_and_named_faraday_mirror(experiment):
    run = experiment
    blocked = run.submit('ht_voltage.set', 6.7)
    assert blocked.status_code == 200, blocked.json
    assert blocked.json['receipt']['outcome'] == 'REJECTED'
    assert 'HT_INCREASE_REQUIRES_CURRENT_OWNER_SUPPLY_AND_PULSE_SEQUENCES' in blocked.json['receipt']['error']
    assert not any(name == 'ht_voltage.set' for name, value, owner in run.effects)
    lowered = run.submit('ht_voltage.set', 6.5)
    assert lowered.json['receipt']['outcome'] == 'QUEUED', lowered.json
    run.ready()
    for operation in ('chauffage.start', 'prema.start', 'focales.start', 'relays_ht.start',
                      'alimentation_ht.start', 'modulator_impulse.start'):
        response = run.submit(operation)
        assert response.json['receipt']['outcome'] == 'QUEUED', response.json
        run.ready()
    for value in (6.6, 6.7):
        response = run.submit('ht_voltage.set', value)
        assert response.json['receipt']['outcome'] == 'QUEUED', response.json
        run.ready()
    for operation in ('faraday_1.en_pulse', 'faraday_3.en_pulse',
                      'laser_mirror.en_pulse', 'laser_mirror.hors_pulse'):
        response = run.submit(operation)
        assert response.json['receipt']['outcome'] == 'QUEUED', response.json
        run.ready()
        assert response.json['receipt']['hardware_acknowledged'] is False
    assert [value for name, value, owner in run.effects if name == 'ht_voltage.set'] == [6.5, 6.6, 6.7]
    assert len({owner for name, value, owner in run.effects}) == 1
    assert run.cards.command_kv == 6.7
    assert run.cards.dps == [False] * 29  # C5 requests are not DPS requests.
    stopped = run.submit('modulator.general.stop')
    assert stopped.json['receipt']['outcome'] == 'QUEUED', stopped.json
    run.ready()


def test_failed_motion_is_not_replayed_and_does_not_run_next_experiment_step(experiment):
    run = experiment
    run.cards.fail_operation = 'faraday_3.en_pulse'
    command_id = uuid4().hex
    reply = run.submit('faraday_3.en_pulse', command_id=command_id)
    assert reply.json['receipt']['outcome'] == 'QUEUED', reply.json
    run.until(lambda: run.runtime.snapshot()['state'] == 'FAULT')
    assert sum(name == 'faraday_3.en_pulse' for name, value, owner in run.effects) == 1
    denied = run.submit('laser_mirror.en_pulse')
    assert denied.status_code == 409
    assert not any(name == 'laser_mirror.en_pulse' for name, value, owner in run.effects)
    assert not any(name == 'ht_voltage.set' for name, value, owner in run.effects)


def test_sync_pair_crosses_same_facade_device_signed_channel_and_owner_once(experiment):
    run = experiment
    before = run.client.get(ROOT).json
    assert before['synchronization']['running_counters'] == [0, 1, 2, 5, 6, 7]
    command_id = uuid4().hex
    value = dict(counter=2, delay_us=1.25, width_us=3.5)
    reply = run.submit('counter_timing.set', value, command_id)
    assert reply.status_code == 200 and reply.json['receipt']['outcome'] == 'QUEUED', reply.json
    run.ready()
    current = run.client.get(ROOT).json
    assert current['synchronization']['commanded_ticks']['2']['high_ticks'] == 70
    matching = [item for item in current['commands'] if item['command_id'] == command_id]
    assert matching[0]['outcome'] == 'COMPLETED'
    original = run.runtime.broker.records[command_id]['request']
    duplicate = run.client.post(ROOT + '/commands', headers=run.headers, json=original)
    assert duplicate.status_code == 200 and duplicate.json['duplicate'] is True
    applied = [(name, argument, owner) for name, argument, owner in run.effects if name == 'counter_timing.set']
    assert len(applied) == 1 and applied[0][1] == value
    assert len({owner for name, argument, owner in run.effects}) == 1
    stopped = run.submit('counter_timing.set', dict(value, counter=3))
    assert stopped.json['receipt']['outcome'] == 'REJECTED'
    assert 'ALREADY_RUNNING_COUNTER' in stopped.json['receipt']['error']


@pytest.mark.parametrize('operation', ['faraday_1.hors_pulse', 'faraday_3.hors_pulse', 'faraday.open', 'raw.write'])
def test_unproven_faraday_hors_or_ambiguous_open_never_reaches_tango(setup_api, operation):
    from tests.web.test_acq_control_api import post, request_command, writes
    assert post(setup_api, request_command(operation=operation)).status_code == 400
    assert writes(setup_api) == []
