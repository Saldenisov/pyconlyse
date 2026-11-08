import sys
import time
from pathlib import Path

import pytest
from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pump_probe_v0_api as v0_api_module
from pump_probe_v0_config import (
    REQUIRED_NETIO_OUTPUTS,
    V0_CAMERA_DEVICES,
    V0_STANDA_DEVICES,
    V0_STARTER_DEVICE,
    V0_STANDA_STARTER_DEVICE,
)


def test_v0_preparation_inventory_matches_operator_requirements():
    assert V0_STARTER_DEVICE == "tango/admin/everest"
    assert len(V0_STANDA_DEVICES) == 16
    assert V0_CAMERA_DEVICES == (
        "manip/V0/Cam1_V0",
        "manip/V0/Cam2_V0",
    )
    assert {
        (item["device"], item["output_id"])
        for item in REQUIRED_NETIO_OUTPUTS
    } == {
        ("manip/V0/PDU_VO", 2),
        ("manip/V0/PDU_VO", 3),
        ("manip/SD1/PDU_SD1", 1),
        ("manip/SD2/PDU_SD2", 2),
        ("manip/SD2/PDU_SD2", 3),
        ("manip/SD2/PDU_SD2", 4),
    }


def test_v0_stopped_daqmx_is_started_manually_on_everest(monkeypatch):
    controller = v0_api_module.PumpProbeV0Controller()
    repairs = []

    class ReadyProxy:
        @staticmethod
        def state():
            return "ON"

        @staticmethod
        def command_inout(command, argument):
            assert command == "DevGetRunningServers"
            return []

    monkeypatch.setattr(
        v0_api_module,
        "_server_name_for_device",
        lambda _device: "DS_DAQmx/TRANCON-DAQ",
    )
    monkeypatch.setattr(
        v0_api_module,
        "_restart_server_for_device",
        lambda device, preferred_starter=None: repairs.append(
            (device, preferred_starter)
        ) or {"server": "DS_DAQmx/TRANCON-DAQ", "starter": preferred_starter},
    )
    monkeypatch.setattr(v0_api_module, "_tango_proxy", lambda *_args, **_kwargs: ReadyProxy())

    result = controller._check_device(
        "DAQmx DS",
        "control/DAQ/TRANCON-DAQ",
        fix=True,
        starter_name=V0_STARTER_DEVICE,
        starter_running=set(),
    )

    assert result["ok"] is True
    assert repairs == [("control/DAQ/TRANCON-DAQ", "tango/admin/everest")]


def test_v0_fault_is_reinitialized_and_enabled_before_server_restart(monkeypatch):
    controller = v0_api_module.PumpProbeV0Controller()

    class FaultedProxy:
        current_state = "FAULT"
        commands = []

        def state(self):
            return self.current_state

        def get_command_list(self):
            return ["recover", "Init", "turn_on"]

        def command_inout(self, name):
            self.commands.append(name)
            if name == "Init":
                self.current_state = "STANDBY"
            elif name == "turn_on" and self.current_state == "STANDBY":
                self.current_state = "ON"

    proxy = FaultedProxy()
    monkeypatch.setattr(v0_api_module, "_server_name_for_device", lambda _device: "device/server")
    monkeypatch.setattr(v0_api_module, "_tango_proxy", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(v0_api_module, "_restart_server_for_device", lambda *_args, **_kwargs: pytest.fail("healthy recovery must not restart server"))

    result = controller._check_device("instrument", "test/instrument/1", fix=True)
    assert result["ok"] is True
    assert proxy.commands == ["recover", "turn_on", "Init", "turn_on"]


def test_v0_power_failure_blocks_dependent_device_and_retry_checks_again(monkeypatch):
    controller = v0_api_module.PumpProbeV0Controller()
    calls = []
    power_ready = False
    monkeypatch.setattr(controller, "_everest_server_snapshot", lambda: ({"ok": True}, set()))
    monkeypatch.setattr(controller, "_starter_server_snapshot", lambda _name: ({"ok": True}, set()))

    def check_device(label, device, **kwargs):
        assert kwargs.get("fix") is False
        if device in V0_STANDA_DEVICES:
            assert kwargs["starter_name"] == V0_STANDA_STARTER_DEVICE
        calls.append(("device", device))
        return {"ok": True, "label": label}

    def check_power(item, fix=False):
        assert fix is False
        calls.append(("power", item["key"]))
        return {"ok": power_ready or item["key"] != "dg645", "label": item["label"]}

    monkeypatch.setattr(controller, "_check_device", check_device)
    monkeypatch.setattr(controller, "_check_netio_output", check_power)
    monkeypatch.setattr(controller, "_check_owis_axes", lambda **_kwargs: [])
    monkeypatch.setattr(controller, "_check_dg645_recall", lambda **_kwargs: {"ok": True, "label": "recall"})
    monkeypatch.setattr(controller, "_check_counter_activity", lambda: {"ok": True, "label": "counter"})
    monkeypatch.setattr(controller, "_check_camera_stream", lambda *a, **kw: {"ok": True, "label": "stream"})
    monkeypatch.setattr(controller, "_check_laser_pointing", lambda *a, **kw: [])

    first = controller._v0_preparation_checks(fix=False)
    assert any(check.get("blocked") and check["label"] == "DG645 Tango server" for check in first)
    assert ("device", controller._hardware_config["dg645_device"]) not in calls
    assert ("device", controller._hardware_config["spectrograph_device"]) not in calls
    assert ("device", controller._hardware_config["andor_device"]) not in calls
    assert ("power", "uv_vis") not in calls
    power_ready = True
    calls.clear()
    second = controller._v0_preparation_checks(fix=False)
    assert all(check["ok"] for check in second)
    assert calls.index(("device", controller._hardware_config["dg645_device"])) > max(
        index for index, (kind, _name) in enumerate(calls) if kind == "power"
    )


@pytest.mark.parametrize("entry", ["_v0_preparation_checks", "hardware_preflight"])
def test_v0_preparation_refuses_fix_before_any_hardware_access(monkeypatch, entry):
    monkeypatch.setattr(v0_api_module, "V0_PREPARATION_READ_ONLY", True)
    controller = v0_api_module.PumpProbeV0Controller()
    monkeypatch.setattr(controller, "_everest_server_snapshot", lambda: pytest.fail("No hardware access when repair is requested"))
    with pytest.raises(ValueError, match="read-only|disabled"):
        getattr(controller, entry)(fix=True)


def test_v0_initialize_route_accepts_fixed_scope_in_local_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(v0_api_module, "authorization_required", lambda: False)
    calls = []
    monkeypatch.setattr(v0_api_module, "_guard_v0_hardware", lambda *args: calls.append(args))
    monkeypatch.setattr(v0_api_module, "_prepare_v0_experiment", lambda: {"success": True})
    monkeypatch.setattr(v0_api_module, "_v0_lifecycle_instance", None)
    monkeypatch.setenv("PYCONLYSE_V0_EXPERIMENT_STATE_DB", str(tmp_path / "lifecycle.sqlite3"))
    app = Flask(__name__)
    app.register_blueprint(v0_api_module.pump_probe_v0_api)
    response = app.test_client().post("/api/pump-probe-v0/hardware/initialize", json={})
    assert response.status_code == 200
    assert calls == [("v0.initialize", {})]


def test_emulator_run_publishes_h5_dat_and_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(v0_api_module, "_emulator", v0_api_module.PumpProbeV0Controller())
    app = Flask(__name__)
    app.register_blueprint(v0_api_module.pump_probe_v0_api)

    with app.test_client() as client:
        configured = client.post("/api/pump-probe-v0/config", json={
            "control_mode": "emulator",
            "point_count": 2,
            "scan_start_ps": -1,
            "delay_step_ps": 1,
            "pulses_per_point": 1,
            "real_zero_ps": 0,
        })
        assert configured.status_code == 200

        started = client.post("/api/pump-probe-v0/run", json={
            "running": True,
            "save_path": str(tmp_path),
            "sample_name": "emulator-test",
        })
        assert started.status_code == 200

        time.sleep(1.0)
        state = client.get("/api/pump-probe-v0/state").get_json()

        assert state["run"]["status"] == "completed"
        artifacts = state["run"]["artifacts"]
        assert all(Path(artifacts[key]).is_file() for key in ("h5", "dat", "manifest"))

        loaded = client.post("/api/pump-probe-v0/data/load", json={"path": artifacts["h5"]})
        assert loaded.status_code == 200
        payload = loaded.get_json()
        assert payload["kind"] == "h5"
        assert len(payload["channels"]) == 6
        assert payload["raw_trace_count"] == 1
