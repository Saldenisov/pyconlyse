"""Synthetic telemetry only: no HDF5, Tango, XP, NI or equipment access."""
from pathlib import Path
from types import SimpleNamespace
from threading import Event

import pytest
from flask import Flask
from tests.web.test_pump_probe_v0_api import BACKEND  # noqa: F401 - backend import path
from supervision_workspace_api import WorkspaceStore, workspace_api, RETENTION_MS


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    clock = [1800000000.0]
    store = WorkspaceStore(tmp_path / 'display.sqlite3', clock=lambda: clock[0])
    app = Flask(__name__)
    app.testing = True
    app.extensions['supervision_workspace_store'] = store
    app.register_blueprint(workspace_api)
    return SimpleNamespace(store=store, clock=clock, client=app.test_client(), app=app)


def sample(receipt=1, session='one'):
    banks = {}
    for name in ('C1NI6071E', 'VAM-A'):
        banks[name] = dict(data=[0.0] * 64, stale=False, age_seconds=0.1,
                           error=dict(status=False, code=0),
                           lv_type=dict(type='Cluster', name=name, fields=[dict(type='DBL')] * 64))
    banks['C1NI6071E']['data'][0] = 20.5
    banks['C1NI6071E']['data'][8] = 21.3
    banks['VAM-A']['data'][10] = 1e-8
    return dict(server_state='ON', snapshot=dict(receiver_session=session, received_this_process=receipt, publications=banks))


def test_restores_curve_from_sqlite_after_store_restart(workspace):
    workspace.store.ingest(sample())
    restored = WorkspaceStore(workspace.store.path, clock=lambda: workspace.clock[0]).query(30)
    assert len(restored['samples']) == 1
    assert restored['samples'][0]['canon'] == 20.5
    assert restored['samples'][0]['section'] == 21.3
    assert restored['samples'][0]['vide:14'] == 1e-8
    assert restored['canonical_archive_read'] is False
    assert restored['archive_complete'] is False
    assert restored['requested_native_source'] == 'Supervision VI'
    assert restored['native_history_available'] is False


def test_same_receipt_deduplicates_and_new_session_is_retained(workspace):
    workspace.store.ingest(sample())
    workspace.store.ingest(sample())
    workspace.clock[0] += 1
    workspace.store.ingest(sample(session='two'))
    assert [s['session'] for s in workspace.store.query(30)['samples']] == ['one', 'two']


@pytest.mark.parametrize('problem', ['stale', 'error', 'schema', 'nonfinite', 'server_off'])
def test_unavailable_values_are_not_saved_as_false_zeros(workspace, problem):
    value = sample()
    bank = value['snapshot']['publications']['C1NI6071E']
    if problem == 'stale': bank['stale'] = True
    if problem == 'error': bank['error']['code'] = 4
    if problem == 'schema': bank['lv_type']['name'] = 'wrong'
    if problem == 'nonfinite': bank['data'][0] = float('nan')
    if problem == 'server_off': value['server_state'] = 'OFF'
    workspace.store.ingest(value)
    assert workspace.store.query(30)['samples'][0]['canon'] is None


def test_read_errors_insert_explicit_gaps_and_cache_retention_is_bounded(workspace):
    workspace.store.ingest(sample())
    workspace.clock[0] += 1
    workspace.store.gap('receiver unavailable')
    assert workspace.store.query(30)['samples'][-1]['session'] == 'gap'
    assert workspace.store.query(30)['samples'][-1]['canon'] is None
    workspace.clock[0] += RETENTION_MS / 1000 + 1
    workspace.store.ingest(sample(2))
    assert len(workspace.store.query(120)['samples']) == 1


@pytest.mark.parametrize('minutes', ['0', '1440', '-1', 'NaN', '30.5', '../data'])
def test_history_query_has_fixed_window_and_no_file_path_input(workspace, minutes):
    assert workspace.client.get('/api/elyse/supervision/workspace/history', query_string={'minutes': minutes}).status_code == 400


def test_never_opens_an_hdf5_file(workspace, monkeypatch):
    original = Path.open
    def checked(path, *args, **kwargs):
        assert path.suffix.lower() not in ('.h5', '.hdf5')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', checked)
    workspace.store.ingest(sample())
    assert workspace.client.get('/api/elyse/supervision/workspace/history?minutes=30').json['storage'] == 'server_sqlite'


def test_draft_persists_but_is_never_applied_and_revision_is_atomic(workspace):
    path = '/api/elyse/supervision/workspace/synchronization'
    values = [float(i) for i in range(33)]
    result = workspace.client.post(path, json=dict(expected_revision=0, values=values))
    assert result.status_code == 200
    assert result.json['hardware_applied'] is False and result.json['draft_only'] is True
    assert result.json['revision'] == 1
    assert WorkspaceStore(workspace.store.path).synchronization()['values'] == values
    assert workspace.client.post(path, json=dict(expected_revision=0, values=values)).status_code == 409


@pytest.mark.parametrize('values', [[1.0] * 32, [1.0] * 34, [True] * 33, ['1'] * 33, [None] * 33])
def test_draft_validation_rejects_missing_or_implicit_values(workspace, values):
    response = workspace.client.post('/api/elyse/supervision/workspace/synchronization', json=dict(values=values, expected_revision=0))
    assert response.status_code == 400
    assert workspace.store.synchronization()['revision'] == 0


def test_draft_rejects_nonfinite_duplicate_keys_and_oversized_body(workspace):
    path = '/api/elyse/supervision/workspace/synchronization'
    assert workspace.client.post(path, data='{"expected_revision":0,"values":[NaN]}', content_type='application/json').status_code == 400
    assert workspace.client.post(path, data='{"expected_revision":0,"expected_revision":1,"values":[]}', content_type='application/json').status_code == 400
    assert workspace.client.post(path, data=' ' * 9000, content_type='application/json').status_code == 413
    assert workspace.client.post(path, json=dict(expected_revision=2**63, values=[1] * 33)).status_code == 400
    assert workspace.client.post(path, json=dict(expected_revision=0, values=[10**500] * 33)).status_code == 413
    assert workspace.client.post(path, json=dict(expected_revision=0, values=[10**500] + [1] * 32)).status_code == 400


def test_observer_singleton_collects_without_any_browser_request(workspace):
    read = Event()
    def reader():
        read.set()
        return sample()
    workspace.store.start(reader)
    thread = workspace.store.thread
    try:
        workspace.store.start(reader)
        assert workspace.store.thread is thread
        assert read.wait(3)
    finally:
        workspace.store.stop_event.set()
        thread.join(3)
    assert not thread.is_alive()
    assert workspace.store.query(30)['samples'][0]['canon'] == 20.5


def test_old_fresh_point_survives_a_later_stale_copy_with_same_receipt(workspace):
    workspace.store.ingest(sample())
    workspace.clock[0] += 1
    stale = sample()
    for bank in stale['snapshot']['publications'].values():
        bank['stale'] = True
    workspace.store.ingest(stale)
    rows = workspace.store.query(30)['samples']
    assert rows[0]['canon'] == 20.5
    assert rows[1]['session'] == 'gap' and rows[1]['canon'] is None


def test_production_rejects_unauthenticated_requests_before_storage(workspace, monkeypatch):
    from flask_jwt_extended import JWTManager
    JWTManager(workspace.app)
    workspace.app.config['JWT_SECRET_KEY'] = 'unit-test-only'
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'true')
    def unexpected():
        pytest.fail('Unauthorized request touched workspace storage')
    monkeypatch.setattr('supervision_workspace_api.store', unexpected)
    root = '/api/elyse/supervision/workspace'
    assert workspace.client.get(root + '/history').status_code == 401
    assert workspace.client.get(root + '/synchronization').status_code == 401
    assert workspace.client.post(root + '/synchronization', json={}).status_code == 401
