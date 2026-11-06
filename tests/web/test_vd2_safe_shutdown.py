"""Software-only lifecycle: startup, repeat startup and verified reverse shutdown."""

import json
from itertools import count
from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api


@pytest.fixture
def rig(monkeypatch):
    events = []
    power = {
        api.VD2_PDU_DEVICE: {1: 1, 2: 1, 3: 1, 4: 1},
        api.ZABER_PDU_DEVICE: {1: 1, 2: 1, 3: 1, 4: 1},
        api.OWIS_PDU_DEVICE: {1: 1, 2: 1, 3: 1, 4: 1},
    }
    native = {
        "connected": True, "application_running": True, "remoteex_status": "idle",
        "streak_shutter": "Open", "spectrograph_shutter": "Open",
        "blaze": "800", "ruling": "150", "streak_mode": "Operate",
        "time_range": "1 us", "wavelength_nm": "550",
    }
    running = []
    faults = {}
    protocol = {"status": "idle"}
    kymera_sdk = {"open": False}
    dg645_delays = {2: (0, "0.0020417"), 6: (0, "0.0022065")}

    class Proxy:
        def __init__(self, device):
            self.device = device

        def set_timeout_millis(self, _timeout):
            pass

        def get_property(self, names):
            return {name: ["0"] for name in names}

        def state(self):
            if self.device in faults and faults[self.device] == "unreachable":
                raise RuntimeError("device unavailable")
            if self.device == api.ZABER_STAGE_DEVICE:
                if not power[api.ZABER_PDU_DEVICE][3]:
                    return "OFF"
                return faults.get("zaber_state", "ON")
            if self.device == api.KYMERA_DEVICE:
                return "ON" if kymera_sdk["open"] else "OFF"
            return "ON"

        def read_attribute(self, name):
            if self.device in power:
                # Deliberately non-sequential IDs; a whole-vector rewrite must
                # preserve all unrelated outputs and follow IDs, not positions.
                value = [3, 1, 4, 2] if name == "ids" else [power[self.device][index] for index in [3, 1, 4, 2]]
            elif self.device == api.STREAK_DEVICE:
                value = native.get(name)
            else:
                value = 12.5 if name in {"pos2", "position_mm"} else 2
            return SimpleNamespace(value=value)

        def command_inout(self, command, arg=None):
            events.append((self.device, command, arg))
            if faults.get(command):
                raise RuntimeError(f"{command} failed")
            if command == "set_channels_states":
                if faults.get("power_off_readback") and self.device == api.VD2_PDU_DEVICE:
                    return 0
                power[self.device].update(dict(zip([3, 1, 4, 2], arg)))
                if faults.get("xenon_power_changed") and self.device == api.ZABER_PDU_DEVICE:
                    power[self.device][2] = 0
                return 0
            if command == "ExecuteRaw":
                if arg == "AcqStatus()":
                    if not native["application_running"]:
                        raise RuntimeError("3,AcqStatus,Application not running")
                    return f"0,AcqStatus,{native['remoteex_status']}"
                if arg == "AppInfo(Version)":
                    return "0,AppInfo,9.5"
                field = {"DevParamGet(TD,Shutter)": "streak_shutter",
                         "DevParamGet(Spec,Shutter)": "spectrograph_shutter",
                         "DevParamGet(Spec,Blaze)": "blaze",
                         "DevParamGet(Spec,Ruling)": "ruling",
                         "DevParamGet(TD,Time Range)": "time_range",
                         "DevParamGet(TD,Mode)": "streak_mode"}[arg]
                return f"0,DevParamGet,{native[field]}"
            if command == "StopAcquisition":
                if not faults.get("acquisition_stays_busy"):
                    native["remoteex_status"] = "idle"
            elif command == "StopApplication":
                if not faults.get("application_stays_running"):
                    native["application_running"] = False
            elif command == "StopRemoteEx":
                native.update(connected=False, application_running=False, remoteex_status="disconnected")
            elif command == "StartRemoteEx":
                native.update(connected=True, remoteex_status="idle")
            elif command == "StartApplication":
                native.update(application_running=True, streak_shutter="Closed", spectrograph_shutter="Open", streak_mode="Operate", time_range="1 us")
            elif command == "DevGetRunningServers":
                return list(running)
            elif command == "DevStop":
                running.remove(arg)
            elif command == "PrepareVD2Grating":
                return json.dumps({"grating": 2, "blaze": 800, "ruling": 150})
            elif command == "turn_on" and self.device == api.KYMERA_DEVICE:
                assert not native["application_running"] and not native["connected"]
                kymera_sdk["open"] = True
                return 0
            elif command == "turn_off" and self.device == api.KYMERA_DEVICE:
                kymera_sdk["open"] = False
                return 0
            elif command == "scpi_query":
                if arg == "*IDN?":
                    return "SRS,DG645,123,1.0"
                if arg == "*OPC?":
                    return "1"
                if arg.startswith("DLAY?"):
                    reference, seconds = dg645_delays[int(arg.split()[1])]
                    return f"{reference},{seconds}"
                return "0"
            elif command == "scpi_write" and arg.startswith("DLAY "):
                channel, reference, seconds = arg.removeprefix("DLAY ").split(",")
                dg645_delays[int(channel)] = (int(reference), seconds)
                return "0"
            elif command == "get_status_axis":
                return api.DevState.ON
            elif command in {"read_position_axis", "Stop"}:
                return 12.5
            elif command in {"turn_off", "scpi_write", "stop_axis"}:
                return "0"
            else:
                pytest.fail(f"Unexpected command {command} {arg}")

        def write_attribute(self, attribute, value):
            events.append((self.device, attribute, value))
            if attribute == "streak_mode" and faults.get("focus_timeout"):
                if faults.get("focus_timeout_completed"):
                    native[attribute] = value
                raise TimeoutError("API_DeviceTimedOut")
            if attribute == "streak_mode" and faults.get("focus_write_failed"):
                raise RuntimeError("Focus command failed")
            if attribute == "streak_mode" and faults.get("focus_stays_operate"):
                return
            if not faults.get("shutter_stays_open"):
                native[attribute] = value

    proxies = {device: Proxy(device) for device in api.VD2_SERVERS}
    starter = Proxy(api.ASTOR_DEVICE)

    def device_proxy(device):
        if faults.get(device) == "unreachable":
            raise RuntimeError("device unavailable")
        if device == api.KYMERA_DEVICE and api.VD2_SERVERS[device] not in running:
            assert not native["application_running"] and not native["connected"]
            running.append(api.VD2_SERVERS[device])
        return proxies[device]

    monkeypatch.setattr(api, "DeviceProxy", device_proxy)
    monkeypatch.setattr(api, "_wait_for_device", lambda device, **_kwargs: device_proxy(device))
    monkeypatch.setattr(api, "_astor", lambda *_args: starter)
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: dict(protocol)))
    monkeypatch.setattr(api.time, "sleep", lambda *_args: None)
    return SimpleNamespace(events=events, power=power, native=native, running=running, faults=faults, protocol=protocol, kymera_sdk=kymera_sdk)


def power_events(rig):
    return [event for event in rig.events if event[1] == "set_channels_states"]


def test_shutdown_is_verified_reverse_order_and_preserves_shared_supplies(rig):
    result = api._deinitialize_experiment()
    assert not result["warnings"]
    assert "safely shut down" in result["message"]
    events = rig.events
    before = lambda command: next(index for index, (_, name, _) in enumerate(events) if name == command)
    assert before("streak_shutter") < before("spectrograph_shutter") < before("StopApplication") < before("StopRemoteEx") < before("set_channels_states")
    assert before("Stop") < before("stop_axis")
    assert power_events(rig) == [
        (api.ZABER_PDU_DEVICE, "set_channels_states", [1, 0, 1, 1]),
        (api.VD2_PDU_DEVICE, "set_channels_states", [1, 1, 1, 0]),
        (api.VD2_PDU_DEVICE, "set_channels_states", [1, 0, 1, 0]),
    ]
    assert rig.power[api.OWIS_PDU_DEVICE] == {1: 1, 2: 1, 3: 1, 4: 1}
    assert rig.power[api.VD2_PDU_DEVICE] == {1: 0, 2: 0, 3: 1, 4: 1}
    assert rig.power[api.ZABER_PDU_DEVICE] == {1: 0, 2: 1, 3: 1, 4: 1}
    assert any(step["step"] == "Zaber" and step["status"] == "stopped; power retained" for step in result["steps"])
    assert not any(command in {"DevStop", "DevStart", "Home", "move_axis"} for _, command, _ in events)


def test_shutdown_verifies_focus_before_application_exit_and_power_off(rig):
    result = api._deinitialize_experiment()
    focus = rig.events.index((api.STREAK_DEVICE, "streak_mode", "Focus"))
    confirmed = rig.events.index((api.STREAK_DEVICE, "ExecuteRaw", "DevParamGet(TD,Mode)"), focus + 1)
    closed = rig.events.index((api.STREAK_DEVICE, "StopApplication", None))
    first_power_write = next(i for i, event in enumerate(rig.events) if event[1] == "set_channels_states")
    assert focus < confirmed < closed < first_power_write
    assert rig.native["streak_mode"] == "Focus"
    assert {"step": "Streak mode", "status": "verified Focus before shutdown"} in result["steps"]


@pytest.mark.parametrize("fault", ["focus_write_failed", "focus_stays_operate"])
def test_unconfirmed_focus_retains_camera_power_and_software(rig, monkeypatch, fault):
    rig.faults[fault] = True
    ticks = count(0, 11)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure, match="Focus"):
        api._deinitialize_experiment()
    assert not power_events(rig)
    assert not any(command in {"StopApplication", "StopRemoteEx"} for _, command, _ in rig.events)
    assert rig.power[api.VD2_PDU_DEVICE][1] == 1


def test_already_focus_is_verified_without_rewriting_mode(rig):
    rig.native["streak_mode"] = "Focus"
    api._deinitialize_experiment()
    assert not any(command == "streak_mode" for _, command, _ in rig.events)
    assert (api.STREAK_DEVICE, "ExecuteRaw", "DevParamGet(TD,Mode)") in rig.events


def test_repeat_unprepare_does_not_reopen_camera_to_set_focus(rig):
    api._deinitialize_experiment()
    rig.events.clear()
    api._deinitialize_experiment()
    assert not any(command in {"streak_mode", "StartRemoteEx", "StartApplication"} for _, command, _ in rig.events)


@pytest.mark.parametrize("connected", [False, True])
def test_stopped_hpdta_cannot_prove_focus_while_camera_is_still_powered(rig, connected):
    rig.native.update(application_running=False, connected=connected, remoteex_status="disconnected")
    with pytest.raises(api.PreparationFailure, match="Cannot confirm.*Focus"):
        api._deinitialize_experiment()
    assert not power_events(rig)
    assert rig.power[api.VD2_PDU_DEVICE][1] == 1


def test_on_off_on_repeated_on_off_cycle(rig):
    rig.power[api.VD2_PDU_DEVICE].update({1: 0, 2: 0})
    rig.power[api.ZABER_PDU_DEVICE].update({1: 0, 2: 0, 3: 0})
    rig.native.update(connected=False, application_running=False, remoteex_status="disconnected")
    first = api._initialize_experiment()
    assert "already_ready" not in first
    assert not api._deinitialize_experiment()["warnings"]
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0
    assert rig.power[api.ZABER_PDU_DEVICE][3] == 1
    assert "already_ready" not in api._initialize_experiment()
    rig.events.clear()
    with pytest.raises(api.AlreadyPrepared, match="already switched on") as repeated:
        api._initialize_experiment()
    assert repeated.value.code == "experiment_already_on"
    assert not power_events(rig)
    assert not any(command in {"scpi_write", "StopRemoteEx", "StopApplication", "StartApplication"} for _, command, _ in rig.events)
    result = api._deinitialize_experiment()
    assert "safely shut down" in result["message"]
    assert rig.power[api.VD2_PDU_DEVICE] == {1: 0, 2: 0, 3: 1, 4: 1}
    assert rig.power[api.ZABER_PDU_DEVICE] == {1: 0, 2: 1, 3: 1, 4: 1}


def test_existing_instrument_processes_survive_prepare_repeat_and_unprepare(rig):
    rig.native.update(connected=False, application_running=False, remoteex_status="disconnected")
    rig.running.extend(api.VD2_SERVERS[device] for device in api.RETAINED_INSTRUMENT_SERVERS)
    existing = set(rig.running)
    api._initialize_experiment()
    assert not rig.kymera_sdk["open"]
    assert set(rig.running) == existing
    before_repeat = len(rig.events)
    with pytest.raises(api.AlreadyPrepared):
        api._initialize_experiment()
    assert not any(command in {"turn_on", "turn_off", "scpi_write", "StartApplication"}
                   for _, command, _ in rig.events[before_repeat:])
    api._deinitialize_experiment()
    assert set(rig.running) == existing
    assert rig.power[api.ZABER_PDU_DEVICE][3] == 1
    assert not any(command in {"DevStop", "DevStart", "Init"} for _, command, _ in rig.events)


@pytest.mark.parametrize("motor_power", [0, 1])
def test_unprepare_and_repeat_preserve_zaber_outlet_in_every_pdu_write(rig, motor_power):
    rig.power[api.ZABER_PDU_DEVICE][3] = motor_power
    result = api._deinitialize_experiment()
    zaber_writes = [states for device, _, states in power_events(rig) if device == api.ZABER_PDU_DEVICE]
    assert zaber_writes
    # ID 3 is first in this PDU's whole-vector writes, not the third item.
    assert all(states[0] == motor_power for states in zaber_writes)
    assert rig.power[api.ZABER_PDU_DEVICE][3] == motor_power
    assert "Zaber power unchanged" in result["message"]
    assert bool([event for event in rig.events if event[:2] == (api.ZABER_STAGE_DEVICE, "Stop")]) == bool(motor_power)
    assert not any(device == api.ZABER_STAGE_DEVICE and command in {"Init", "recover", "turn_off", "turn_on", "Home"}
                   for device, command, _ in rig.events)
    rig.events.clear()
    api._deinitialize_experiment()
    assert not power_events(rig)
    assert rig.power[api.ZABER_PDU_DEVICE][3] == motor_power


@pytest.mark.parametrize("fault", ["shutter_stays_open", "StopApplication", "application_stays_running", "StopRemoteEx"])
def test_failed_optical_or_software_closure_never_cuts_power(rig, monkeypatch, fault):
    rig.faults[fault] = True
    ticks = count(0, 2)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure):
        api._deinitialize_experiment()
    assert not power_events(rig)
    assert rig.power[api.VD2_PDU_DEVICE][1] == 1


@pytest.mark.parametrize("status", ["acquiring", "saving", "processing"])
def test_unfinished_his_retains_power_without_data_loss(rig, monkeypatch, status):
    rig.protocol["status"] = status
    ticks = count(0, 601)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure, match="HIS measurement/save"):
        api._deinitialize_experiment()
    assert rig.events == []


@pytest.mark.parametrize("status", ["busy", "busy,Live", "busy,Acquire", "BUSY,live"])
def test_manual_live_is_stopped_and_idle_is_confirmed_before_closing(rig, status):
    rig.native["remoteex_status"] = status
    api._deinitialize_experiment()
    assert rig.events[:3] == [
        (api.STREAK_DEVICE, "ExecuteRaw", "AcqStatus()"),
        (api.STREAK_DEVICE, "StopAcquisition", None),
        (api.STREAK_DEVICE, "ExecuteRaw", "AcqStatus()"),
    ]


def test_failed_live_stop_retains_camera_power(rig, monkeypatch):
    rig.native["remoteex_status"] = "busy"
    rig.faults["acquisition_stays_busy"] = True
    ticks = count(0, 11)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure, match="acquisition stopped"):
        api._deinitialize_experiment()
    assert not power_events(rig)


def test_stale_false_application_cache_does_not_skip_shutters(rig, monkeypatch):
    original = api._value
    monkeypatch.setattr(api, "_value", lambda proxy, key: False if key == "application_running" else original(proxy, key))
    api._deinitialize_experiment()
    assert (api.STREAK_DEVICE, "streak_shutter", "Closed") in rig.events


def test_unavailable_zaber_retains_motor_and_xenon_power_but_cuts_flashlamp_and_generator(rig):
    rig.faults[api.ZABER_STAGE_DEVICE] = "unreachable"
    with pytest.raises(api.PreparationFailure, match="Zaber power retained") as error:
        api._deinitialize_experiment()
    assert rig.power[api.ZABER_PDU_DEVICE] == {1: 0, 2: 1, 3: 1, 4: 1}
    assert rig.power[api.VD2_PDU_DEVICE] == {1: 0, 2: 0, 3: 1, 4: 1}
    assert any(step["step"] == "Zaber" and step["status"] == "failed" for step in error.value.steps)


@pytest.mark.parametrize("fault", ["Stop", "moving"])
def test_failed_zaber_motion_stop_never_disables_motor_power(rig, monkeypatch, fault):
    if fault == "moving":
        rig.faults["zaber_state"] = "MOVING"
        ticks = count(0, 11)
        monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    else:
        rig.faults[fault] = True
    with pytest.raises(api.PreparationFailure, match="Zaber power retained"):
        api._deinitialize_experiment()
    assert rig.power[api.ZABER_PDU_DEVICE] == {1: 0, 2: 1, 3: 1, 4: 1}
    assert rig.power[api.VD2_PDU_DEVICE] == {1: 0, 2: 0, 3: 1, 4: 1}
    assert all(states[0] == 1 for device, _, states in power_events(rig) if device == api.ZABER_PDU_DEVICE)


def test_unavailable_vd2_pdu_does_not_block_independent_sd2_shutdown(rig, monkeypatch):
    original = api._ensure_server
    def ensure(device, steps):
        if device == api.ZABER_PDU_DEVICE:
            raise RuntimeError("VD2 PDU restart failed")
        return original(device, steps)
    monkeypatch.setattr(api, "_ensure_server", ensure)
    with pytest.raises(api.PreparationFailure, match="VD2 PDU restart failed"):
        api._deinitialize_experiment()
    assert rig.power[api.VD2_PDU_DEVICE] == {1: 0, 2: 0, 3: 1, 4: 1}
    assert rig.power[api.ZABER_PDU_DEVICE] == {1: 1, 2: 1, 3: 1, 4: 1}
    assert rig.power[api.OWIS_PDU_DEVICE] == {1: 1, 2: 1, 3: 1, 4: 1}


def test_unavailable_owis_is_reported_and_shared_supply_is_never_changed(rig):
    rig.faults[api.OWIS_SAMPLE_DEVICE] = "unreachable"
    result = api._deinitialize_experiment()
    assert result["warnings"]
    assert any("OWIS axis 2 could not be verified" in warning for warning in result["warnings"])
    assert rig.power[api.OWIS_PDU_DEVICE][2] == 1


def test_repeat_shutdown_does_not_rewrite_already_off_power_or_restart_software(rig):
    api._deinitialize_experiment()
    rig.events.clear()
    api._deinitialize_experiment()
    assert not power_events(rig)
    assert not any(command in {"StartRemoteEx", "StartApplication", "DevStart", "StopAcquisition", "StopApplication"} for _, command, _ in rig.events)


@pytest.mark.parametrize("xenon_power", [0, 1])
def test_unprepare_and_repeat_preserve_xenon_cooling_in_every_pdu_write(rig, xenon_power):
    rig.power[api.ZABER_PDU_DEVICE][2] = xenon_power
    result = api._deinitialize_experiment()
    writes = [states for device, _, states in power_events(rig) if device == api.ZABER_PDU_DEVICE]
    assert writes
    # Non-sequential IDs [3, 1, 4, 2]: Xe outlet 2 is last, not second.
    assert all(states[3] == xenon_power for states in writes)
    assert rig.power[api.ZABER_PDU_DEVICE][2] == xenon_power
    assert "Xe lamp cooling power unchanged" in result["message"]
    assert any(step["step"] == "Xe lamp cooling supply (VD2 output 2)"
               and step["status"] == ("retained ON" if xenon_power else "already OFF; outlet unchanged")
               for step in result["steps"])
    assert bool(result["warnings"]) == (xenon_power == 0)
    rig.events.clear()
    api._deinitialize_experiment()
    assert not power_events(rig)
    assert rig.power[api.ZABER_PDU_DEVICE][2] == xenon_power


@pytest.mark.parametrize("output_id", [2, 3])
def test_shutdown_helper_blocks_retained_outlets_before_any_device_access(output_id):
    with pytest.raises(RuntimeError, match="must retain PDU VD2 outputs"):
        api._disable_pdu_outputs(object(), [], {output_id: "Forbidden"}, "VD2")


def test_missing_xenon_readback_blocks_flashlamp_vector_write():
    calls = []
    pdu = SimpleNamespace(
        read_attribute=lambda key: SimpleNamespace(value=[3, 1, 4] if key == "ids" else [1, 1, 1]),
        command_inout=lambda *args: calls.append(args),
    )
    with pytest.raises(RuntimeError, match="required outputs are missing: \\[2\\]"):
        api._disable_pdu_outputs(pdu, [], {1: "Flash Lamp"}, "VD2")
    assert not calls


def test_unexpected_xenon_cooling_loss_is_reported_without_replaying_power_writes(rig):
    rig.faults["xenon_power_changed"] = True
    with pytest.raises(api.PreparationFailure, match="retained power changed or unverified: Xe lamp cooling"):
        api._deinitialize_experiment()
    writes = [states for device, _, states in power_events(rig) if device == api.ZABER_PDU_DEVICE]
    assert writes == [[1, 0, 1, 1]]
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0


@pytest.mark.parametrize("fault", [api.ZABER_STAGE_DEVICE, api.OWIS_SAMPLE_DEVICE,
                                   "Stop", "StopApplication", "focus_write_failed", "power_off_readback"])
def test_fault_paths_never_request_xenon_cooling_power_off(rig, monkeypatch, fault):
    rig.faults[fault] = "unreachable" if fault in {api.ZABER_STAGE_DEVICE, api.OWIS_SAMPLE_DEVICE} else True
    ticks = count(0, 11)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    try:
        api._deinitialize_experiment()
    except api.PreparationFailure:
        pass
    assert rig.power[api.ZABER_PDU_DEVICE][2] == 1
    assert all(states[3] == 1 for device, _, states in power_events(rig) if device == api.ZABER_PDU_DEVICE)


def test_generator_power_off_must_be_confirmed_before_camera_power_off(rig, monkeypatch):
    rig.faults["power_off_readback"] = True
    ticks = count(0, 9)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure, match="did not disable: DG645"):
        api._deinitialize_experiment()
    assert rig.power[api.VD2_PDU_DEVICE][1] == 1


def test_active_kymera_sdk_owner_is_released_but_no_other_server_is_stopped(rig):
    rig.running.append(api.VD2_SERVERS[api.KYMERA_DEVICE])
    rig.running.append(api.VD2_SERVERS[api.ZABER_STAGE_DEVICE])
    rig.kymera_sdk["open"] = True
    api._deinitialize_experiment()
    stopped = [arg for _, command, arg in rig.events if command == "DevStop"]
    assert stopped == []
    assert not rig.kymera_sdk["open"]
    assert api.VD2_SERVERS[api.KYMERA_DEVICE] in rig.running
    assert api.VD2_SERVERS[api.ZABER_STAGE_DEVICE] in rig.running


def test_shutdown_route_returns_partial_steps_and_releases_lifecycle_lock(rig):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    rig.faults["shutter_stays_open"] = True
    with app.test_client() as client:
        response = client.post("/api/pump-probe-vd2/deinitialize")
    assert response.status_code == 503
    assert response.get_json()["steps"][-1]["status"] == "failed"
    assert not api._preparation_lock.locked()


def test_shutdown_cannot_overlap_startup(rig):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    api._preparation_lock.acquire()
    try:
        with app.test_client() as client:
            response = client.post("/api/pump-probe-vd2/deinitialize")
        assert response.status_code == 409
        assert not rig.events
    finally:
        api._preparation_lock.release()


@pytest.mark.parametrize("route,payload", [
    ("/command/StartLive", {}),
    ("/runtime/remoteex/start", {}),
    ("/parameter/wavelength_nm", {"value": 532}),
    ("/protocol/start", {"phase": "BRUIT", "frames_per_his": 2, "run_name": "blocked"}),
])
def test_new_commands_cannot_race_shutdown(rig, route, payload):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    api._preparation_lock.acquire()
    try:
        with app.test_client() as client:
            response = client.post(f"/api/pump-probe-vd2{route}", json=payload)
        assert response.status_code == 409
        assert not rig.events
    finally:
        api._preparation_lock.release()


@pytest.mark.parametrize("status", ["paused", "idle,Live", "busy,,Live"])
def test_unknown_acquisition_reply_never_allows_power_off(rig, status):
    rig.native["remoteex_status"] = status
    with pytest.raises(api.PreparationFailure, match="Unknown acquisition status"):
        api._deinitialize_experiment()
    assert not power_events(rig)
    assert not any(command == "StopAcquisition" for _, command, _ in rig.events)


def test_focus_timeout_completed_is_verified_without_replaying_write(rig):
    rig.faults.update(focus_timeout=True, focus_timeout_completed=True)
    api._deinitialize_experiment()
    assert [e for e in rig.events if e[1] == "streak_mode"] == [(api.STREAK_DEVICE, "streak_mode", "Focus")]
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0


def test_focus_timeout_pending_is_observed_through_read_timeouts_then_completes(rig, monkeypatch):
    rig.faults["focus_timeout"] = True
    proxy = api.DeviceProxy(api.STREAK_DEVICE)
    original = proxy.command_inout
    observations = []
    def command(name, arg=None):
        if arg == "DevParamGet(TD,Mode)" and any(e[1] == "streak_mode" for e in rig.events):
            observations.append(True)
            if len(observations) == 1:
                raise TimeoutError("API_DeviceTimedOut")
            if len(observations) == 3:
                rig.native["streak_mode"] = "Focus"
        return original(name, arg)
    monkeypatch.setattr(proxy, "command_inout", command)
    api._deinitialize_experiment()
    assert len(observations) == 3
    assert len([e for e in rig.events if e[1] == "streak_mode"]) == 1
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0


def test_focus_timeout_without_confirmation_keeps_camera_power_and_application(rig, monkeypatch):
    rig.faults["focus_timeout"] = True
    ticks = count(0, 2)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(api.PreparationFailure, match="Cannot confirm streak camera Focus; power retained"):
        api._deinitialize_experiment()
    assert len([e for e in rig.events if e[1] == "streak_mode"]) == 1
    assert not power_events(rig)
    assert rig.native["application_running"] is True


def test_stop_timeout_with_confirmed_idle_continues_without_replaying_stop(rig, monkeypatch):
    rig.native["remoteex_status"] = "busy,Live"
    proxy = api.DeviceProxy(api.STREAK_DEVICE)
    original = proxy.command_inout
    def command(name, arg=None):
        result = original(name, arg)
        if name == "StopAcquisition":
            raise TimeoutError("TRANSIENT_CallTimedout")
        return result
    monkeypatch.setattr(proxy, "command_inout", command)
    api._deinitialize_experiment()
    assert len([e for e in rig.events if e[1] == "StopAcquisition"]) == 1
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0


def test_unprepare_waits_for_his_save_and_processing_then_finishes_in_same_request(rig, monkeypatch):
    stages = iter(["acquiring", "saving", "processing", "completed"])
    observed = []
    def status():
        phase = next(stages)
        observed.append(phase)
        assert not rig.events  # No camera command or power change races HIS.
        return {"status": phase}
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=status))
    api._deinitialize_experiment()
    assert observed == ["acquiring", "saving", "processing", "completed"]
    assert rig.power[api.VD2_PDU_DEVICE][1] == 0


def test_software_exit_timeout_does_not_trust_cached_disconnected_flags(rig, monkeypatch):
    proxy = api.DeviceProxy(api.STREAK_DEVICE)
    original = proxy.command_inout
    def command(name, arg=None):
        result = original(name, arg)
        if name == "StopRemoteEx":
            raise TimeoutError("process exit acknowledgement missing")
        return result
    monkeypatch.setattr(proxy, "command_inout", command)
    with pytest.raises(api.PreparationFailure, match="acknowledgement missing"):
        api._deinitialize_experiment()
    assert not power_events(rig)
