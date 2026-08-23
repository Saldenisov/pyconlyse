import importlib
from pathlib import Path

import pytest
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token, get_csrf_token

BACKEND_DIR = Path(__file__).resolve().parents[2] / "web" / "backend"

MUTATION_ROUTES = (
    ("/api/device/test-device/command/Start", "device_api.execute_command"),
    ("/api/treatment/session/reset", "treatment_api.reset_session"),
    ("/api/pump-probe-vd2/command/Connect", "pump_probe_vd2_api.command"),
    ("/api/pump-probe-v0/reset", "pump_probe_v0_api.pump_probe_reset"),
)


@pytest.fixture
def guarded_app(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    modules = (
        importlib.import_module("device_api"),
        importlib.import_module("treatment_api"),
        importlib.import_module("pump_probe_vd2_api"),
        importlib.import_module("pump_probe_v0_api"),
    )
    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_CSRF_PROTECT=True,
    )
    JWTManager(app)
    for module in modules:
        app.register_blueprint(getattr(module, module.__name__))
    return app


def _recording_handler(calls):
    def handler(**_kwargs):
        calls.append(True)
        return jsonify({"handler_reached": True})

    return handler


def _authenticated_client(app):
    with app.app_context():
        token = create_access_token(identity="test-user")
        csrf_token = get_csrf_token(token)
    client = app.test_client()
    client.set_cookie("access_token_cookie", token)
    return client, csrf_token


@pytest.mark.parametrize(("path", "endpoint"), MUTATION_ROUTES)
def test_production_mutation_auth_blocks_handler_before_side_effects(
    guarded_app, monkeypatch, path, endpoint
):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    calls = []
    guarded_app.view_functions[endpoint] = _recording_handler(calls)

    response = guarded_app.test_client().post(path, json={})

    assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize(("path", "endpoint"), MUTATION_ROUTES)
def test_authenticated_csrf_mutation_reaches_handler(
    guarded_app, monkeypatch, path, endpoint
):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    calls = []
    guarded_app.view_functions[endpoint] = _recording_handler(calls)
    client, csrf_token = _authenticated_client(guarded_app)

    response = client.post(path, json={}, headers={"X-CSRF-TOKEN": csrf_token})

    assert response.status_code == 200
    assert response.get_json() == {"handler_reached": True}
    assert calls == [True]


def test_local_development_preserves_mutation_auth_opt_out(guarded_app, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    calls = []
    guarded_app.view_functions["device_api.execute_command"] = _recording_handler(calls)

    response = guarded_app.test_client().post(
        "/api/device/test-device/command/Start", json={}
    )

    assert response.status_code == 200
    assert calls == [True]


def test_local_opt_in_and_csrf_rejection_block_mutation_handlers(
    guarded_app, monkeypatch
):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    calls = []
    endpoint = "device_api.execute_command"
    path = "/api/device/test-device/command/Start"
    guarded_app.view_functions[endpoint] = _recording_handler(calls)
    client, _csrf_token = _authenticated_client(guarded_app)

    unauthenticated = guarded_app.test_client().post(path, json={})
    missing_csrf = client.post(path, json={})

    assert unauthenticated.status_code == missing_csrf.status_code == 401
    assert calls == []


def test_malformed_jwt_is_a_generic_authentication_failure(guarded_app, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    calls = []
    guarded_app.view_functions["device_api.execute_command"] = _recording_handler(calls)
    client = guarded_app.test_client()
    client.set_cookie("access_token_cookie", "garbage")

    response = client.post("/api/device/test-device/command/Start", json={})

    body = response.get_data(as_text=True)
    assert response.status_code == 401
    assert response.get_json() == {
        "msg": "Missing or invalid authentication credentials"
    }
    assert calls == []
    assert "Traceback" not in body
    assert str(BACKEND_DIR) not in body


def test_unexpected_guard_fault_is_not_converted_to_authentication_failure(
    guarded_app, monkeypatch
):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    mutation_auth = importlib.import_module("mutation_auth")
    monkeypatch.setattr(
        mutation_auth,
        "verify_jwt_in_request",
        lambda: (_ for _ in ()).throw(RuntimeError("invalid JWT configuration")),
    )
    guard = guarded_app.before_request_funcs["device_api"][0]

    with guarded_app.test_request_context(
        "/api/device/test-device/command/Start", method="POST"
    ):
        with pytest.raises(RuntimeError, match="invalid JWT configuration"):
            guard()


def test_safe_gets_remain_public_but_debug_monitor_requires_auth(
    guarded_app, monkeypatch
):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    safe_calls = []
    debug_calls = []
    guarded_app.view_functions["device_api.list_devices"] = _recording_handler(
        safe_calls
    )
    guarded_app.view_functions["device_api.debug_monitor_device"] = _recording_handler(
        debug_calls
    )
    client = guarded_app.test_client()

    safe_response = client.get("/api/devices")
    debug_response = client.get("/api/debug/monitor/test-device")

    assert safe_response.status_code == 200
    assert safe_calls == [True]
    assert debug_response.status_code == 401
    assert debug_calls == []
