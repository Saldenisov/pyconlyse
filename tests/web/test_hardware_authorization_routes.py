"""Route-level T11 matrix; all handlers use fake side effects only."""

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from tests.web._hardware_authorization_test_support import (
    simulate_hardware_authorization_service_acl,
)


DANGEROUS_ROUTES = [
    ("device.command", "POST", "/api/device/motor/command/move_axis"),
    ("device.attribute", "POST", "/api/device/motor/attribute/position"),
    ("server.control", "POST", "/api/server/control"),
    ("itest.output", "POST", "/api/device/itest/power/1/slot/1/output"),
    ("itest.current", "POST", "/api/device/itest/power/1/slot/1/current"),
    ("daqmx.write", "POST", "/api/daqmx/device/daq/write"),
    ("psp.ack", "POST", "/api/psp/device/vacuum/commands/ack"),
    ("camera.capture", "POST", "/api/device/camera/cam/capture"),
    ("camera.grabbing", "POST", "/api/camera/cam/grabbing"),
    ("camera.trigger", "POST", "/api/camera/cam/trigger"),
    ("spectrograph.parameters", "POST", "/api/spectrograph/spec/parameters"),
    ("vd2.initialize", "POST", "/api/pump-probe-vd2/initialize"),
    ("vd2.remoteex", "POST", "/api/pump-probe-vd2/runtime/remoteex/start"),
    ("vd2.parameter", "POST", "/api/pump-probe-vd2/parameter/mcp_gain"),
    ("vd2.command", "POST", "/api/pump-probe-vd2/command/Acquire"),
    ("v0.initialize", "POST", "/api/pump-probe-v0/hardware/initialize"),
    ("v0.run", "POST", "/api/pump-probe-v0/run"),
    ("v0.stage-move", "POST", "/api/pump-probe-v0/stage/move"),
    ("v0.stage-stop", "POST", "/api/pump-probe-v0/stage/stop"),
]


@pytest.mark.parametrize("route_id,method,path", DANGEROUS_ROUTES)
def test_dangerous_route_requires_bound_approval(route_id, method, path, gate_config):
    from hardware_authorization import AuthorizationError, authorize_http_route
    with pytest.raises(AuthorizationError) as exc:
        authorize_http_route(
            gate_config,
            subject="alice",
            role="operator",
            route_id=route_id,
            method=method,
            path=path,
            payload={},
            nonce=None,
        )
    assert exc.value.status_code == 428


def test_safe_v0_get_and_preflight_never_enter_hardware_gate(fake_v0_client, gate_config):
    assert fake_v0_client.get("/api/pump-probe-v0/state").status_code == 200
    assert fake_v0_client.get("/api/pump-probe-v0/hardware/preflight").status_code == 200
    assert fake_v0_client.proxy.mutating_calls == []


def test_v0_preflight_fix_false_does_not_issue_side_effects(fake_v0_client):
    response = fake_v0_client.post("/api/pump-probe-v0/hardware/preflight", json={})
    assert response.status_code == 200
    assert fake_v0_client.proxy.mutating_calls == []
    assert fake_v0_client.proxy.passive_calls


def test_v0_get_config_and_state_do_not_start_grabbing_or_register_order(fake_v0_client):
    fake_v0_client.get("/api/pump-probe-v0/hardware-config")
    fake_v0_client.get("/api/pump-probe-v0/state")
    assert fake_v0_client.proxy.mutating_calls == []


def test_v0_config_changes_are_in_memory_only(fake_v0_client):
    response = fake_v0_client.post("/api/pump-probe-v0/config", json={"control_mode": "emulator"})
    assert response.status_code == 200
    assert fake_v0_client.proxy.mutating_calls == []
    response = fake_v0_client.post("/api/pump-probe-v0/hardware-config", json={"control_mode": "emulator"})
    assert response.status_code == 200
    assert fake_v0_client.proxy.mutating_calls == []


def test_v0_tango_idle_get_never_starts_acquisition(fake_v0_client):
    fake_v0_client.get("/api/pump-probe-v0/state")
    assert not set(fake_v0_client.proxy.calls) & {
        "start_grabbing", "register_order", "give_order", "move_axis",
        "stop_axis", "turn_on_axis", "set_channels_states", "scpi_write",
        "DevStop", "HardKillServer", "DevStart",
    }


def test_v0_enforced_initialize_requires_approval_before_side_effect(fake_v0_client, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    response = fake_v0_client.post("/api/pump-probe-v0/hardware/initialize", json={})
    assert response.status_code == 403
    assert fake_v0_client.proxy.mutating_calls == []
    assert not (fake_v0_client.proxy.calls and "approval" in fake_v0_client.proxy.calls)


@pytest.mark.parametrize("path,payload", [
    ("/api/pump-probe-v0/stage/move", {"axis": "1", "position": "2.5"}),
    ("/api/pump-probe-v0/run", {"running": True, "point_count": 2}),
    ("/api/pump-probe-v0/realtime", {"enabled": True}),
])
def test_v0_control_payloads_retain_normalized_sequence_fields(fake_v0_client, path, payload):
    response = fake_v0_client.post(path, json=payload)
    assert response.status_code in {200, 400, 403, 428}
    assert fake_v0_client.proxy.mutating_calls == []


@pytest.mark.parametrize("path,payload", [
    ("/api/device/itest/test/current", {"action": action})
    for action in ("inc_fine", "dec_fine", "inc_coarse", "dec_coarse")
] + [
    ("/api/device/itest/test/slot/1/current", {"action": action})
    for action in ("inc_fine", "dec_fine", "inc_coarse", "dec_coarse")
])
def test_itest_increment_decrement_fail_closed_before_guard_or_proxy(device_client, path, payload, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    response = device_client.post(path, json=payload)
    assert response.status_code == 403
    assert response.get_json()["code"] == "hardware_not_authorized"
    assert device_client.guard_calls == []
    assert device_client.side_effects == []


@pytest.mark.parametrize("path,payload", [
    ("/api/pump-probe-v0/run", {"running": True}),
    ("/api/pump-probe-v0/realtime", {"enabled": True}),
])
def test_v0_tango_start_paths_fail_closed_before_order_or_proxy(fake_v0_client, path, payload, monkeypatch):
    config = fake_v0_client.post("/api/pump-probe-v0/hardware-config", json={"control_mode": "tango"})
    assert config.status_code == 200
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    response = fake_v0_client.post(path, json=payload)
    assert response.status_code == 403
    assert response.get_json()["code"] == "hardware_not_authorized"
    assert fake_v0_client.proxy.mutating_calls == []


@pytest.mark.parametrize("path,payload", [
    ("/api/pump-probe-v0/run", {"running": False}),
    ("/api/pump-probe-v0/realtime", {"enabled": False}),
])
def test_v0_stop_disable_paths_have_no_mutating_calls(fake_v0_client, path, payload):
    response = fake_v0_client.post(path, json=payload)
    assert response.status_code in {200, 400, 403, 428}
    assert fake_v0_client.proxy.mutating_calls == []


def test_device_routes_call_hardware_guard_before_any_proxy(device_client):
    calls = device_client.guard_calls
    for path, payload in (
        ("/api/device/test/command/move_axis", {"args": {"axis": 1, "position": 2.0}}),
        ("/api/device/test/attribute/position", {"value": 2.0}),
        ("/api/server/control", {"action": "start", "server_name": "DS/test"}),
    ):
        response = device_client.post(path, json=payload)
        assert response.status_code == 428
    assert len(calls) == 3
    assert all(call["action"] for call in calls)
    assert all(call["targets"] for call in calls)
    assert all("args" in call for call in calls)
    assert device_client.side_effects == []


def test_generic_device_command_consumes_readonly_approval_before_proxy_side_effect(
    monkeypatch, tmp_path
):
    """The actual HTTP command route binds JWT identity to durable approval use."""
    from tests._tango_stub import install_tango_stub

    install_tango_stub(monkeypatch)
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    sys.modules.pop("device_api", None)
    import device_api

    nonce = "b" * 64
    root = tmp_path / "external-http-authorization"
    approval_dir = root / "approvals"
    consumed_dir = root / "consumed"
    root.mkdir()
    approval_dir.mkdir()
    consumed_dir.mkdir()
    policy_path = root / "policy.json"
    args = {"axis": 1, "position": 2.5}
    policy_path.write_text(json.dumps({
        "version": 1,
        "subjects": {"alice": {"roles": ["operator"]}},
        "roles": {"operator": {"device.command": ["execute"]}},
        "operations": [{
            "method": "POST",
            "route_id": "device.command",
            "action": "execute",
            "targets": [{"device": "motor/test", "command": "move_axis"}],
            "roles": ["operator"],
            "args": {
                "type": "object",
                "required": ["axis", "position"],
                "additionalProperties": False,
                "properties": {
                    "axis": {"type": "integer", "minimum": 0, "maximum": 15},
                    "position": {
                        "type": "number", "minimum": -1000, "maximum": 1000,
                    },
                },
            },
        }],
    }), encoding="utf-8")
    issued_at = datetime.now(timezone.utc)
    approval_path = approval_dir / f"{nonce}.json"
    approval_path.write_text(json.dumps({
        "version": 1,
        "subject": "alice",
        "role": "operator",
        "method": "POST",
        "route_id": "device.command",
        "action": "execute",
        "targets": [{"device": "motor/test", "command": "move_axis"}],
        "args": args,
        "approved_by": "External Operator",
        "hardware_safe": True,
        "nonce": nonce,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
    }), encoding="utf-8")
    monkeypatch.setenv("PYCONLYSE_HARDWARE_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_APPROVAL_DIR", str(approval_dir))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_CONSUMED_DIR", str(consumed_dir))
    simulate_hardware_authorization_service_acl(
        monkeypatch,
        policy_path=policy_path,
        approval_dir=approval_dir,
        consumed_dir=consumed_dir,
    )

    marker = consumed_dir / f"{nonce}.used"
    command_calls = []

    class FakeDevice:
        def command_inout(self, command, value):
            command_calls.append((command, value, marker.exists()))
            return "ok"

    monkeypatch.setattr(
        device_api.DeviceManager, "get_device", lambda _device: FakeDevice()
    )
    application = Flask(__name__)
    application.config.update(
        JWT_SECRET_KEY="0123456789abcdef0123456789abcdef",
        JWT_TOKEN_LOCATION=["headers"],
    )
    JWTManager(application)
    application.register_blueprint(device_api.device_api)
    with application.app_context():
        token = create_access_token(identity="alice")

    response = application.test_client().post(
        "/api/device/motor/test/command/move_axis",
        json={"args": args},
        headers={
            "Authorization": f"Bearer {token}",
            "X-PYCONLYSE-HARDWARE-APPROVAL": nonce,
        },
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["success"] is True
    assert command_calls == [("move_axis", args, True)]
    assert marker.exists()


@pytest.fixture
def gate_config(tmp_path):
    from hardware_authorization import AuthorizationConfig
    root = tmp_path / "external"
    root.mkdir()
    approval = root / "approvals"
    consumed = root / "consumed"
    approval.mkdir()
    consumed.mkdir()
    policy = root / "policy.json"
    policy.write_text(json.dumps({
        "version": 1,
        "subjects": {"alice": {"roles": ["operator"]}},
        "roles": {"operator": {route_id: ["execute"] for route_id, _, _ in DANGEROUS_ROUTES}},
        "operations": [{
            "method": method,
            "route_id": route_id,
            "action": "execute",
            "targets": [{"device": "route", "command": route_id}],
            "roles": ["operator"],
            "args": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        } for route_id, method, _path in DANGEROUS_ROUTES],
    }), encoding="utf-8")
    return AuthorizationConfig(policy, approval, consumed, strict=True)


@pytest.fixture
def fake_v0_client(monkeypatch):
    from tests._tango_stub import install_tango_stub
    install_tango_stub(monkeypatch)
    from flask import Flask
    os.environ["TANGO_HOST"] = "stub.invalid:1"
    os.environ["PYCONLYSE_TANGO_HOST"] = "stub.invalid:1"
    sys.modules.pop("pump_probe_v0_api", None)
    import pump_probe_v0_api
    import mutation_auth
    # Bypass only legacy JWT preprocessing so this fixture reaches T11's
    # hardware authorization layer; production gate remains unmodified.
    monkeypatch.setattr(mutation_auth, "mutation_auth_required", lambda: False)

    class FakeProxy:
        def __init__(self):
            self.calls = []
            self.passive_calls = []
            self.mutating_calls = []

        def command_inout(self, name, value=None):
            self.calls.append(name)
            if name in {"start_grabbing", "register_order", "give_order", "move_axis", "stop_axis", "turn_on_axis", "set_channels_states", "scpi_write", "DevStop", "HardKillServer", "DevStart"}:
                self.mutating_calls.append(name)
            else:
                self.passive_calls.append(name)
            return [] if name in {"register_order", "get_status_axis"} else "0"

        def read_attribute(self, name):
            return types.SimpleNamespace(value=0)

        def write_attribute(self, name, value):
            self.calls.append(f"write:{name}")
            self.mutating_calls.append(f"write:{name}")

    proxy = FakeProxy()
    pump_probe_v0_api._tango_proxy = lambda *_a, **_k: proxy
    app = Flask(__name__)
    app.register_blueprint(pump_probe_v0_api.pump_probe_v0_api)
    for guard in app.before_request_funcs.get("pump_probe_v0_api", ()):
        guard.__globals__["mutation_auth_required"] = lambda: False
    client = app.test_client()
    client.proxy = proxy
    return client


@pytest.fixture
def device_client(monkeypatch):
    from tests._tango_stub import install_tango_stub
    install_tango_stub(monkeypatch)
    from flask import Flask, jsonify
    os.environ["TANGO_HOST"] = "stub.invalid:1"
    os.environ["PYCONLYSE_TANGO_HOST"] = "stub.invalid:1"
    sys.modules.pop("device_api", None)
    import device_api
    import mutation_auth
    monkeypatch.setattr(mutation_auth, "mutation_auth_required", lambda: False)
    monkeypatch.setattr(device_api, "_maybe_require_auth", lambda: None)
    app = Flask(__name__)
    app.config["TESTING"] = True
    calls = []
    side_effects = []

    def guard(**kwargs):
        calls.append(kwargs)
        return jsonify({"success": False, "error": "approval required"}), 428

    monkeypatch.setattr(device_api, "require_http_hardware", guard, raising=False)
    monkeypatch.setattr(device_api.DeviceManager, "get_device", lambda *_a, **_k: side_effects.append("device"), raising=False)
    monkeypatch.setattr(device_api, "_resolve_server_name", lambda *_a, **_k: side_effects.append("resolve"), raising=False)
    monkeypatch.setattr(device_api, "_find_starter_for_server", lambda *_a, **_k: side_effects.append("starter"), raising=False)
    app.register_blueprint(device_api.device_api)
    for guard in app.before_request_funcs.get("device_api", ()):
        guard.__globals__["mutation_auth_required"] = lambda: False
    client = app.test_client()
    client.guard_calls = calls
    client.side_effects = side_effects
    return client
