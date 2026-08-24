"""Software-only contracts for WebSocket device monitoring."""

import importlib
import json
import math
import sys
import types
from types import SimpleNamespace
from pathlib import Path

import pytest


class FakeAttribute:
    def __init__(self, value):
        self.value = value


class FakeDevice:
    def __init__(self, attributes=None, state="ON", status="Ready"):
        self.attributes = dict(attributes or {})
        self._state = state
        self._status = status

    def state(self):
        return self._state

    def status(self):
        return self._status

    def read_attribute(self, name):
        if name not in self.attributes:
            raise KeyError(name)
        return FakeAttribute(self.attributes[name])


class FailingDevice(FakeDevice):
    def state(self):
        raise RuntimeError("device unavailable")


class FakeSocket:
    def __init__(self):
        self.emitted = []

    def emit(self, event, payload, room=None):
        self.emitted.append((event, payload, room))


class FakeSocketIO(FakeSocket):
    def __init__(self, app, **kwargs):
        super().__init__()
        self.app = app
        self.options = kwargs
        self.handlers = {}

    def on(self, event):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register


class FakeThread:
    created = []

    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False
        self.created.append(self)

    def start(self):
        self.started = True


class FailingThread(FakeThread):
    def start(self):
        raise RuntimeError("thread start failed")


@pytest.fixture
def handler(monkeypatch):
    """Import handler against test Tango stub without retaining global state."""
    backend = Path(__file__).resolve().parents[2] / "web" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    flask_module = types.ModuleType("flask")
    flask_module.current_app = SimpleNamespace(config={})
    flask_module.request = SimpleNamespace(sid=None, cookies={})
    flask_module.jsonify = lambda payload: payload
    socketio_module = types.ModuleType("flask_socketio")
    socketio_module.SocketIO = FakeSocketIO
    socketio_module.emit = lambda *_args, **_kwargs: None
    socketio_module.join_room = lambda *_args, **_kwargs: None
    socketio_module.leave_room = lambda *_args, **_kwargs: None
    jwt_module = types.ModuleType("flask_jwt_extended")
    jwt_module.decode_token = lambda token: {"token": token}
    jwt_module.get_jwt_identity = lambda: "alice"
    monkeypatch.setitem(sys.modules, "flask", flask_module)
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)
    monkeypatch.setitem(sys.modules, "flask_jwt_extended", jwt_module)
    monkeypatch.delitem(sys.modules, "web.backend.websocket_handler", raising=False)
    monkeypatch.delitem(sys.modules, "hardware_authorization", raising=False)
    module = importlib.import_module("web.backend.websocket_handler")
    module.monitoring_rooms.clear()
    module.device_subscriptions.clear()
    module.client_subscriptions.clear()
    module.socketio = None
    return module


def test_json_and_environment_helpers_produce_json_safe_contracts(handler, monkeypatch):
    assert handler._json_safe_number("1.25") == 1.25
    assert handler._json_safe_number("invalid", default=-1) == -1
    assert handler._json_safe_number(math.nan) is None
    assert handler._json_safe_number(math.inf) is None
    json.dumps({"measurement": handler._json_safe_number(math.nan)}, allow_nan=False)

    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    assert handler._env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH") is False
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", " YES ")
    assert handler._env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH") is True
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "0")
    assert handler._env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH", default=True) is False


def test_socket_auth_uses_configured_http_only_cookie_when_enforcement_is_enabled(handler, monkeypatch):
    calls = []
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    monkeypatch.setattr(handler, "decode_token", lambda token: calls.append(token))
    assert handler._socket_auth_allowed({"token": "ignored"}) is True
    assert calls == []

    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setattr(handler, "request", SimpleNamespace(cookies={}))
    assert handler._socket_auth_allowed({"token": "ignored"}) is False
    assert calls == []

    monkeypatch.setattr(
        handler,
        "current_app",
        SimpleNamespace(config={"JWT_ACCESS_COOKIE_NAME": "custom_access"}),
    )
    monkeypatch.setattr(
        handler,
        "request",
        SimpleNamespace(cookies={"custom_access": "valid-cookie"}),
    )
    assert handler._socket_auth_allowed({"token": "ignored"}) is True
    assert calls == ["valid-cookie"]

    monkeypatch.setattr(
        handler,
        "decode_token",
        lambda _token: (_ for _ in ()).throw(ValueError("bad cookie")),
    )
    assert handler._socket_auth_allowed(None) is False


def test_socket_auth_defaults_to_required_in_production_despite_false_override(handler, monkeypatch):
    calls = []
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    monkeypatch.setattr(handler, "request", SimpleNamespace(cookies={"access_token_cookie": "cookie"}))
    monkeypatch.setattr(handler, "decode_token", lambda token: calls.append(token))

    assert handler._socket_auth_allowed(None) is True
    assert calls == ["cookie"]

    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    assert handler._socket_auth_allowed(None) is True
    assert calls == ["cookie", "cookie"]


def test_connect_rejects_missing_cookie_before_registering_client(handler, monkeypatch):
    socket_emits = []
    socket = handler.init_socketio(object())
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a", cookies={}))
    monkeypatch.setattr(handler, "emit", lambda event, payload: socket_emits.append((event, payload)))

    assert socket.handlers["connect"]() is False
    assert socket_emits == []


def test_get_device_caches_success_and_does_not_cache_connection_errors(handler, monkeypatch):
    created = []

    def make_device(name):
        created.append(name)
        return FakeDevice()

    monitor = handler.DeviceMonitor()
    monkeypatch.setattr(handler.tango, "DeviceProxy", make_device)
    assert monitor.get_device("test/device") is monitor.get_device("test/device")
    assert created == ["test/device"]

    monkeypatch.setattr(handler.tango, "DeviceProxy", lambda _name: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(RuntimeError, match="offline"):
        monitor.get_device("offline/device")
    assert "offline/device" not in monitor.device_cache


def test_monitor_itest_payload_is_json_safe_and_uses_hardware_slot_ids(handler, monkeypatch):
    device = FakeDevice(
        {
            "names": ["Channel A", "Channel B"],
            "states": [1, 0],
            "currents_meas": [math.nan, math.inf],
            "currents_setpoint": [0.75, "1.25"],
            "ids": [12, "18"],
        }
    )
    fake_socket = FakeSocket()
    monitor = handler.DeviceMonitor()
    monkeypatch.setattr(handler.tango, "DeviceProxy", lambda _name: device)
    monkeypatch.setattr(handler, "socketio", fake_socket)

    monitor.monitor_device("power/itest/test", "room-1")

    [(event, payload, room)] = fake_socket.emitted
    assert (event, room) == ("device_update", "room-1")
    assert payload["slot_count"] == 2
    assert payload["slots"] == [
        {"id": 12, "index": 0, "name": "Channel A", "state": True, "current_measured": None, "current_setpoint": 0.75},
        {"id": 18, "index": 1, "name": "Channel B", "state": False, "current_measured": None, "current_setpoint": 1.25},
    ]
    json.dumps(payload, allow_nan=False)


def test_monitor_connection_failure_emits_device_error(handler, monkeypatch):
    fake_socket = FakeSocket()
    monitor = handler.DeviceMonitor()
    monkeypatch.setattr(handler.tango, "DeviceProxy", lambda _name: FailingDevice())
    monkeypatch.setattr(handler, "socketio", fake_socket)

    monitor.monitor_device("camera/offline", "room-2")

    [(event, payload, room)] = fake_socket.emitted
    assert (event, room) == ("device_error", "room-2")
    assert payload["device"] == "camera/offline"
    assert payload["connected"] is False
    assert "device unavailable" in payload["error"]


def test_monitoring_loop_exits_after_recoverable_error_without_background_thread(handler, monkeypatch):
    room_id = "device_test/error"
    handler.monitoring_rooms[room_id] = {"devices": {"test/error"}, "active": True, "thread": None}
    monitor = handler.DeviceMonitor()
    calls = []

    def fail_once(_device, _room):
        calls.append((_device, _room))
        raise RuntimeError("read failure")

    def stop_after_backoff(seconds):
        assert seconds == 5
        handler.monitoring_rooms[room_id]["active"] = False

    monkeypatch.setattr(monitor, "monitor_device", fail_once)
    monkeypatch.setattr(handler.time, "sleep", stop_after_backoff)
    monitor.monitoring_loop(room_id)

    assert calls == [("test/error", room_id)]


def test_subscription_lifecycle_tracks_each_client_and_stops_after_last_subscriber(handler, monkeypatch):
    FakeThread.created.clear()
    socket_emits = []
    joined = []
    left = []
    monkeypatch.setattr(handler, "SocketIO", FakeSocketIO)
    monkeypatch.setattr(handler.threading, "Thread", FakeThread)
    monkeypatch.setattr(handler, "join_room", joined.append)
    monkeypatch.setattr(handler, "leave_room", left.append)
    monkeypatch.setattr(handler, "emit", lambda event, payload: socket_emits.append((event, payload)))

    socket = handler.init_socketio(object())
    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a"))
    socket.handlers["subscribe_device"]({"device": "camera/test"})

    room_id = "device_camera/test"
    assert joined == [room_id]
    assert handler.monitoring_rooms[room_id]["devices"] == {"camera/test"}
    assert handler.device_subscriptions == {"camera/test": {"client-a"}}
    assert handler.client_subscriptions == {"client-a": {"camera/test"}}
    assert len(FakeThread.created) == 1
    assert FakeThread.created[0].started is True
    assert FakeThread.created[0].daemon is True

    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-b"))
    socket.handlers["subscribe_device"]({"device": "camera/test"})
    assert joined == [room_id, room_id]
    assert handler.device_subscriptions == {"camera/test": {"client-a", "client-b"}}
    assert handler.client_subscriptions == {
        "client-a": {"camera/test"},
        "client-b": {"camera/test"},
    }
    assert len(FakeThread.created) == 1

    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a"))
    socket.handlers["subscribe_device"]({"device": "camera/test"})
    assert joined == [room_id, room_id]
    assert len(FakeThread.created) == 1

    socket.handlers["unsubscribe_device"]({"device": "camera/test"})

    assert left == [room_id]
    assert room_id in handler.monitoring_rooms
    assert handler.device_subscriptions == {"camera/test": {"client-b"}}
    assert handler.client_subscriptions == {"client-b": {"camera/test"}}

    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-b"))
    socket.handlers["disconnect"]()

    assert room_id not in handler.monitoring_rooms
    assert handler.device_subscriptions == {}
    assert handler.client_subscriptions == {}
    assert socket_emits == [
        ("subscribed", {"device": "camera/test", "room": room_id, "status": "Monitoring started"}),
        ("subscribed", {"device": "camera/test", "room": room_id, "status": "Monitoring started"}),
        ("subscribed", {"device": "camera/test", "room": room_id, "status": "Monitoring started"}),
        ("unsubscribed", {"device": "camera/test", "status": "Monitoring stopped"}),
    ]


def test_subscription_rolls_back_when_monitor_thread_cannot_start(handler, monkeypatch):
    monkeypatch.setattr(handler.threading, "Thread", FailingThread)

    with pytest.raises(RuntimeError, match="thread start failed"):
        handler._add_subscription("client-a", "camera/test")

    assert handler.monitoring_rooms == {}
    assert handler.device_subscriptions == {}
    assert handler.client_subscriptions == {}


def test_stale_monitor_generation_exits_after_last_unsubscribe_and_resubscribe(handler, monkeypatch):
    FakeThread.created.clear()
    monkeypatch.setattr(handler.threading, "Thread", FakeThread)

    room_id, added = handler._add_subscription("client-a", "camera/test")
    assert added is True
    old_generation = handler.monitoring_rooms[room_id]["generation"]

    handler._remove_subscription("client-a", "camera/test")
    _, added = handler._add_subscription("client-b", "camera/test")
    new_generation = handler.monitoring_rooms[room_id]["generation"]
    assert new_generation != old_generation

    monitor = handler.DeviceMonitor()
    monkeypatch.setattr(
        monitor,
        "monitor_device",
        lambda *_args: pytest.fail("stale monitor must not read the recreated room"),
    )
    monkeypatch.setattr(
        handler.time,
        "sleep",
        lambda _seconds: pytest.fail("stale monitor must exit before sleeping"),
    )

    monitor.monitoring_loop(room_id, old_generation)


def test_socketio_uses_application_cors_configuration(handler, monkeypatch):
    monkeypatch.setattr(handler, "SocketIO", FakeSocketIO)
    app = SimpleNamespace(config={"PYCONLYSE_CORS_ORIGINS": ["https://ui.example.test"]})

    socket = handler.init_socketio(app)

    assert socket.options["cors_allowed_origins"] == ["https://ui.example.test"]


def test_socketio_uses_same_origin_checks_without_configured_cors_origins(handler, monkeypatch):
    monkeypatch.setattr(handler, "SocketIO", FakeSocketIO)

    socket = handler.init_socketio(SimpleNamespace(config={"PYCONLYSE_CORS_ORIGINS": []}))

    assert socket.options["cors_allowed_origins"] is None


def test_device_alert_broadcasts_once_to_shared_device_room(handler, monkeypatch):
    fake_socket = FakeSocket()
    handler.socketio = fake_socket
    handler.device_subscriptions["camera/test"] = {"client-a", "client-b"}
    monkeypatch.setattr(handler, "datetime", SimpleNamespace(now=lambda: SimpleNamespace(isoformat=lambda: "now")))

    handler.broadcast_device_alert("camera/test", "warning", "temperature high")

    assert fake_socket.emitted == [
        (
            "device_alert",
            {
                "device": "camera/test",
                "alert_type": "warning",
                "message": "temperature high",
                "timestamp": "now",
            },
            "device_camera/test",
        )
    ]


def test_execute_command_rechecks_cookie_auth_before_accessing_device(handler, monkeypatch):
    socket_emits = []
    socket = handler.init_socketio(object())
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a", cookies={"access_token_cookie": "expired"}))
    monkeypatch.setattr(
        handler,
        "decode_token",
        lambda _token: (_ for _ in ()).throw(ValueError("expired cookie")),
    )
    monkeypatch.setattr(
        handler.monitor,
        "get_device",
        lambda _device: pytest.fail("device access must require cookie auth"),
    )
    monkeypatch.setattr(handler, "emit", lambda event, payload: socket_emits.append((event, payload)))

    socket.handlers["execute_command"]({
        "device": "camera/test", "command": "State",
        "approval_nonce": "a" * 64, "role": "admin", "subject": "mallory",
    })

    assert socket_emits == [
        (
            "command_error",
            {
                "device": "camera/test",
                "command": "State",
                "error": "Authentication required",
                "success": False,
                "code": "hardware_authentication_required",
                "status": 401,
            },
        )
    ]


def test_execute_command_rejects_client_identity_and_legacy_nonce(handler, monkeypatch):
    socket = handler.init_socketio(object())
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a", cookies={}))
    monkeypatch.setattr(handler.monitor, "get_device", lambda _device: pytest.fail("device access must be denied"))
    emitted = []
    monkeypatch.setattr(handler, "emit", lambda event, payload: emitted.append((event, payload)))
    socket.handlers["execute_command"]({
        "device": "camera/test", "command": "State", "nonce": "a" * 64,
        "subject": "mallory", "role": "admin",
    })
    assert emitted[-1][0] == "command_error"
    assert emitted[-1][1]["status"] == 401
    assert emitted[-1][1]["code"] == "hardware_authentication_required"


def test_execute_command_authenticates_before_envelope_validation(handler, monkeypatch):
    socket = handler.init_socketio(object())
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setattr(handler, "request", SimpleNamespace(sid="client-a", cookies={}))
    emitted = []
    monkeypatch.setattr(handler, "emit", lambda event, payload: emitted.append((event, payload)))
    socket.handlers["execute_command"]({"approval_nonce": "a" * 64})
    assert emitted[-1][0] == "command_error"
    assert emitted[-1][1]["status"] == 401
    assert emitted[-1][1]["code"] == "hardware_authentication_required"
