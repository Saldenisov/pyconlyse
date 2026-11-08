"""Repeated Prepare verifies an idle, healthy rig without changing hardware."""

from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api


@pytest.fixture
def ready_rig(monkeypatch):
    events = []
    pdu_values = {"ids": [3, 1, 4, 2], "states": [1, 1, 0, 1]}
    streak_values = {
        "connected": True, "application_running": True, "remoteex_status": "idle",
        # Operator settings differ from startup defaults and must survive Prepare.
        "wavelength_nm": "650", "time_range": "5 us", "streak_mode": "Operate",
        "streak_shutter": "Open", "spectrograph_shutter": "Closed",
        "blaze": "800", "ruling": "150",
    }
    native = {
        "AppInfo(Version)": "0,AppInfo,9.5",
        "DevParamGet(Spec,Blaze)": "0,DevParamGet,800",
        "DevParamGet(Spec,Ruling)": "0,DevParamGet,150",
        "DevParamGet(TD,Mode)": "0,DevParamGet,Operate",
        "DevParamGet(TD,Time Range)": "0,DevParamGet,5 us",
        "AcqStatus()": "0,AcqStatus,idle",
    }
    running_servers = []

    class Proxy:
        def __init__(self, device):
            self.device = device
            self.current_state = "ON"
            self.values = dict(streak_values if device == api.STREAK_DEVICE else pdu_values)
            self.values.update({"pos2": 12.5, "position_mm": 21.0})
            self.axis_state = api.DevState.ON
            self.burst = "0"

        def set_timeout_millis(self, _timeout):
            pass

        def state(self):
            return self.current_state

        def status(self):
            return "test device"

        def get_property(self, names):
            return {name: ["0"] for name in names}

        def read_attribute(self, name):
            return SimpleNamespace(value=self.values.get(name))

        def write_attribute(self, *_args):
            pytest.fail("Prepare must not write attributes on a ready rig")

        def command_inout(self, command, arg=None):
            events.append((self.device, command, arg))
            if command == "scpi_query":
                if arg == "*IDN?":
                    return "SRS,DG645,123,1.0"
                if arg == "DLAY? 2":
                    return "0,0.0020417"
                if arg == "DLAY? 6":
                    return getattr(self, "timing_override", "0,0.002202")
                assert arg == "BURM?"
                return self.burst
            if command == "get_status_axis":
                assert arg == api.OWIS_SAMPLE_AXIS
                return self.axis_state
            if command == "read_position_axis":
                assert arg == api.OWIS_SAMPLE_AXIS
                return self.values["pos2"]
            if command == "ExecuteRaw":
                assert self.device == api.STREAK_DEVICE
                return native[arg]
            if command == "DevGetRunningServers":
                assert arg is True
                return running_servers
            pytest.fail(f"Unexpected mutating command: {command} {arg}")

    proxies = {device: Proxy(device) for device in api.VD2_SERVERS}
    starter = Proxy(api.ASTOR_DEVICE)

    def proxy_for(device):
        # A Tango OFF-state read is not an SDK initialization.
        if device == api.KYMERA_DEVICE:
            assert api.VD2_SERVERS[device] in running_servers
        return proxies[device]

    monkeypatch.setattr(api, "DeviceProxy", proxy_for)
    monkeypatch.setattr(api, "_wait_for_device", lambda device, **_kwargs: proxy_for(device))
    monkeypatch.setattr(api, "_astor", lambda *_args: starter)
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    for name in ("_ensure_server", "_prepare_dg645_for_vd2", "_prepare_kymera_for_vd2"):
        monkeypatch.setattr(api, name, lambda *_args: pytest.fail("No startup/recovery on a ready rig"))
    return SimpleNamespace(
        proxies=proxies, native=native, events=events, running_servers=running_servers,
    )


def test_repeated_initialize_rejects_already_on_and_preserves_settings(ready_rig):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    with app.test_client() as client:
        for _ in range(2):
            response = client.post("/api/pump-probe-vd2/initialize")
            assert response.status_code == 409
            result = response.get_json()
            assert result["success"] is False
            assert result["code"] == "experiment_already_on"
            assert "already switched on" in result["error"]
            values = ready_rig.proxies[api.STREAK_DEVICE].values
            assert values["wavelength_nm"] == "650"
            assert values["time_range"] == "5 us"
            assert values["streak_shutter"] == "Open"
            assert values["spectrograph_shutter"] == "Closed"
    assert sum(command == "scpi_query" and arg == "BURM?" for _, command, arg in ready_rig.events) == 4
    assert sum(arg == "DevParamGet(Spec,Blaze)" for _, _, arg in ready_rig.events) == 2


def test_repeat_prepare_with_wrong_timing_fails_without_resetting_operational_optics(ready_rig):
    ready_rig.proxies[api.DG645_DEVICE].timing_override = "0,0.0022065"
    with pytest.raises(api.PreparationFailure, match="timing unverified"):
        api._initialize_experiment()
    values = ready_rig.proxies[api.STREAK_DEVICE].values
    assert values["time_range"] == "5 us"
    assert values["wavelength_nm"] == "650"
    assert not any(command in {"scpi_write", "StartApplication", "StopApplication", "DevStop", "DevStart"}
                   for _, command, _ in ready_rig.events)


@pytest.mark.parametrize("device_name", [
    "VD2_PDU_DEVICE", "ZABER_PDU_DEVICE", "OWIS_PDU_DEVICE", "DG645_DEVICE",
    "OWIS_SAMPLE_DEVICE",
    "ZABER_STAGE_DEVICE", "STREAK_DEVICE",
])
def test_a_fault_in_any_required_server_is_not_already_ready(ready_rig, device_name):
    ready_rig.proxies[getattr(api, device_name)].current_state = "FAULT"
    assert api._prepared_equipment_state() is None


@pytest.mark.parametrize("device", [api.OWIS_CONTROLLER_DEVICE, api.OWIS_SAMPLE_DEVICE, api.OWIS_LEGACY_DEVICE])
def test_other_shared_owis_motion_does_not_reset_an_already_prepared_rig(ready_rig, device):
    ready_rig.proxies[device].current_state = "MOVING"
    # VD2 axis 2 itself is idle; another shared V0 axis may still be moving.
    with pytest.raises(api.AlreadyPrepared):
        api._initialize_experiment()
    assert not any(command in {"Init", "recover", "turn_on", "DevStop", "DevStart"}
                   for _device, command, _arg in ready_rig.events)


@pytest.mark.parametrize("device_name,output_id", [
    ("VD2_PDU_DEVICE", 1), ("VD2_PDU_DEVICE", 2), ("VD2_PDU_DEVICE", 3),
    ("ZABER_PDU_DEVICE", 1), ("ZABER_PDU_DEVICE", 2), ("ZABER_PDU_DEVICE", 3),
    ("OWIS_PDU_DEVICE", 2),
])
def test_required_power_loss_is_not_already_ready(ready_rig, device_name, output_id):
    values = ready_rig.proxies[getattr(api, device_name)].values
    values["states"] = list(values["states"])
    values["states"][values["ids"].index(output_id)] = 0
    assert api._prepared_equipment_state() is None


@pytest.mark.parametrize("field,value", [
    ("burst", "1"), ("burst", "nan"), ("axis_state", api.DevState.OFF),
])
def test_unsafe_generator_or_axis_is_not_already_ready(ready_rig, field, value):
    device = api.DG645_DEVICE if field == "burst" else api.OWIS_SAMPLE_DEVICE
    setattr(ready_rig.proxies[device], field, value)
    assert api._prepared_equipment_state() is None


@pytest.mark.parametrize("device,attribute", [
    (api.OWIS_SAMPLE_DEVICE, "pos2"), (api.ZABER_STAGE_DEVICE, "position_mm"),
])
def test_invalid_stage_readback_is_not_already_ready(ready_rig, device, attribute):
    ready_rig.proxies[device].values[attribute] = float("nan")
    assert api._prepared_equipment_state() is None


@pytest.mark.parametrize("command,response", [
    ("AppInfo(Version)", "3,AppInfo,Application not running"),
    ("AppInfo(Version)", "0,AppInfo,"),
    ("DevParamGet(Spec,Blaze)", "0,DevParamGet,300"),
    ("DevParamGet(Spec,Blaze)", "0,DevParamGet,nan"),
    ("DevParamGet(Spec,Ruling)", "0,DevParamGet,1200"),
    ("DevParamGet(TD,Mode)", "0,DevParamGet,Focus"),
    ("AcqStatus()", "0,AcqStatus,busy"),
    ("DevParamGet(Spec,Blaze)", "0,AppInfo,800"),
])
def test_native_readback_overrides_stale_healthy_tango_cache(ready_rig, command, response):
    ready_rig.native[command] = response
    assert api._prepared_equipment_state() is None


def test_simultaneous_sdk_owner_is_not_already_ready(ready_rig):
    ready_rig.running_servers.append(api.VD2_SERVERS[api.KYMERA_DEVICE])
    assert api._prepared_equipment_state() is None


def test_running_deinitialized_kymera_is_already_ready_without_server_restart(ready_rig):
    ready_rig.running_servers.append(api.VD2_SERVERS[api.KYMERA_DEVICE])
    ready_rig.proxies[api.KYMERA_DEVICE].current_state = "OFF"
    with pytest.raises(api.AlreadyPrepared):
        api._initialize_experiment()
    assert not any(command in {"Init", "turn_on", "turn_off", "DevStop", "DevStart"}
                   for _, command, _ in ready_rig.events)


def test_readiness_is_rechecked_after_a_previous_success(ready_rig, monkeypatch):
    with pytest.raises(api.AlreadyPrepared):
        api._initialize_experiment()
    ready_rig.proxies[api.DG645_DEVICE].current_state = "FAULT"
    recovery_calls = []

    def recover(device, _steps):
        recovery_calls.append(device)
        raise RuntimeError("normal power-first recovery reached")

    monkeypatch.setattr(api, "_ensure_server", recover)
    with pytest.raises(api.PreparationFailure, match="normal power-first recovery"):
        api._initialize_experiment()
    assert recovery_calls == [api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE, api.OWIS_PDU_DEVICE]


@pytest.mark.parametrize("protocol_state", ["acquiring", "saving"])
def test_active_measurement_cannot_enter_prepare(ready_rig, monkeypatch, protocol_state):
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": protocol_state}))
    with pytest.raises(api.PreparationFailure, match="Stop the VD2 measurement"):
        api._initialize_experiment()
    assert ready_rig.events == []


def test_native_acquisition_blocks_prepare_even_when_tango_cache_says_idle(ready_rig):
    ready_rig.native["AcqStatus()"] = "0,AcqStatus,busy"
    with pytest.raises(api.PreparationFailure, match="acquisition is not confirmed idle"):
        api._initialize_experiment()
    assert ready_rig.events == [(api.STREAK_DEVICE, "ExecuteRaw", "AcqStatus()")]


def test_measurement_started_during_passive_checks_blocks_recovery(ready_rig, monkeypatch):
    def incomplete_readiness():
        ready_rig.native["AcqStatus()"] = "0,AcqStatus,busy"
        return None

    monkeypatch.setattr(api, "_prepared_equipment_state", incomplete_readiness)
    with pytest.raises(api.PreparationFailure, match="acquisition is not confirmed idle"):
        api._initialize_experiment()
    assert ready_rig.events == [
        (api.STREAK_DEVICE, "ExecuteRaw", "AcqStatus()"),
        (api.STREAK_DEVICE, "ExecuteRaw", "AcqStatus()"),
    ]
