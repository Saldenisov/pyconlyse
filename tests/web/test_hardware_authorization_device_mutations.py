"""T11-B3 device_api mutation inventory; no Tango or network access."""

import importlib
import sys
import types
from pathlib import Path

import pytest
from flask import Flask, jsonify


BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"


MUTATIONS = [
    ("/api/device/itest/test/slot/1/output", {"state": 1}, "itest.output"),
    ("/api/device/ds_itest_psu/test/slot/1/current", {"current": 1.0}, "itest.current"),
    ("/api/device/ds_itest_psu/test/slot/1/state", {"enabled": True}, "itest.state"),
    ("/api/device/itest/test/current", {"action": "set", "value": 1.0}, "itest.current"),
    ("/api/device/itest/test/current", {"action": "inc_fine"}, "itest.current"),
    ("/api/device/itest/test/current", {"action": "dec_fine"}, "itest.current"),
    ("/api/device/itest/test/current", {"action": "inc_coarse"}, "itest.current"),
    ("/api/device/itest/test/current", {"action": "dec_coarse"}, "itest.current"),
    ("/api/device/itest/test/slot/1/current", {"action": "set", "value": 1.0}, "itest.slot_current"),
    ("/api/device/itest/test/slot/1/current", {"action": "inc_fine"}, "itest.slot_current"),
    ("/api/device/itest/test/slot/1/current", {"action": "dec_fine"}, "itest.slot_current"),
    ("/api/device/itest/test/slot/1/current", {"action": "inc_coarse"}, "itest.slot_current"),
    ("/api/device/itest/test/slot/1/current", {"action": "dec_coarse"}, "itest.slot_current"),
    ("/api/device/camera/test/capture", {}, "camera.capture"),
    ("/api/device/camera/test/parameters", {"exposure_time": 1.0}, "camera.parameters"),
    ("/api/camera/test/grabbing", {"action": "start"}, "camera.grabbing"),
    ("/api/camera/test/grabbing", {"action": "stop"}, "camera.grabbing"),
    ("/api/camera/test/trigger", {}, "camera.trigger"),
    ("/api/psp/device/test/commands/ack", {"command": "ack"}, "psp.ack"),
    ("/api/daqmx/device/test/write", {"channel": "x", "value": 1}, "daqmx.write"),
    ("/api/spectrograph/test/parameters", {"wavelength_nm": 500}, "spectrograph.parameters"),
]


@pytest.fixture
def device_client(monkeypatch):
    from tests._tango_stub import install_tango_stub
    install_tango_stub(monkeypatch)
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    monkeypatch.syspath_prepend(str(BACKEND))
    monitor_calls = []
    fake_ws = types.ModuleType("websocket_handler")
    fake_ws.monitor = types.SimpleNamespace(
        monitor_device=lambda *args: monitor_calls.append(args),
    )
    monkeypatch.setitem(sys.modules, "websocket_handler", fake_ws)
    sys.modules.pop("device_api", None)
    module = importlib.import_module("device_api")
    import mutation_auth
    # Bypass only legacy JWT preprocessing; route guard remains under test.
    monkeypatch.setattr(mutation_auth, "mutation_auth_required", lambda: False)
    monkeypatch.setattr(module, "_maybe_require_auth", lambda: None)
    app = Flask(__name__)
    app.config["TESTING"] = True
    calls = []
    effects = []

    def guard(**kwargs):
        calls.append(kwargs)
        return jsonify({"success": False, "code": "hardware_approval_required"}), 428

    monkeypatch.setattr(module, "require_http_hardware", guard, raising=False)
    monkeypatch.setattr(module.DeviceManager, "get_device", lambda *_a, **_k: effects.append("get_device"), raising=False)
    monkeypatch.setattr(module, "_resolve_server_name", lambda *_a, **_k: effects.append("resolve"), raising=False)
    app.register_blueprint(module.device_api)
    client = app.test_client()
    client.gate_calls = calls
    client.effects = effects
    client.monitor_calls = monitor_calls
    client.module = module
    return client


@pytest.mark.parametrize("path,payload,route_id", MUTATIONS)
def test_every_device_mutation_is_guarded_before_tango(device_client, path, payload, route_id):
    response = device_client.post(path, json=payload)
    assert response.status_code == 428
    assert device_client.gate_calls
    call = device_client.gate_calls[-1]
    assert call["route_id"] == route_id
    assert call["action"]
    assert call["targets"]
    assert "args" in call
    assert device_client.effects == []


@pytest.mark.parametrize("path,payload", [
    ("/api/device/itest/test/current", {"action": "invalid"}),
    ("/api/camera/test/grabbing", {"action": "invalid"}),
    ("/api/device/itest/test/slot/1/output", {}),
    ("/api/daqmx/device/test/write", {"value": 1}),
])
def test_invalid_mutation_input_does_not_reach_proxy(device_client, path, payload):
    response = device_client.post(path, json=payload)
    assert response.status_code == 400
    assert device_client.gate_calls == []
    assert device_client.effects == []


def test_pending_pop_get_is_not_a_hidden_mutation(device_client):
    response = device_client.get("/api/psp/device/test/commands/pending?pop=1")
    assert response.status_code == 400
    assert device_client.gate_calls == []
    assert device_client.effects == []


@pytest.mark.parametrize("path,payload,expected", [
    ("/api/daqmx/device/test/write", {"channel": "x", "value": 1}, "daqmx.write"),
    ("/api/device/camera/test/capture", {"exposure_time": 0.1}, "camera.capture"),
    ("/api/camera/test/grabbing", {"action": "start"}, "camera.grabbing"),
    ("/api/camera/test/grabbing", {"action": "stop"}, "camera.grabbing"),
    ("/api/camera/test/trigger", {}, "camera.trigger"),
    ("/api/server/control", {"action": "restart", "server_name": "DS/test"}, "server.control"),
    ("/api/camera/test/parameters", {"gain": 2, "exposure_time": 0.1}, "camera.parameters"),
])
def test_exact_guard_route_branch_and_ordered_target(device_client, path, payload, expected):
    response = device_client.post(path, json=payload)
    assert response.status_code == 428
    call = device_client.gate_calls[-1]
    assert call["route_id"] == expected
    assert isinstance(call["targets"], (list, tuple))
    assert all(tuple(target) == ("device", "command") for target in call["targets"])
    assert device_client.effects == []


def test_debug_monitor_get_is_read_only_and_post_is_mutation_contract(device_client):
    read = device_client.get("/api/debug/monitor/test")
    assert read.status_code == 200
    assert device_client.effects == []
    assert device_client.monitor_calls == []
    write = device_client.post("/api/debug/monitor/test", json={})
    assert write.status_code == 200
    assert len(device_client.monitor_calls) == 1


def test_server_start_and_restart_have_exact_starter_command_order(device_client, monkeypatch):
    module = device_client.module
    monkeypatch.setattr(module, "require_http_hardware", lambda **_kwargs: None, raising=False)

    class Starter:
        def __init__(self):
            self.calls = []

        def command_inout(self, command, argument=None):
            self.calls.append((command, argument))
            return []

    starter = Starter()
    monkeypatch.setattr(module, "_find_starter_for_server", lambda _name: (
        "tango/admin/test", starter, {"DS/test"}, set()
    ))
    monkeypatch.setattr(module, "_get_starter_server_lists", lambda _name: (
        starter, {"DS/test"}, set()
    ))
    monkeypatch.setattr(module, "_wait_for_starter_server", lambda *_args: ({"DS/test"}, set()))
    monkeypatch.setattr(module, "_schedule_device_list_refresh", lambda *_args: None)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    start = device_client.post("/api/server/control", json={"action": "start", "server_name": "DS/test"})
    assert start.status_code == 200
    assert [name for name, _arg in starter.calls] == ["DevStart"]
    starter.calls.clear()

    monkeypatch.setattr(module, "_find_starter_for_server", lambda _name: (
        "tango/admin/test", starter, set(), {"DS/test"}
    ))
    restart = device_client.post("/api/server/control", json={"action": "restart", "server_name": "DS/test"})
    assert restart.status_code == 200
    assert [name for name, _arg in starter.calls] == ["DevStop", "DevStart"]
    assert all(name != "HardKillServer" for name, _arg in starter.calls)
