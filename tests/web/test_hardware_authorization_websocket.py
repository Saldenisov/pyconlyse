"""T11 WebSocket command authorization contract with fake devices."""

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest


def test_missing_ws_approval_is_428(ws_gate):
    from hardware_authorization import AuthorizationError, authorize_websocket_command
    with pytest.raises(AuthorizationError) as exc:
        authorize_websocket_command(
            ws_gate,
            subject="alice",
            role="operator",
            sid="sid-1",
            device="motor/test",
            command="move_axis",
            args={"axis": 1, "position": 2.5},
            nonce=None,
        )
    assert exc.value.status_code == 428


@pytest.mark.parametrize("nonce", ["b" * 64, "c" * 64])
def test_ws_mismatch_and_replay_are_409(ws_gate, nonce):
    from hardware_authorization import AuthorizationError, authorize_websocket_command
    with pytest.raises(AuthorizationError) as mismatch:
        authorize_websocket_command(
            ws_gate,
            subject="mallory",
            role="operator",
            sid="sid-1",
            device="motor/test",
            command="move_axis",
            args={"axis": 1, "position": 2.5},
            nonce=nonce,
        )
    assert mismatch.value.status_code == 409


def test_ws_positive_path_consumes_before_device_access(ws_gate, fake_device):
    from hardware_authorization import authorize_websocket_command
    fake_device.marker_path = ws_gate.consumed_dir / ("a" * 64 + ".used")
    result = authorize_websocket_command(
        ws_gate,
        subject="alice",
        role="operator",
        sid="sid-1",
        device="motor/test",
        command="move_axis",
        args={"axis": 1, "position": 2.5},
        nonce="a" * 64,
        before_side_effect=fake_device.command_inout,
    )
    assert result is True
    assert fake_device.marker_existed is True


def test_ws_denial_has_command_error_code(ws_gate, socket_client):
    response = socket_client.execute_command(
        {"device": "motor/test", "command": "move_axis", "args": {"axis": 1, "position": 2.5}, "nonce": None}
    )
    assert response["event"] == "command_error"
    assert response["code"] == "hardware_approval_required"
    assert response["status"] == 428


def test_real_socket_handler_denies_before_monitor_access(real_handler):
    emitted = []
    real_handler.monitor.get_device = lambda *_a: (_ for _ in ()).throw(
        AssertionError("monitor access must follow authorization")
    )
    real_handler.authorize_runtime_operation = lambda *_a, **_k: (_ for _ in ()).throw(
        real_handler.AuthorizationError(428, "hardware_approval_required", "approval required")
    )
    real_handler.emit = lambda event, payload: emitted.append((event, payload))
    socket = real_handler.init_socketio(types.SimpleNamespace(config={}))
    socket.handlers["execute_command"]({"device": "motor/test", "command": "move_axis", "args": {}})
    assert emitted[-1][0] == "command_error"
    assert emitted[-1][1]["status"] == 428
    assert emitted[-1][1]["code"] == "hardware_approval_required"


@pytest.fixture
def ws_gate(tmp_path):
    from hardware_authorization import AuthorizationConfig
    os.environ["TANGO_HOST"] = "stub.invalid:1"
    os.environ["PYCONLYSE_TANGO_HOST"] = "stub.invalid:1"
    root = tmp_path / "external"
    (root / "approvals").mkdir(parents=True)
    (root / "consumed").mkdir()
    (root / "policy.json").write_text(json.dumps({
        "version": 1,
        "subjects": {"alice": {"roles": ["operator"]}},
        "roles": {"operator": {"websocket.execute_command": ["device.command"]}},
        "operations": [{
            "method": "WEBSOCKET",
            "route_id": "websocket.execute_command",
            "action": "device.command",
            "targets": [{"device": "motor/test", "command": "move_axis"}],
            "roles": ["operator"],
            "args": {"type": "object", "properties": {"axis": {"type": "integer", "minimum": 0, "maximum": 15}, "position": {"type": "number", "minimum": -1000, "maximum": 1000}}, "required": ["axis", "position"], "additionalProperties": False},
        }],
    }), encoding="utf-8")
    now = datetime.now(timezone.utc)
    (root / "approvals" / ("a" * 64 + ".json")).write_text(json.dumps({
        "version": 1, "subject": "alice", "role": "operator", "method": "WEBSOCKET",
        "route_id": "websocket.execute_command", "action": "device.command",
        "targets": [{"device": "motor/test", "command": "move_axis"}],
        "args": {"axis": 1, "position": 2.5}, "nonce": "a" * 64,
        "approved_by": "Operator One", "hardware_safe": True,
        "issued_at": now.isoformat(), "expires_at": (now + timedelta(minutes=1)).isoformat(),
    }), encoding="utf-8")
    for nonce in ("b" * 64, "c" * 64):
        approval_path = root / "approvals" / f"{nonce}.json"
        approval_path.write_text(json.dumps({
            "version": 1, "subject": "alice", "role": "operator", "method": "WEBSOCKET",
            "route_id": "websocket.execute_command", "action": "device.command",
            "targets": [{"device": "motor/test", "command": "move_axis"}],
            "args": {"axis": 1, "position": 2.5}, "nonce": nonce,
            "approved_by": "Operator One", "hardware_safe": True,
            "issued_at": now.isoformat(), "expires_at": (now + timedelta(minutes=1)).isoformat(),
        }), encoding="utf-8")
    return AuthorizationConfig(root / "policy.json", root / "approvals", root / "consumed", strict=True)


@pytest.fixture
def fake_device():
    class Device:
        marker_existed = False

        def command_inout(self, *_args):
            self.marker_existed = self.marker_path.exists()
            return None

    return Device()


@pytest.fixture
def socket_client(ws_gate):
    from hardware_authorization import AuthorizationError, authorize_websocket_command

    class SocketClient:
        def execute_command(self, payload):
            try:
                authorize_websocket_command(
                    ws_gate, subject="alice", role="operator", sid="sid-1",
                    device=payload["device"], command=payload["command"],
                    args=payload.get("args"), nonce=payload.get("nonce"),
                )
            except AuthorizationError as exc:
                return {"event": "command_error", "code": exc.code, "status": exc.status_code}
            return {"event": "command_result", "status": 200}

    return SocketClient()


@pytest.fixture
def real_handler(monkeypatch):
    from tests._tango_stub import install_tango_stub
    install_tango_stub(monkeypatch)
    flask_module = types.ModuleType("flask")
    flask_module.current_app = types.SimpleNamespace(config={})
    flask_module.request = types.SimpleNamespace(sid="sid-1", cookies={})
    socketio_module = types.ModuleType("flask_socketio")

    class FakeSocket:
        def __init__(self, app, **_kwargs):
            self.handlers = {}

        def on(self, event):
            return lambda fn: self.handlers.setdefault(event, fn) or fn

    socketio_module.SocketIO = FakeSocket
    socketio_module.emit = lambda *_a, **_k: None
    socketio_module.join_room = lambda *_a, **_k: None
    socketio_module.leave_room = lambda *_a, **_k: None
    jwt_module = types.ModuleType("flask_jwt_extended")
    jwt_module.decode_token = lambda token: {"sub": token}
    jwt_module.get_jwt_identity = lambda: "alice"
    monkeypatch.setitem(sys.modules, "flask", flask_module)
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)
    monkeypatch.setitem(sys.modules, "flask_jwt_extended", jwt_module)
    sys.modules.pop("websocket_handler", None)
    sys.modules.pop("web.backend.websocket_handler", None)
    import importlib
    return importlib.import_module("web.backend.websocket_handler")
