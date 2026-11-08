"""VD2 uses IP axis 2; an unrelated USB axis cannot gate or receive its commands."""
from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from tests.web.test_vd2_prepare_idempotence import ready_rig as ready_rig


def test_prepare_plan_excludes_usb_backend_and_shared_router():
    targets, arguments = api._initialize_authorization()
    excluded = {api.OWIS_LEGACY_DEVICE, "manip/general/DS_OWIS_Aggregator"}
    assert api.OWIS_SAMPLE_DEVICE == api.OWIS_CONTROLLER_DEVICE == "manip/general/DS_OWIS_PS90_IP"
    assert not excluded.intersection(arguments["servers"])
    assert not excluded.intersection(item["device"] for item in arguments["recovery_plan"])
    assert not excluded.intersection(item["device"] for item in targets)
    assert {"device": api.OWIS_SAMPLE_DEVICE, "command": "turn_on_axis"} in targets
    shutdown_targets, _ = api._deinitialize_authorization()
    assert {"device": api.OWIS_SAMPLE_DEVICE, "command": "stop_axis"} in shutdown_targets
    assert not excluded.intersection(item["device"] for item in shutdown_targets)


@pytest.mark.parametrize("legacy_state", ["FAULT", "OFF", "STANDBY"])
def test_unused_axis_failure_does_not_reset_prepared_optics(request, monkeypatch, legacy_state):
    rig = request.getfixturevalue("ready_rig")
    rig.proxies[api.OWIS_LEGACY_DEVICE].current_state = legacy_state

    def proxy_for(device):
        assert device not in {api.OWIS_LEGACY_DEVICE, "manip/general/DS_OWIS_Aggregator"}
        return rig.proxies[device]

    monkeypatch.setattr(api, "DeviceProxy", proxy_for)
    with pytest.raises(api.AlreadyPrepared):
        api._initialize_experiment()
    assert not any(command in {"Init", "recover", "turn_on", "turn_on_axis", "scpi_write", "StartApplication", "StopApplication"}
                   for _device, command, _argument in rig.events)


def test_cold_prepare_does_not_start_or_activate_usb_axis_or_router(monkeypatch):
    devices = []
    axis_checks = []
    monkeypatch.setattr(api, "_prepared_equipment_state", lambda: None)
    monkeypatch.setattr(api, "_assert_preparation_idle", lambda: None)

    def ensure(device, _steps):
        assert device not in {api.OWIS_LEGACY_DEVICE, "manip/general/DS_OWIS_Aggregator"}
        devices.append(device)
        return SimpleNamespace(device=device)

    monkeypatch.setattr(api, "_ensure_server", ensure)
    monkeypatch.setattr(api, "_enable_vd2_power", lambda *_args: None)
    monkeypatch.setattr(api, "_enable_required_power", lambda *_args: None)
    monkeypatch.setattr(api, "_prepare_dg645_for_vd2", lambda *_args: None)
    monkeypatch.setattr(api, "_verify_owis_sample_axis", lambda proxy, _steps: axis_checks.append(proxy.device))
    monkeypatch.setattr(api, "_start_vd2_optics", lambda *_args: {})
    api._initialize_experiment()
    assert devices.count(api.OWIS_SAMPLE_DEVICE) == 1
    assert axis_checks == ["manip/general/DS_OWIS_PS90_IP"]


def test_stage_readings_use_direct_axis_two_and_its_limits(monkeypatch):
    reads = []

    class Proxy:
        def __init__(self, device):
            assert device in {api.OWIS_SAMPLE_DEVICE, api.ZABER_STAGE_DEVICE}
            self.device = device

        def set_timeout_millis(self, _value):
            pass

        def state(self):
            return "ON"

        def status(self):
            return "Connected"

        def command_inout(self, command, argument):
            reads.append((self.device, command, argument))
            assert (command, argument) == ("get_status_axis", 2)
            return int(api.DevState.ON)

        def read_attribute(self, name):
            return SimpleNamespace(value={"pos2": 39.0, "position_mm": 0.0, "minimum_mm": 0.0, "maximum_mm": 50.8}[name])

        def get_property(self, _names):
            return {"delay_lines_parameters": ["{2: {'limit_min': -40, 'limit_max': 260}}"]}

    monkeypatch.setattr(api, "DeviceProxy", Proxy)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    with app.test_client() as client:
        response = client.get("/api/pump-probe-vd2/stages/state")
    sample = response.get_json()["owis_sample"]
    assert sample["device"] == "manip/general/DS_OWIS_PS90_IP"
    assert sample["axis_state"] == "ON"
    assert (sample["position_mm"], sample["minimum_mm"], sample["maximum_mm"]) == (39.0, -40.0, 260.0)
    assert reads == [("manip/general/DS_OWIS_PS90_IP", "get_status_axis", 2)]
