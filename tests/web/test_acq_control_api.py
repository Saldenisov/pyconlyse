"""All Tango and network boundaries are fake; no live equipment commands."""
import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("acq_control_api")
ROOT = "/api/elyse/acquisition/control"


def request_command(**changes):
    value = dict(command_id="b" * 32, session_id="a" * 32, expected_revision=7,
                 operation="modulator.general.start", operator_confirmed=True, value=None)
    value.update(changes)
    return value


def view_fixture():
    return dict(source="xp_python_acquisition_control", bridge_age_seconds=.1, bridge_error="",
                quality="FRESH", commands_enabled=True, source_current=True,
                runtime=dict(server_variant="acquisition_control_vnext", runtime_protocol_version=2,
                    control_policy_version=2,
                    auto_initialize=False, remote_initialization_enabled=False, remote_setpoints_enabled=True,
                    state="RUNNING", session_id="a" * 32, build_id="d" * 64, state_revision=7,
                    startup_phase="NOT_STARTED", age_seconds=.1,
                    control=dict(protocol_version=1, enabled=True, lease="do-not-disclose",
                        capabilities={name: dict(enabled=name != "cooling.stop", reason="" if name != "cooling.stop" else "COOLDOWN")
                                      for name in api.OPERATIONS}, results=[]),
                    latest=dict(source="python_daqmx_acquisition", simulated=False,
                        banks={"C1_NI6071E_AI": dict(values=[1.] * 64, legacy_scaled_values=[123.] * 64),
                               "C3_DIO96_DI": dict(values=[False] * 56)})))


@pytest.fixture
def setup_api(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-ACQ-command-secret-0000000000",
                      ELYSE_CONTROL_STATE_DB=str(tmp_path / "commands.sqlite3"), ELYSE_ACQUISITION_SOURCE="xp_control")
    JWTManager(app)
    app.register_blueprint(api.api)
    with app.app_context():
        token = create_access_token(identity="operator-test")
    view, calls = view_fixture(), []
    class Proxy:
        fail = False
        def set_timeout_millis(self, timeout): pass
        def read_attribute(self, name):
            calls.append(("read", name))
            return SimpleNamespace(has_failed=False, value=json.dumps(view))
        def command_inout(self, name, body):
            calls.append(("command", name, json.loads(body)))
            if self.fail: raise TimeoutError("test-only lost reply")
            command = json.loads(body)
            return json.dumps(dict(command_id=command["command_id"], session_id=command["session_id"],
                operation=command["operation"], outcome="QUEUED", hardware_acknowledged=False))
    proxy = Proxy()
    def factory(device):
        assert device == api.DEVICE
        return proxy
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    return app, app.test_client(), {"Authorization": "Bearer " + token}, view, calls, proxy


def post(setup, command=None, auth=True):
    app, client, headers, view, calls, proxy = setup
    return client.post(ROOT + "/commands", json=command or request_command(), headers=headers if auth else {})


def writes(setup):
    return [call for call in setup[4] if call[0] == "command"]


def test_get_redacts_leases_and_never_sends_commands(setup_api):
    response = setup_api[1].get(ROOT)
    assert response.status_code == 200
    assert response.json["execution_allowed"] is True
    assert "lease" not in response.text
    assert writes(setup_api) == []


def test_live_commands_require_auth_even_in_development(setup_api):
    assert post(setup_api, auth=False).status_code == 401
    assert writes(setup_api) == []
    assert setup_api[4] == []


def test_labview_mode_from_same_device_cannot_authorize_commands(setup_api):
    setup_api[3].clear()
    setup_api[3].update(source="labview_receive_only", commands_enabled=False)
    result = setup_api[1].get(ROOT)
    assert result.status_code == 200
    assert result.json["source_selected"] is False
    assert result.json["execution_allowed"] is False
    assert setup_api[4] == [("read", "runtime_json")]


def test_exact_named_command_and_durable_duplicate_dispatch_once(setup_api):
    first, second = post(setup_api), post(setup_api)
    assert first.status_code == second.status_code == 200
    assert first.json["receipt"]["outcome"] == "QUEUED"
    assert second.json["duplicate"] is True
    assert writes(setup_api) == [("command", "ExecuteCommand", request_command())]
    assert post(setup_api, request_command(operation="prema.start")).status_code == 409
    assert len(writes(setup_api)) == 1


@pytest.mark.parametrize("changes", [dict(operator_confirmed=False), dict(operation="raw.write"),
                                    dict(expected_revision=True), dict(value=1), dict(channel=3)])
def test_malformed_commands_never_reach_tango(setup_api, changes):
    assert post(setup_api, request_command(**changes)).status_code == 400
    assert writes(setup_api) == []


@pytest.mark.parametrize("change", ["source", "session", "revision", "disabled", "stale", "legacy"])
def test_changed_or_unavailable_source_blocks_dispatch(setup_api, change):
    app, client, headers, view, calls, proxy = setup_api
    if change == "source": view["source"] = "labview_receive_only"
    if change == "session": view["runtime"]["session_id"] = "c" * 32
    if change == "revision": view["runtime"]["state_revision"] = 8
    if change == "disabled": view["commands_enabled"] = False
    if change == "stale": view["bridge_age_seconds"] = 2
    if change == "legacy": view["source"] = "copied_labview_telemetry"
    assert post(setup_api).status_code == 409
    assert writes(setup_api) == []


def test_unknown_dispatch_is_not_retried_and_survives_new_browser(setup_api):
    setup_api[5].fail = True
    assert post(setup_api).json["receipt"]["outcome"] == "INDETERMINATE"
    assert post(setup_api).json["duplicate"] is True
    assert len(writes(setup_api)) == 1
    assert post(setup_api, request_command(command_id="e" * 32)).status_code == 409
    value = setup_api[0].test_client().get(ROOT).json
    assert value["commands"][0]["outcome"] == "INDETERMINATE"
    assert not value["capabilities"]["chauffage.start"]["enabled"]
    assert value["capabilities"]["modulator.general.stop"]["enabled"]


def test_receipt_changes_only_from_matching_xp_result(setup_api):
    post(setup_api)
    result = dict(request_command(), outcome="COMPLETED", hardware_acknowledged=False)
    setup_api[3]["runtime"]["control"]["results"] = [dict(result, operation="prema.start")]
    assert setup_api[1].get(ROOT).json["commands"][0]["outcome"] == "QUEUED"
    setup_api[3]["runtime"]["control"]["results"] = [result]
    value = setup_api[1].get(ROOT).json["commands"][0]
    assert value["outcome"] == "COMPLETED"
    assert value["hardware_acknowledged"] is False


def test_control_and_telemetry_use_same_device_without_second_projection(setup_api):
    assert api.DEVICE == "tango://10.20.30.202:10000/elyse/acquisition/telemetry"
    assert setup_api[1].get(ROOT).status_code == 200
    assert setup_api[4] == [("read", "runtime_json")]


def test_selected_python_telemetry_never_falls_back_to_labview(setup_api, monkeypatch):
    telemetry = importlib.import_module("acq_telemetry_api")
    setup_api[0].register_blueprint(telemetry.acq_telemetry_api)
    calls = []
    def unavailable(device):
        calls.append(device)
        raise RuntimeError("test missing Python facade")
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", unavailable)
    response = setup_api[1].get("/api/elyse/acquisition/telemetry")
    assert response.status_code == 503
    assert calls == [api.DEVICE]
