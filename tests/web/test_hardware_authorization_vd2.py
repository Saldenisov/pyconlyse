"""Isolation tests for VD2 mutation authorization.

These routes are intentionally tested with the Tango module stubbed before the
blueprint is imported. A denial must occur before a proxy, worker thread, or
experiment helper is reached.
"""

import sys
from pathlib import Path

import pytest
from flask import Flask, jsonify

from tests._tango_stub import install_tango_stub


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class _CollectionMonkeyPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(_CollectionMonkeyPatch())

import pump_probe_vd2_api as vd2


@pytest.fixture(autouse=True)
def _local_authorization_environment(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)


def _client():
    app = Flask(__name__)
    app.register_blueprint(vd2.pump_probe_vd2_api)
    return app.test_client()


def _deny(monkeypatch, calls):
    def guard(**kwargs):
        calls.append(kwargs)
        return jsonify({"success": False, "code": "hardware_approval_required"}), 428

    monkeypatch.setattr(vd2, "require_http_hardware", guard)


def test_protocol_denial_precedes_worker_and_binds_canonical_his_path(monkeypatch):
    calls = []
    _deny(monkeypatch, calls)
    monkeypatch.setattr(vd2._measurement_protocol, "start", lambda **_: (_ for _ in ()).throw(AssertionError("worker must not start")))

    response = _client().post(
        "/api/pump-probe-vd2/protocol/start",
        json={
            "phase": "brew",
            "frames_per_his": "4",
            "output_root": r"E:\DATA_VD2",
            "run_name": "run_1",
        },
    )

    assert response.status_code == 428
    assert calls == [{
        "action": "start",
        "targets": [
            {"device": vd2.STREAK_DEVICE, "command": "write_attribute:sequence_loops"},
            {"device": vd2.STREAK_DEVICE, "command": "StartSequence"},
            {"device": vd2.STREAK_DEVICE, "command": "WaitForIdle"},
            {"device": vd2.STREAK_DEVICE, "command": "SaveCurrentSequence"},
        ],
        "args": {
            "phase": "BRUIT",
            "frames_per_his": 4,
            "output_root": r"E:\DATA_VD2",
            "run_name": "run_1",
            "his_path": r"E:\DATA_VD2\run_1\BRUIT.his",
            "sequence_loops": "4",
        },
        "route_id": "vd2.protocol.start",
        "wrapper_fields": {"phase", "frames_per_his", "output_root", "run_name"},
    }]


def test_initialize_and_deinitialize_denial_precedes_experiment_helpers(monkeypatch):
    calls = []
    _deny(monkeypatch, calls)
    monkeypatch.setattr(vd2, "_initialize_experiment", lambda: (_ for _ in ()).throw(AssertionError("initialize must not run")))
    monkeypatch.setattr(vd2, "_deinitialize_experiment", lambda: (_ for _ in ()).throw(AssertionError("deinitialize must not run")))

    client = _client()
    assert client.post("/api/pump-probe-vd2/initialize").status_code == 428
    assert client.post("/api/pump-probe-vd2/deinitialize").status_code == 428

    assert [call["action"] for call in calls] == ["initialize", "deinitialize"]
    initialize_targets = calls[0]["targets"]
    assert {target["command"] for target in initialize_targets} >= {
        "recover", "DevStop", "DevStart", "set_channels_states",
        "PrepareDG645ForHPDTA", "StartRemoteEx", "StartApplication",
    }
    assert calls[0]["args"]["servers"] == vd2._server_arguments()
    assert calls[0]["wrapper_fields"] == set()
    deinitialize_targets = calls[1]["targets"]
    assert {target["command"] for target in deinitialize_targets} >= {
        "StopAcquisition", "write_attribute:streak_shutter",
        "write_attribute:spectrograph_shutter", "StopApplication", "StopRemoteEx",
        "recover", "DevStop", "DevStart", "set_channels_states",
    }


def test_runtime_parameter_and_command_denial_precedes_proxy(monkeypatch):
    calls = []
    _deny(monkeypatch, calls)
    monkeypatch.setattr(vd2, "_proxy", lambda: (_ for _ in ()).throw(AssertionError("proxy must not be constructed")))

    client = _client()
    assert client.post("/api/pump-probe-vd2/runtime/remoteex/start").status_code == 428
    assert client.post("/api/pump-probe-vd2/parameter/wavelength_nm", json={"value": "532.5"}).status_code == 428
    assert client.post("/api/pump-probe-vd2/parameter/mcp_gain", json={"value": "17"}).status_code == 428
    assert client.post("/api/pump-probe-vd2/command/StartLive").status_code == 428

    assert calls[0]["targets"] == [{"device": vd2.STREAK_DEVICE, "command": "StartRemoteEx"}]
    assert calls[0]["route_id"] == "vd2.remoteex"
    assert calls[1]["args"] == {"name": "wavelength_nm", "value": 532.5}
    assert calls[1]["wrapper_fields"] == {"value"}
    assert calls[1]["action"] == "parameter.wavelength_nm.write"
    assert calls[1]["targets"] == [{"device": vd2.STREAK_DEVICE, "command": "write_attribute:wavelength_nm"}]
    assert calls[2]["action"] == "parameter.mcp_gain.write"
    assert calls[2]["targets"] == [{"device": vd2.STREAK_DEVICE, "command": "SetMCPGain"}]
    assert calls[3]["action"] == "command.StartLive.execute"
    assert calls[3]["wrapper_fields"] == set()
    assert calls[3]["targets"] == [{"device": vd2.STREAK_DEVICE, "command": "StartLive"}]


def test_local_opt_out_keeps_parameter_and_command_behavior(monkeypatch):
    class Proxy:
        def __init__(self):
            self.writes = []
            self.commands = []

        def write_attribute(self, name, value):
            self.writes.append((name, value))

        def command_inout(self, name, value=None):
            self.commands.append((name, value))

        def read_attribute(self, name):
            return type("Attribute", (), {"value": True})()

        def state(self):
            return "ON"

    proxy = Proxy()
    monkeypatch.setattr(vd2, "require_http_hardware", lambda **_: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)

    client = _client()
    assert client.post("/api/pump-probe-vd2/parameter/wavelength_nm", json={"value": "532.5"}).status_code == 200
    assert client.post("/api/pump-probe-vd2/command/StartLive").status_code == 200
    assert proxy.writes == [("wavelength_nm", 532.5)]
    assert proxy.commands == [("StartLive", None)]


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/pump-probe-vd2/protocol/start", "[]"),
        ("/api/pump-probe-vd2/initialize", '{"client_role":"operator"}'),
        ("/api/pump-probe-vd2/deinitialize", '{"subject":"user"}'),
        ("/api/pump-probe-vd2/runtime/remoteex/start", '{"role":"operator"}'),
        ("/api/pump-probe-vd2/parameter/wavelength_nm", "{}"),
        ("/api/pump-probe-vd2/parameter/wavelength_nm", '{"value":NaN}'),
        ("/api/pump-probe-vd2/command/StartLive", '{"x":1,"x":2}'),
    ],
)
def test_strict_envelopes_reject_untrusted_or_ambiguous_json_before_guard_or_proxy(monkeypatch, path, body):
    calls = []
    monkeypatch.setattr(vd2, "authorization_required", lambda: True)
    monkeypatch.setattr(vd2, "require_http_hardware", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(vd2, "_proxy", lambda: (_ for _ in ()).throw(AssertionError("proxy must not be constructed")))
    monkeypatch.setattr(vd2, "_initialize_experiment", lambda: (_ for _ in ()).throw(AssertionError("initialize must not run")))
    monkeypatch.setattr(vd2, "_deinitialize_experiment", lambda: (_ for _ in ()).throw(AssertionError("deinitialize must not run")))
    monkeypatch.setattr(vd2._measurement_protocol, "start", lambda **_: (_ for _ in ()).throw(AssertionError("worker must not start")))

    response = _client().post(path, data=body, content_type="application/json")

    assert response.status_code == 409
    assert response.get_json()["code"] == "hardware_approval_invalid"
    assert calls == []


@pytest.fixture
def _enforced_client(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    # Patch the registered callback itself. Importing ``mutation_auth`` can
    # resolve a package duplicate rather than the module whose globals the
    # already-registered Blueprint callback closes over.
    legacy_guard = next(
        guard
        for guard in vd2.pump_probe_vd2_api.before_request_funcs.get(None, ())
        if guard.__name__ == "require_mutation_authentication"
    )
    monkeypatch.setitem(legacy_guard.__globals__, "mutation_auth_required", lambda: False)
    return _client()


@pytest.mark.parametrize(
    "path, helper_name",
    [
        ("/api/pump-probe-vd2/initialize", "_initialize_experiment"),
        ("/api/pump-probe-vd2/deinitialize", "_deinitialize_experiment"),
    ],
)
def test_enforced_lifecycle_requires_exact_plan_before_guard_or_helper(_enforced_client, monkeypatch, path, helper_name):
    monkeypatch.setattr(vd2, "require_http_hardware", lambda **_: (_ for _ in ()).throw(AssertionError("approval guard must not run")))
    monkeypatch.setattr(vd2, helper_name, lambda: (_ for _ in ()).throw(AssertionError("workflow helper must not run")))
    monkeypatch.setattr(vd2, "_initialize_authorization", lambda: (_ for _ in ()).throw(AssertionError("plan helper must not run")))
    monkeypatch.setattr(vd2, "_deinitialize_authorization", lambda: (_ for _ in ()).throw(AssertionError("plan helper must not run")))

    response = _enforced_client.post(path, json={})

    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "This workflow requires an exact precomputed hardware plan",
        "code": "hardware_not_authorized",
    }
