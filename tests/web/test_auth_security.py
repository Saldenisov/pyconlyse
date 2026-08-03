import importlib
import os
import sys
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parents[2] / "web" / "backend"
WEB_DIR = BACKEND_DIR.parent


def _is_web_module(module):
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return False
    try:
        Path(module_file).resolve().relative_to(WEB_DIR.resolve())
    except (OSError, ValueError):
        return False
    return True


@pytest.fixture(autouse=True)
def isolate_tango_environment(monkeypatch):
    original_sys_path = list(sys.path)
    original_web_modules = {
        name: module for name, module in sys.modules.items() if _is_web_module(module)
    }
    for module_dir in (WEB_DIR, BACKEND_DIR):
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
    original_values = {
        name: os.environ.get(name)
        for name in ("TANGO_HOST", "PYCONLYSE_TANGO_HOST")
    }
    for name in original_values:
        monkeypatch.delenv(name, raising=False)
    yield
    for name, value in original_values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    for name, module in tuple(sys.modules.items()):
        if name not in original_web_modules and _is_web_module(module):
            sys.modules.pop(name, None)
    sys.modules.update(original_web_modules)
    sys.path[:] = original_sys_path


@pytest.fixture
def auth_client(monkeypatch):
    password_hash = generate_password_hash("test-password")
    monkeypatch.setenv(
        "PYCONLYSE_AUTH_USERS", f'{{"test-user": "{password_hash}"}}'
    )
    auth_module = importlib.import_module("auth")
    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_CSRF_PROTECT=False,
    )
    JWTManager(app)
    app.register_blueprint(auth_module.auth)
    return app.test_client()


def test_login_uses_configured_credentials_and_httponly_cookie(auth_client):
    response = auth_client.post(
        "/api/login", json={"username": "test-user", "password": "test-password"}
    )

    assert response.status_code == 200
    assert response.get_json() == {"login": True}
    assert "access_token_cookie=" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]


def test_login_does_not_accept_removed_hardcoded_credentials(auth_client):
    response = auth_client.post(
        "/api/login", json={"username": "admin", "password": "sad"}
    )

    assert response.status_code == 401


def test_login_is_unavailable_without_configured_users(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_AUTH_USERS", raising=False)
    auth_module = importlib.import_module("auth")
    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_CSRF_PROTECT=False,
    )
    JWTManager(app)
    app.register_blueprint(auth_module.auth)

    response = app.test_client().post(
        "/api/login", json={"username": "admin", "password": "sad"}
    )

    assert response.status_code == 503
    assert response.get_json() == {"msg": "Authentication is not configured"}


@pytest.mark.parametrize(
    ("production", "device_auth", "expected_calls"),
    [
        ("true", None, 1),
        ("true", "false", 1),
        ("false", None, 0),
        ("false", "false", 0),
    ],
)
def test_device_auth_requires_jwt_in_production(
    monkeypatch, production, device_auth, expected_calls
):
    device_module = importlib.import_module("device_api")
    jwt_checks = []
    monkeypatch.setattr(
        device_module,
        "verify_jwt_in_request",
        lambda: jwt_checks.append("required"),
    )
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", production)
    if device_auth is None:
        monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    else:
        monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", device_auth)

    with Flask(__name__).test_request_context("/api/device/test/command"):
        device_module._maybe_require_auth()

    assert len(jwt_checks) == expected_calls


def test_production_cookie_auth_requires_csrf_for_device_mutations(monkeypatch):
    password_hash = generate_password_hash("test-password")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv(
        "PYCONLYSE_AUTH_USERS", f'{{"test-user": "{password_hash}"}}'
    )
    auth_module = importlib.import_module("auth")
    device_module = importlib.import_module("device_api")
    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-production-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_SECURE=True,
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_SAMESITE="Lax",
        JWT_COOKIE_CSRF_PROTECT=True,
    )
    JWTManager(app)
    app.register_blueprint(auth_module.auth)

    @app.post("/api/protected-device-mutation")
    def protected_device_mutation():
        device_module._maybe_require_auth()
        return jsonify({"success": True})

    client = app.test_client()
    login_response = client.post(
        "/api/login",
        base_url="https://control.example.test",
        json={"username": "test-user", "password": "test-password"},
    )

    cookies = SimpleCookie()
    for header in login_response.headers.getlist("Set-Cookie"):
        cookies.load(header)
    assert login_response.status_code == 200
    assert cookies["access_token_cookie"]["httponly"] is True
    assert cookies["csrf_access_token"]["httponly"] == ""

    missing_csrf_response = client.post(
        "/api/protected-device-mutation",
        base_url="https://control.example.test",
    )
    assert missing_csrf_response.status_code == 401

    csrf_response = client.post(
        "/api/protected-device-mutation",
        base_url="https://control.example.test",
        headers={"X-CSRF-TOKEN": cookies["csrf_access_token"].value},
    )
    assert csrf_response.status_code == 200
    assert csrf_response.get_json() == {"success": True}


def test_production_security_configuration_requires_explicit_values(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("PYCONLYSE_AUTH_USERS", raising=False)
    monkeypatch.delenv("PYCONLYSE_CORS_ORIGINS", raising=False)
    isolated_app = Flask(__name__)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        app_module.configure_security(isolated_app)


def test_production_security_configuration_uses_secure_cookie_csrf_and_cors(
    monkeypatch,
):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-production-secret")
    monkeypatch.setenv(
        "PYCONLYSE_AUTH_USERS",
        f'{{"test-user": "{generate_password_hash("test-password")}"}}',
    )
    monkeypatch.setenv("PYCONLYSE_CORS_ORIGINS", "https://control.example.test")
    app_module = importlib.import_module("app")
    isolated_app = Flask(__name__)

    app_module.configure_security(isolated_app)

    assert isolated_app.config["JWT_COOKIE_SECURE"] is True
    assert isolated_app.config["JWT_COOKIE_CSRF_PROTECT"] is True
    assert isolated_app.config["JWT_COOKIE_HTTPONLY"] is True
    assert isolated_app.config["JWT_COOKIE_SAMESITE"] == "Lax"
    assert isolated_app.config["PYCONLYSE_CORS_ORIGINS"] == [
        "https://control.example.test"
    ]


def test_production_security_configuration_rejects_disabled_device_auth(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")

    with pytest.raises(RuntimeError, match="PYCONLYSE_ENFORCE_DEVICE_AUTH"):
        app_module.configure_security(Flask(__name__))


def test_production_security_configuration_rejects_disabled_csrf(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-production-secret")
    monkeypatch.setenv("PYCONLYSE_JWT_COOKIE_CSRF_PROTECT", "false")

    with pytest.raises(RuntimeError, match="PYCONLYSE_JWT_COOKIE_CSRF_PROTECT"):
        app_module.configure_security(Flask(__name__))


def test_production_security_configuration_rejects_wildcard_cors(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-production-secret")
    monkeypatch.setenv("PYCONLYSE_CORS_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="PYCONLYSE_CORS_ORIGINS"):
        app_module.configure_security(Flask(__name__))


def test_production_startup_rejects_disabled_device_authentication():
    production_module = importlib.import_module("start_production")
    environment = {
        "JWT_SECRET_KEY": "test-production-secret",
        "PYCONLYSE_AUTH_USERS": (
            f'{{"test-user": "{generate_password_hash("test-password")}"}}'
        ),
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "false",
    }

    with pytest.raises(RuntimeError, match="PYCONLYSE_ENFORCE_DEVICE_AUTH"):
        production_module.configure_production_environment(environment)


def test_production_startup_rejects_disabled_csrf():
    production_module = importlib.import_module("start_production")
    environment = {
        "JWT_SECRET_KEY": "test-production-secret",
        "PYCONLYSE_AUTH_USERS": (
            f'{{"test-user": "{generate_password_hash("test-password")}"}}'
        ),
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT": "false",
    }

    with pytest.raises(RuntimeError, match="PYCONLYSE_JWT_COOKIE_CSRF_PROTECT"):
        production_module.configure_production_environment(environment)


def test_production_security_configuration_rejects_plaintext_passwords(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    app_module = importlib.import_module("app")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-production-secret")
    monkeypatch.setenv("PYCONLYSE_AUTH_USERS", '{"test-user": "test-password"}')

    with pytest.raises(RuntimeError, match="password hashes"):
        app_module.configured_users()
