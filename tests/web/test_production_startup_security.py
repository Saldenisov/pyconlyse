import errno
import importlib
import json
import socket
from pathlib import Path

import pytest
from flask import Flask

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
BACKEND_DIR = WEB_DIR / "backend"
VALID_SECRET = "0123456789abcdef0123456789abcdef"

from tests.web._hardware_authorization_test_support import (
    simulate_hardware_authorization_service_acl,
)


@pytest.fixture
def t11_environment(monkeypatch, tmp_path):
    root = tmp_path / "external-t11"
    approval = root / "approvals"
    consumed = root / "consumed"
    approval.mkdir(parents=True)
    consumed.mkdir()
    policy = root / "policy.json"
    policy.write_text(json.dumps({
        "version": 1,
        "subjects": {"operator": {"roles": ["operator"]}},
        "roles": {"operator": {}},
        "operations": [],
    }), encoding="utf-8")
    monkeypatch.setenv("PYCONLYSE_HARDWARE_POLICY_PATH", str(policy))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_APPROVAL_DIR", str(approval))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_CONSUMED_DIR", str(consumed))
    simulate_hardware_authorization_service_acl(
        monkeypatch,
        policy_path=policy,
        approval_dir=approval,
        consumed_dir=consumed,
    )
    yield root


@pytest.fixture
def production_module(monkeypatch):
    monkeypatch.syspath_prepend(str(WEB_DIR))
    return importlib.import_module("start_production")


@pytest.fixture
def app_module(monkeypatch):
    from tests._tango_stub import install_tango_stub
    install_tango_stub(monkeypatch)
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    return importlib.import_module("app")


def _production_environment(secret=VALID_SECRET):
    return {
        "JWT_SECRET_KEY": secret,
        "PYCONLYSE_AUTH_USERS": '{"operator": "hashed-password"}',
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT": "true",
    }


def _configure_production_environment(monkeypatch, secret):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("PYCONLYSE_JWT_COOKIE_CSRF_PROTECT", "true")
    monkeypatch.setenv("PYCONLYSE_CORS_ORIGINS", "https://control.example.test")


def _fake_tcp_address(host, port, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, port))]


@pytest.mark.parametrize("secret", ("short-secret", "é" * 15))
def test_production_secret_minimum_is_enforced_before_startup_and_in_app(
    monkeypatch, production_module, app_module, secret
):
    expected = "JWT_SECRET_KEY must be at least 32 bytes in production"

    with pytest.raises(RuntimeError, match=f"^{expected}$"):
        production_module.configure_production_environment(
            _production_environment(secret)
        )

    _configure_production_environment(monkeypatch, secret)
    with pytest.raises(RuntimeError, match=f"^{expected}$"):
        app_module.configure_security(Flask(__name__))


def test_production_accepts_a_32_byte_utf8_jwt_secret(
    monkeypatch, production_module, app_module, t11_environment
):
    secret = "é" * 16
    environment = _production_environment(secret)

    production_module.configure_production_environment(environment)
    assert environment["PYCONLYSE_PRODUCTION"] == "true"

    _configure_production_environment(monkeypatch, secret)
    flask_app = Flask(__name__)
    app_module.configure_security(flask_app)
    assert flask_app.config["JWT_SECRET_KEY"] == secret


def test_development_generates_a_jwt_secret_when_unset(monkeypatch, app_module):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    flask_app = Flask(__name__)

    app_module.configure_security(flask_app)

    assert len(flask_app.config["JWT_SECRET_KEY"].encode("utf-8")) >= 32


@pytest.mark.parametrize("value", ("", "0", "65536", "invalid", "-1"))
def test_web_port_must_be_a_tcp_port(production_module, value):
    expected = "PYCONLYSE_WEB_PORT must be an integer from 1 to 65535"

    with pytest.raises(RuntimeError, match=f"^{expected}$"):
        production_module.parse_web_port(value)


def test_preflight_binds_configured_address_and_closes_probe(
    monkeypatch, production_module
):
    probes = []

    class Probe:
        def __init__(self):
            self.bound_address = None
            self.closed = False

        def bind(self, address):
            self.bound_address = address

        def close(self):
            self.closed = True

    def create_probe(*_):
        probe = Probe()
        probes.append(probe)
        return probe

    monkeypatch.setattr(
        production_module.socket,
        "getaddrinfo",
        _fake_tcp_address,
    )
    monkeypatch.setattr(production_module.socket, "socket", create_probe)

    production_module.preflight_web_port("127.0.0.1", 5000)

    assert [probe.bound_address for probe in probes] == [("127.0.0.1", 5000)]
    assert all(probe.closed for probe in probes)


def test_preflight_fails_closed_when_configured_port_is_occupied(
    monkeypatch, production_module
):
    class OccupiedProbe:
        closed = False

        def bind(self, _address):
            raise OSError(errno.EADDRINUSE, "Address already in use")

        def close(self):
            self.closed = True

    probe = OccupiedProbe()
    monkeypatch.setattr(
        production_module.socket,
        "getaddrinfo",
        _fake_tcp_address,
    )
    monkeypatch.setattr(production_module.socket, "socket", lambda *_: probe)

    with pytest.raises(
        RuntimeError,
        match="^PYCONLYSE_WEB_PORT 5000 is already in use for host '127.0.0.1'$",
    ):
        production_module.preflight_web_port("127.0.0.1", 5000)

    assert probe.closed is True


@pytest.mark.parametrize(
    ("failure", "diagnostic"),
    (
        (RuntimeError("bind failed"), "Error starting server: bind failed"),
        (ImportError("No module named 'simple_websocket'"), "Error starting server:"),
    ),
)
def test_production_server_failure_is_reported_and_propagated(
    capsys, production_module, failure, diagnostic
):
    class FailingSocketIO:
        def __init__(self):
            self.run_kwargs = None

        def run(self, *_args, **_kwargs):
            self.run_kwargs = _kwargs
            raise failure

    socketio = FailingSocketIO()
    with pytest.raises(type(failure), match=f"^{failure}$"):
        production_module.run_production_server(
            socketio, object(), "127.0.0.1", 5000
        )

    assert diagnostic in capsys.readouterr().out
    assert socketio.run_kwargs == {
        "debug": False,
        "port": 5000,
        "host": "127.0.0.1",
        "use_reloader": False,
    }


def test_production_socketio_runtime_and_dependencies_are_explicitly_threading_based(
    production_module, app_module
):
    """Keep launcher, Socket.IO runtime, and direct dependencies aligned."""
    with (WEB_DIR.parent / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    with (WEB_DIR.parent / "poetry.lock").open("rb") as handle:
        poetry_lock = tomllib.load(handle)

    assert production_module.SOCKETIO_ASYNC_MODE == "threading"
    assert production_module.SOCKETIO_WEBSOCKET_DEPENDENCY == "simple-websocket"
    assert production_module.SERVER_RUNTIME_CLASS == (
        "controlled single-process Werkzeug runner"
    )
    assert app_module.socketio.async_mode == production_module.SOCKETIO_ASYNC_MODE
    assert pyproject["tool"]["poetry"]["dependencies"]["simple-websocket"] == "==1.1.0"
    dev_dependencies = pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"]
    assert dev_dependencies["pytest"] == "==8.4.2"
    assert dev_dependencies["coverage"] == "==7.10.7"

    locked_packages = {package["name"]: package for package in poetry_lock["package"]}
    package_contracts = {
        "simple-websocket": (
            pyproject["tool"]["poetry"]["dependencies"]["simple-websocket"],
            ["main"],
        ),
        "pytest": (dev_dependencies["pytest"], ["dev"]),
        "coverage": (dev_dependencies["coverage"], ["dev"]),
    }
    for package_name, (declared_version, groups) in package_contracts.items():
        package = locked_packages[package_name]
        assert package["version"] == declared_version.removeprefix("==")
        assert package["groups"] == groups
    assert "eventlet" not in locked_packages
