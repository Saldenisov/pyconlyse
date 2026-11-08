"""Synthetic matrices and temporary session memory; no acquisition or files."""
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path
import sys
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from zipfile import ZipFile

import numpy as np
import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

BACKEND = Path(__file__).resolve().parents[2] / 'web/backend'
sys.path.insert(0, str(BACKEND))
ROOT = '/api/treatment/skana'
HEADERS = {'X-Treatment-Session-Id': 'skana-test-one'}
TEXT = '0,400,500,600\n0,1,2,3\n1,2,4,6\n2,3,6,9\n3,4,8,12\n'


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    monkeypatch.setenv('PYCONLYSE_TREATMENT_ROOT', str(tmp_path))
    treatment = import_module('treatment_api')
    api = import_module('skana_api')
    from treatment_service import TreatmentDataService
    service = TreatmentDataService()
    monkeypatch.setattr(treatment, 'treatment_service', service)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY='skana-synthetic-only')
    JWTManager(app)
    app.register_blueprint(api.skana_api)
    value = SimpleNamespace(client=app.test_client(), app=app, service=service, api=api)
    yield value
    workspace = app.extensions.get('skana_workspace')
    if workspace and workspace.executor:
        for job in workspace.jobs.values():
            job.cancel.set()
        workspace.executor.shutdown(wait=True, cancel_futures=True)


def imported(setup, headers=HEADERS):
    response = setup.client.post(ROOT + '/import', headers=headers, json={
        'text': TEXT, 'filename': 'synthetic.csv', 'orientation': 'time_rows', 'time_unit': 'ns'})
    assert response.status_code == 200, response.json
    return response.json['dataset']


def start(setup, dataset, method='svd', options=None, source='import', headers=HEADERS):
    response = setup.client.post(ROOT + '/jobs', headers=headers, json=dict(
        source=source, fingerprint=dataset['fingerprint'], method=method, options=options or {'rank': 1}))
    assert response.status_code == 202, response.json
    return response.json['job']['id']


def finished(setup, job_id, headers=HEADERS):
    deadline = monotonic() + 10
    while monotonic() < deadline:
        response = setup.client.get(ROOT + '/jobs/' + job_id, headers=headers)
        assert response.status_code == 200, response.json
        if response.json['job']['status'] not in ('queued', 'running'):
            return response.json
        sleep(0.01)
    pytest.fail('Synthetic analysis did not finish')


def test_no_od_does_not_read_or_restore_any_source_file(setup, monkeypatch):
    def forbidden(*args):
        pytest.fail('SK-Ana reopened an experimental input file')
    monkeypatch.setattr(setup.service, '_get_opener', forbidden)
    response = setup.client.get(ROOT + '/dataset', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['dataset']['ready'] is False


def test_import_and_svd_run_original_python_engine_without_source_mutation(setup):
    data = imported(setup)
    assert data['shape'] == [4, 3] and data['time_unit'] == 'ns'
    assert data['warnings']
    job_id = start(setup, data)
    completed = finished(setup, job_id)
    assert completed['job']['status'] == 'completed', completed
    result = completed['result']
    assert result['lof_percent'] < 1e-10
    assert result['fingerprint'] == data['fingerprint']
    assert 'reconstruction' not in result  # Full result is export-only.
    assert result['model_preview']['downsampled'] is False
    assert setup.client.get(ROOT + '/dataset?source=import', headers=HEADERS).json['dataset']['fingerprint'] == data['fingerprint']


def test_native_orientation_and_full_result_export(setup):
    data = imported(setup)
    job_id = start(setup, data)
    finished(setup, job_id)
    response = setup.client.get(ROOT + f'/jobs/{job_id}/export?format=json', headers=HEADERS)
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert np.shape(payload['reconstruction']) == (4, 3)
    np.testing.assert_allclose(payload['reconstruction'], [[1, 2, 3], [2, 4, 6], [3, 6, 9], [4, 8, 12]], atol=1e-10)
    archive = setup.client.get(ROOT + f'/jobs/{job_id}/export?format=csv', headers=HEADERS)
    assert archive.status_code == 200
    with ZipFile(BytesIO(archive.data)) as zipped:
        assert set(zipped.namelist()) == {'data.csv', 'model.csv', 'residuals.csv', 'spectra.csv', 'kinetics.csv', 'metadata.json'}
        assert json.loads(zipped.read('metadata.json'))['time_unit'] == 'ns'


def test_full_resolution_od_snapshot_never_uses_preview_or_file_path(setup, monkeypatch):
    wavelengths, delays = np.arange(135.0) + 400, np.arange(130.0)
    array = np.outer(np.arange(1., 136.), np.arange(1., 131.))
    info = SimpleNamespace(wavelengths=wavelengths, timedelays=delays, scaling_yunit='ps')
    runtime = setup.service._empty_runtime()
    runtime.update(result=array, result_info=info, result_source_path=Path('must-not-open.h5'))
    setup.service._runtimes[HEADERS['X-Treatment-Session-Id']] = runtime
    metadata = setup.client.get(ROOT + '/dataset?source=od', headers=HEADERS).json['dataset']
    assert metadata['shape'] == [130, 135]
    assert np.shape(metadata['preview']['z']) == (128, 128)
    assert metadata['preview']['downsampled'] is True
    job_id = start(setup, metadata, source='od')
    result = finished(setup, job_id)
    assert result['job']['status'] == 'completed', result
    assert len(result['result']['times']) == 130
    np.testing.assert_array_equal(array, runtime['result'])


def test_import_and_result_are_session_isolated(setup):
    metadata = imported(setup)
    job_id = start(setup, metadata)
    other = {'X-Treatment-Session-Id': 'skana-test-other'}
    assert setup.client.get(ROOT + '/dataset?source=import', headers=other).json['dataset']['ready'] is False
    assert setup.client.get(ROOT + f'/jobs/{job_id}', headers=other).status_code == 404
    assert setup.client.post(ROOT + f'/jobs/{job_id}/cancel', headers=other).status_code == 404
    assert setup.client.get(ROOT + f'/jobs/{job_id}/export', headers=other).status_code == 404


def test_old_fingerprint_cannot_fit_replaced_import(setup):
    data = imported(setup)
    setup.client.post(ROOT + '/import', headers=HEADERS, json=dict(text=TEXT.replace('12', '13'), time_unit='ns'))
    response = setup.client.post(ROOT + '/jobs', headers=HEADERS, json=dict(
        source='import', method='svd', options={'rank': 1}, fingerprint=data['fingerprint']))
    assert response.status_code == 409


def test_reopening_tab_restores_latest_job_only_for_same_matrix_and_session(setup):
    data = imported(setup)
    job_id = start(setup, data)
    finished(setup, job_id)
    response = setup.client.get(ROOT + '/dataset?source=import', headers=HEADERS)
    assert response.json['dataset']['latest_job']['id'] == job_id
    assert response.json['dataset']['latest_job']['status'] == 'completed'
    assert response.json['latest_job']['fingerprint'] == data['fingerprint']
    setup.client.post(ROOT + '/import', headers=HEADERS, json=dict(text=TEXT.replace('12', '13'), time_unit='ns'))
    assert setup.client.get(ROOT + '/dataset?source=import', headers=HEADERS).json['latest_job'] is None


def test_finished_fit_retention_starts_at_completion_not_submission(setup):
    data = imported(setup)
    job_id = start(setup, data)
    finished(setup, job_id)
    store = setup.app.extensions['skana_workspace']
    store.jobs[job_id].created -= setup.api.RETENTION + 1
    assert setup.client.get(ROOT + f'/jobs/{job_id}', headers=HEADERS).status_code == 200


def test_failed_numerical_job_remains_explicit_and_cannot_export(setup):
    data = imported(setup)
    job_id = start(setup, data, options={'rank': 999})
    payload = finished(setup, job_id)
    assert payload['job']['status'] == 'failed'
    assert payload['job']['error']
    assert 'result' not in payload
    assert setup.client.get(ROOT + f'/jobs/{job_id}/export', headers=HEADERS).status_code == 409


def test_selected_axes_match_masked_result_previews_and_exports(setup):
    data = imported(setup)
    job_id = start(setup, data, options={'rank': 1, 'delay_range': [1, 2], 'wavelength_range': [500, 600]})
    payload = finished(setup, job_id)
    assert payload['job']['status'] == 'completed', payload
    result = payload['result']
    assert result['times'] == [1, 2] and result['wavelengths'] == [500, 600]
    assert result['data_preview']['z'] == [[4, 6], [6, 9]]
    exported = setup.client.get(ROOT + f'/jobs/{job_id}/export?format=csv', headers=HEADERS)
    with ZipFile(BytesIO(exported.data)) as archive:
        matrix = np.loadtxt(BytesIO(archive.read('data.csv')), delimiter=',')
    np.testing.assert_array_equal(matrix, [[0, 500, 600], [1, 4, 6], [2, 6, 9]])


def test_existing_mcr_als_runs_and_preserves_limit_reached_status(setup):
    data = imported(setup)
    job_id = start(setup, data, method='mcr_als', options={'n_components': 1, 'maxiter': 1})
    result = finished(setup, job_id)
    assert result['job']['status'] == 'completed', result
    assert result['result']['iterations'] <= 1
    assert type(result['result']['converged']) is bool


def test_existing_fixed_parameter_kinetic_map_engine_is_available(setup):
    times = np.linspace(0, 3, 8)
    wavelengths = [400, 500, 600]
    c = np.column_stack((np.exp(-0.7 * times), 1 - np.exp(-0.7 * times)))
    spectra = np.array([[1., 0.2], [0.5, 0.5], [0.2, 1.]])
    table = np.vstack((np.r_[0, wavelengths], np.column_stack((times, c @ spectra.T))))
    text = '\n'.join(','.join(str(v) for v in row) for row in table)
    data = setup.client.post(ROOT + '/import', headers=HEADERS, json=dict(text=text, time_unit='ns')).json['dataset']
    scheme = 'A -> B ; 0.7\nc0_A_1 = 1\neps_A = 1\neps_B = 1'
    job_id = start(setup, data, method='target', options={'scheme': scheme})
    result = finished(setup, job_id)
    assert result['job']['status'] == 'completed', result
    assert result['result']['parameters']['k_1'] == 0.7
    assert result['result']['iterations'] is None


def test_cancel_keeps_running_native_fit_owned_until_it_returns(setup, monkeypatch):
    import utilities.skana as facade
    entered, release = Event(), Event()
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return {'never': 'published'}
    monkeypatch.setattr(facade, 'analyze', delayed)
    data = imported(setup)
    job_id = start(setup, data)
    try:
        assert entered.wait(2)
        response = setup.client.post(ROOT + f'/jobs/{job_id}/cancel', headers=HEADERS)
        assert response.json['job']['cancel_requested'] is True
        assert response.json['job']['status'] == 'running'
        retry = setup.client.post(ROOT + '/jobs', headers=HEADERS, json=dict(
            source='import', method='svd', options={'rank': 1}, fingerprint=data['fingerprint']))
        assert retry.status_code == 409
    finally:
        release.set()
    completed = finished(setup, job_id)
    assert completed['job']['status'] == 'cancelled' and 'result' not in completed


@pytest.mark.parametrize('body', [None, [], {'text': ''}, {'text': TEXT, 'orientation': 'guess'},
    {'text': TEXT, 'path': 'F:/active.h5'}])
def test_invalid_import_rejected(setup, body):
    response = setup.client.post(ROOT + '/import', headers=HEADERS,
                                 data=json.dumps(body), content_type='application/json')
    assert response.status_code == 400


def test_duplicate_keys_nonfinite_and_oversized_requests_rejected(setup):
    for raw in ('{"text":"a","text":"b"}', '{"text":NaN}', '[]'):
        assert setup.client.post(ROOT + '/import', headers=HEADERS, data=raw, content_type='application/json').status_code == 400
    assert setup.client.post(ROOT + '/import', headers=HEADERS, data=' ' * (setup.api.MAX_BODY + 1), content_type='application/json').status_code == 400


def test_production_auth_precedes_all_storage_access(setup, monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'true')
    def forbidden():
        pytest.fail('Unauthenticated request accessed SK-Ana storage')
    monkeypatch.setattr(setup.api, 'workspace', forbidden)
    assert setup.client.get(ROOT + '/dataset', headers=HEADERS).status_code == 401
    assert setup.client.post(ROOT + '/import', headers=HEADERS, json={}).status_code == 401
    assert setup.client.get(ROOT + '/jobs/one', headers=HEADERS).status_code == 401
    assert setup.client.get(ROOT + '/jobs/one/export', headers=HEADERS).status_code == 401
