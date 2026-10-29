"""Authenticated local centroid preferences, no device or camera network."""
import sys
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from supervision_diagnostics import DiagnosticsService
from supervision_diagnostics_api import create_diagnostics_api
from tests.web.test_supervision_diagnostics import CAMERA, MemoryStore, video

URL = '/api/elyse/supervision/diagnostics'


@pytest.fixture
def setup_api(monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    store = MemoryStore()
    service = DiagnosticsService(lambda name: video(), store, camera_ids=(CAMERA,))
    service.observe(CAMERA, video())
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY='diagnostics-test-only-secret')
    JWTManager(app)
    app.register_blueprint(create_diagnostics_api(service))
    return app.test_client(), service, store


def test_get_reference_and_mode_mutate_durable_preferences_only(setup_api):
    client, service, store = setup_api
    response = client.get(URL)
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    row = response.json['cameras'][0]
    reference = dict(camera_id=CAMERA, frame_identity=row['frame_identity'], expected_revision=0, radius_px=2)
    response = client.post(URL + '/reference', json=reference)
    assert response.status_code == 200
    assert response.json['cameras'][0]['reference']['revision'] == 1
    response = client.post(URL + '/mode', json=dict(camera_id=CAMERA, mode='auto', expected_revision=0))
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False and response.json['hardware_writes'] is False
    assert response.json['cameras'][0]['mode_revision'] == 1
    assert len(store.references) == 1 and len(store.modes) == 1


def test_invalid_request_and_revision_conflict_are_explicit(setup_api):
    client, service, store = setup_api
    assert client.get(URL + '?camera_id=wrong').status_code == 400
    assert client.post(URL + '/reference', json={'pixels': 'fake'}).status_code == 400
    assert client.post(URL + '/mode', data=b'{' + b'x' * 3000).status_code == 400
    assert client.post(URL + '/mode', json=dict(camera_id=CAMERA, mode='auto', expected_revision=4)).status_code == 409
    assert store.references == [] and store.modes == []


def test_database_failure_is_503_without_image_analysis_failure(setup_api):
    client, service, store = setup_api
    store.fail = True
    assert client.post(URL + '/mode', json=dict(camera_id=CAMERA, mode='auto', expected_revision=0)).status_code == 503
    assert client.get(URL).json['cameras'][0]['current']['valid'] is True


def test_authentication_protects_state_and_mutation_in_production(setup_api, monkeypatch):
    client, service, store = setup_api
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'true')
    assert client.get(URL).status_code == 401
    assert client.post(URL + '/mode', json=dict(camera_id=CAMERA, mode='auto', expected_revision=0)).status_code == 401
    assert store.references == [] and store.modes == []


def test_authenticated_audit_json_cache_does_not_consume_preference_body(setup_api, monkeypatch):
    from flask import request
    from flask_jwt_extended import create_access_token
    client, service, store = setup_api
    app = client.application
    @app.before_request
    def cached_audit_read():
        if request.method == 'POST':
            request.get_json(silent=True)
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'true')
    with app.app_context():
        token = create_access_token(identity='fixture-operator')
    response = client.post(URL + '/mode', json=dict(camera_id=CAMERA, mode='auto', expected_revision=0),
                           headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 200
    assert store.get_state(CAMERA)['mode'] == 'auto'
