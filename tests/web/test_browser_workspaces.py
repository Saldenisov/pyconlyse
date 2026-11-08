import sys
from pathlib import Path

from flask import Flask
import pytest
from tests._tango_stub import install_tango_stub


class Patch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(Patch())
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from browser_workspace_state import BrowserWorkspaceStates, WorkspaceConflict
import pump_probe_vd2_api as vd2
import treatment_api as treatment
from treatment_state_repository import TreatmentStateRepository

BROWSER = 'browser-one-123456'
WINDOW = 'window-one-123456'
SETTINGS = dict(outputRoot=r'E:\DATA_VD2\2026\project', runName='water', framesPerHis='20', sampleDescription='sample notes', reuseBruit='latest')


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('PYCONLYSE_WORKSPACE_STATE_DB', str(tmp_path / 'workspaces.sqlite3'))
    monkeypatch.setenv('PYCONLYSE_TREATMENT_ROOT', str(tmp_path))
    monkeypatch.setenv('PYCONLYSE_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setattr(vd2, '_proxy', lambda: pytest.fail('No hardware access for UI snapshots'))
    monkeypatch.setattr(vd2, 'DeviceProxy', lambda *_: pytest.fail('No hardware access for UI snapshots'))
    monkeypatch.setattr(treatment, 'session_store', treatment.TreatmentSessionStore(TreatmentStateRepository(tmp_path / 'treatment.sqlite3')))
    monkeypatch.setattr(treatment, 'treatment_queue_store', treatment.TreatmentQueueStore())
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    app.register_blueprint(treatment.treatment_api)
    return app.test_client()


def headers(window=WINDOW, browser=BROWSER, session=None):
    result = {'X-Workspace-Browser': browser, 'X-Workspace-Window': window}
    if session:
        result['X-Treatment-Session-Id'] = session
    return result


def test_measurement_settings_survive_repository_restart_and_isolate_browsers_and_windows(tmp_path):
    path = tmp_path / 'workspaces.sqlite3'
    first = BrowserWorkspaceStates(path)
    first.save(BROWSER, WINDOW, SETTINGS, 0)
    first.save(BROWSER, 'window-two-123456', {**SETTINGS, 'runName': 'second'}, 0)
    fresh = BrowserWorkspaceStates(path)
    assert fresh.get(BROWSER, WINDOW)['settings'] == SETTINGS
    assert fresh.get(BROWSER, 'window-two-123456')['settings']['runName'] == 'second'
    assert fresh.history('another-browser-123456') == []
    assert len(fresh.history(BROWSER)) == 2


def test_stale_writes_cannot_overwrite_the_saved_window(tmp_path):
    repo = BrowserWorkspaceStates(tmp_path / 'state.sqlite3')
    repo.save(BROWSER, WINDOW, SETTINGS, 0)
    with pytest.raises(WorkspaceConflict):
        BrowserWorkspaceStates(repo.path).save(BROWSER, WINDOW, {**SETTINGS, 'runName': 'stale'}, 0)
    assert repo.get(BROWSER, WINDOW)['settings']['runName'] == 'water'


def test_http_snapshot_restore_is_software_only_and_rejects_hardware_fields(client):
    url = '/api/pump-probe-vd2/workspace'
    assert client.get(url, headers=headers()).json['workspace'] is None
    result = client.post(url, headers=headers(), json={'settings': SETTINGS, 'revision': 0})
    assert result.status_code == 200 and result.json['workspace']['revision'] == 1
    assert client.get(url, headers=headers()).json['workspace']['settings'] == SETTINGS
    assert client.get(url, headers=headers(window='another-window-1234')).json['workspace'] is None
    assert client.post(url, headers=headers(), json={'settings': SETTINGS, 'revision': 0}).status_code == 409
    unsafe = client.post(url, headers=headers(), json={'settings': {**SETTINGS, 'streak_shutter': 'Open'}, 'revision': 1})
    assert unsafe.status_code == 400
    assert client.get(url).status_code == 400
    assert len(client.get(url + '/history', headers=headers()).json['workspaces']) == 1
    assert client.get(url + '/history', headers=headers(browser='another-browser-1234')).json['workspaces'] == []


def test_workspace_mutation_keeps_existing_authentication_guard(client, monkeypatch):
    import mutation_auth
    from flask_jwt_extended.exceptions import JWTExtendedException
    monkeypatch.setattr(mutation_auth, 'mutation_auth_required', lambda: True)
    def deny():
        raise JWTExtendedException('not authenticated')
    monkeypatch.setattr(mutation_auth, 'verify_jwt_in_request', deny)
    assert client.post('/api/pump-probe-vd2/workspace', headers=headers(), json={'settings': SETTINGS, 'revision': 0}).status_code == 401


def test_folder_picker_lists_one_level_and_cannot_escape_data_root(client, tmp_path):
    project = tmp_path / 'project'; project.mkdir()
    (project / 'sample').mkdir()
    (project / 'ABS.h5').write_bytes(b'untouched')
    (project / 'sample' / 'do-not-scan').mkdir()
    result = client.get('/api/pump-probe-vd2/protocol/folders', query_string={'folder': str(project)})
    assert result.status_code == 200
    assert result.json['folders'] == [dict(name='sample', path=str(project / 'sample'))]
    assert result.json['parent'] == str(tmp_path)
    assert client.get('/api/pump-probe-vd2/protocol/folders').json['parent'] is None
    assert client.get('/api/pump-probe-vd2/protocol/folders', query_string={'folder': str(tmp_path.parent)}).status_code == 400
    assert client.get('/api/pump-probe-vd2/protocol/folders', query_string={'folder': str(tmp_path / 'missing')}).status_code == 404
    assert (project / 'ABS.h5').read_bytes() == b'untouched'


def seed_treatment(tmp_path):
    source = f'browser:{BROWSER}:profile:vd2'
    treatment.session_store.set_folder(source, str(tmp_path))
    treatment.session_store.update_config(source, {'save_file_name': 'water.dat', 'calc_mode': 'individual'})
    treatment.session_store.update_selection(source, {'map_index': 3, 'selection': {'x1': 4, 'x2': 8}})
    return source


def test_treatment_restore_clones_legacy_browser_work_without_queue_replay(client, tmp_path):
    source = seed_treatment(tmp_path)
    target = f'browser:{BROWSER}:window:{WINDOW}:profile:vd2:workspace:restored-one'
    other = f'browser:another-browser-1234:profile:vd2'
    treatment.session_store.update_config(other, {'save_file_name': 'private.dat'})
    result = client.get('/api/treatment/session/saved', headers=headers(session=target))
    assert [item['session_id'] for item in result.json['sessions']] == [source]
    treatment.treatment_queue_store.enqueue(source, {'output': {}})
    copied = client.post('/api/treatment/session/copy', headers=headers(session=target), json={'source_session_id': source})
    assert copied.status_code == 200 and copied.json['restored']
    state = treatment.session_store.snapshot(target)
    assert (state['save_file_name'], state['calc_mode'], state['map_index'], state['selection']) == ('water.dat', 'individual', 3, {'x1': 4, 'x2': 8})
    assert treatment.treatment_queue_store.snapshot(target)['jobs'] == []
    treatment.session_store.update_config(target, {'save_file_name': 'independent.dat'})
    assert treatment.session_store.snapshot(source)['save_file_name'] == 'water.dat'
    assert client.post('/api/treatment/session/copy', headers=headers(session=target), json={'source_session_id': source}).status_code == 409


def test_treatment_restore_rejects_other_browser_profile_and_changed_path_boundary(client, tmp_path, monkeypatch):
    source = seed_treatment(tmp_path)
    target = f'browser:{BROWSER}:window:{WINDOW}:profile:vd2:workspace:restored-one'
    for foreign in [f'browser:another-browser-1234:profile:vd2', f'browser:{BROWSER}:profile:v0']:
        assert client.post('/api/treatment/session/copy', headers=headers(session=target), json={'source_session_id': foreign}).status_code == 400
    narrower = tmp_path / 'new-root'; narrower.mkdir()
    monkeypatch.setenv('PYCONLYSE_TREATMENT_ROOT', str(narrower))
    assert client.post('/api/treatment/session/copy', headers=headers(session=target), json={'source_session_id': source}).status_code == 400


def test_treatment_saved_session_list_survives_store_restart(client, tmp_path):
    source = seed_treatment(tmp_path)
    repo = TreatmentStateRepository(tmp_path / 'treatment.sqlite3')
    store = treatment.TreatmentSessionStore(repo)
    saved = store.saved_sessions(BROWSER, 'vd2')
    assert saved[0]['session_id'] == source and saved[0]['updated_at']


def test_restore_does_not_change_an_existing_queue_workspace(client, tmp_path):
    source = seed_treatment(tmp_path)
    target = f'browser:{BROWSER}:window:{WINDOW}:profile:vd2:workspace:already-queued'
    treatment.treatment_queue_store.enqueue(target, {'output': {}})
    result = client.post('/api/treatment/session/copy', headers=headers(session=target), json={'source_session_id': source})
    assert result.status_code == 409
    assert treatment.session_store.snapshot(target)['save_file_name'] == ''


def test_manifest_picker_lists_json_names_and_accepts_quoted_folder_without_reading_files(client, tmp_path):
    (tmp_path / 'vd2-manifest.json').write_text('read only when selected')
    (tmp_path / 'untouched.h5').write_bytes(b'untouched')
    response = client.get('/api/pump-probe-vd2/protocol/folders', query_string={'kind':'manifest','folder':f'"{tmp_path}"'})
    assert response.status_code == 200
    assert response.json['files'] == [{'name':'vd2-manifest.json','path':str(tmp_path / 'vd2-manifest.json')}]
    assert (tmp_path / 'untouched.h5').read_bytes() == b'untouched'
