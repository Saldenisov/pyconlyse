"""Imported-axis contracts; software only, without device calls."""

import copy
import sys
from pathlib import Path

import pytest
from flask import Flask

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pump_probe_v0_api as v0_api
from pump_probe_v0_delays import resolve_scan_settings


DEFAULTS = {
    "point_count": 3, "scan_start_ps": 0.0, "delay_step_ps": 2.0,
    "scan_span_ps": 4.0, "pulses_per_point": 10, "real_zero_ps": 465.0,
    "delay_points_ps": None,
}


@pytest.fixture
def config_client(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "0")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "0")
    monkeypatch.setattr(v0_api, "authorization_required", lambda: False)
    monkeypatch.setattr(v0_api, "_tango_proxy", lambda *args, **kwargs: pytest.fail("Unexpected device call"))
    controller = v0_api.PumpProbeV0Controller()
    monkeypatch.setattr(v0_api, "_emulator", controller)
    app = Flask(__name__)
    app.register_blueprint(v0_api.pump_probe_v0_api)
    with app.test_client() as client:
        yield client, controller


@pytest.mark.parametrize("axis", [[0, 2, 9], [3, -1, -1, 2], [9, 2, 0], [0, 0]])
def test_react_payload_preserves_explicit_order_and_duplicates(config_client, axis):
    client, _ = config_client
    # settingsToApi supplies all scalar axis fields along with custom delays.
    payload = {
        "point_count": len(axis), "scan_start_ps": axis[0],
        "delay_step_ps": axis[1] - axis[0], "scan_span_ps": axis[-1] - axis[0],
        "pulses_per_point": 10, "real_zero_ps": 465,
        "delay_points_ps": axis, "hardware_config": {"control_mode": "emulator"},
    }
    response = client.post("/api/pump-probe-v0/config", json=payload)
    assert response.status_code == 200
    state = response.get_json()
    assert state["delays"] == axis
    assert state["settings"]["delay_points_ps"] == axis
    assert state["settings"]["point_count"] == len(axis)
    assert state["settings"]["scan_span_ps"] == axis[-1] - axis[0]


@pytest.mark.parametrize("payload", [
    {"delay_points_ps": None}, {"delay_points_ps": []},
    {"point_count": 3}, {"scan_start_ps": 1}, {"delay_step_ps": -2},
])
def test_generated_mode_is_selected_explicitly(payload):
    custom = resolve_scan_settings(DEFAULTS, {"delay_points_ps": [0, 2, 9]})
    updated = resolve_scan_settings(custom, payload)
    assert updated["delay_points_ps"] is None
    assert updated["scan_span_ps"] == (updated["point_count"] - 1) * updated["delay_step_ps"]
    assert custom["delay_points_ps"] == [0, 2, 9]


@pytest.mark.parametrize("payload", [
    {"pulses_per_point": 3}, {"real_zero_ps": 42},
    {"hardware_config": {"control_mode": "emulator"}}, {},
])
def test_unrelated_partial_update_keeps_custom_axis(payload):
    custom = resolve_scan_settings(DEFAULTS, {"delay_points_ps": [0, 2, 9]})
    updated = resolve_scan_settings(custom, payload)
    assert updated["delay_points_ps"] == [0, 2, 9]
    assert updated["delay_points_ps"] is not custom["delay_points_ps"]


def test_explicit_axis_overrides_conflicting_auxiliary_fields():
    updated = resolve_scan_settings(DEFAULTS, {
        "delay_points_ps": [0, 2, 9], "point_count": 999,
        "scan_start_ps": -20, "delay_step_ps": 500, "scan_span_ps": 999,
    })
    assert [updated[key] for key in ("point_count", "scan_start_ps", "delay_step_ps", "scan_span_ps")] == [3, 0, 2, 9]


@pytest.mark.parametrize("payload", [
    {"delay_points_ps": [0]}, {"delay_points_ps": list(range(401))},
    {"delay_points_ps": "0,2,9"}, {"delay_points_ps": True},
    {"delay_points_ps": [0, True]}, {"delay_points_ps": [0, "2"]},
    {"delay_points_ps": [0, float("nan")]},
    {"delay_points_ps": [0, float("inf")]},
    {"delay_points_ps": [-1e308, 1e308]},
    {"point_count": 2.5}, {"point_count": True},
    {"pulses_per_point": 1.5}, {"real_zero_ps": float("nan")},
    {"scan_start_ps": 1e308, "delay_step_ps": 1e308},
    {"scan_span_ps": float("inf")},
    {"delay_points_ps": [-1e6, -999999]},
    {"delay_points_ps": [0, 1e308], "real_zero_ps": 1e308},
])
def test_rejected_candidate_does_not_modify_settings(payload):
    settings = copy.deepcopy(DEFAULTS)
    before = copy.deepcopy(settings)
    with pytest.raises(ValueError):
        resolve_scan_settings(settings, payload)
    assert settings == before


@pytest.mark.parametrize("count", [2, 400])
def test_explicit_axis_limit_is_inclusive(count):
    assert resolve_scan_settings(DEFAULTS, {"delay_points_ps": list(range(count))})["point_count"] == count


@pytest.mark.parametrize("endpoint", ["/config", "/hardware-config"])
def test_invalid_config_returns_json_error_before_hardware_or_reset(config_client, endpoint):
    client, controller = config_client
    before = copy.deepcopy((controller._settings, controller._hardware_config, controller._delays, controller._heatmap))
    response = client.post(f"/api/pump-probe-v0{endpoint}", json={
        "delay_points_ps": [0, True], "hardware_config": {"control_mode": "tango"},
    })
    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert "finite number" in response.get_json()["error"]
    assert (controller._settings, controller._hardware_config, controller._delays, controller._heatmap) == before


def test_active_writer_rejects_config_before_advancing_run(config_client, monkeypatch):
    client, controller = config_client
    controller._running = True
    controller._run_writer = object()
    monkeypatch.setattr(controller, "_sync_locked", lambda: pytest.fail("Run advanced during rejected config"))
    response = client.post("/api/pump-probe-v0/config", json={"delay_points_ps": [0, 2, 9]})
    assert response.status_code == 400
    assert "Stop the active run" in response.get_json()["error"]
    assert controller._settings["delay_points_ps"] is None


def test_generated_zero_and_negative_steps_are_preserved():
    zero = resolve_scan_settings(DEFAULTS, {"delay_step_ps": 0})
    negative = resolve_scan_settings(DEFAULTS, {"delay_step_ps": -2})
    assert zero["scan_span_ps"] == 0
    assert negative["scan_span_ps"] == -4


@pytest.mark.parametrize("endpoint", ["/config", "/hardware-config"])
@pytest.mark.parametrize("body", ['{bad json', 'null', 'false', '0', '[]', '[0,2,9]', '"text"'])
def test_config_routes_reject_nonobject_json_without_reset(config_client, endpoint, body):
    client, controller = config_client
    before = copy.deepcopy((controller._settings, controller._hardware_config, controller._delays, controller._heatmap))
    response = client.post(f"/api/pump-probe-v0{endpoint}", data=body, content_type="application/json")
    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]
    assert (controller._settings, controller._hardware_config, controller._delays, controller._heatmap) == before


@pytest.mark.parametrize("payload", [
    {"delay_points_ps": [-1e6, -999999]},
    {"point_count": 2, "scan_start_ps": -1e6, "delay_step_ps": 1},
])
def test_preview_overflow_is_rejected_before_committing_config(config_client, payload):
    client, controller = config_client
    before = copy.deepcopy((controller._settings, controller._hardware_config, controller._delays, controller._heatmap))
    response = client.post("/api/pump-probe-v0/config", json=payload)
    assert response.status_code == 400
    assert "numeric range" in response.get_json()["error"]
    assert (controller._settings, controller._hardware_config, controller._delays, controller._heatmap) == before
