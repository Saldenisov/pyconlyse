"""Software-only checks of instrument ownership and managed Burst acquisition."""
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from vd2_measurement_protocol import Vd2MeasurementProtocol
import vd2_tango_optics as optics


class Generator:
    def __init__(self, events, **settings):
        self.events = events
        self.values = {"BURM": 0, "TSRC": 5, "TRAT": 5, "BURC": 2, "BURP": 0.1, "BURD": 0, "BURT": 0,
                       **{f"PRES? {i}": 1 for i in range(5)}, **settings}
        self.reject_pause = False

    def set_timeout_millis(self, timeout):
        pass

    def state(self):
        return "ON"

    def command_inout(self, command, value):
        if command == "scpi_query":
            return str(self.values[value.removesuffix("?")])
        assert command == "scpi_write"
        key, raw = value.split()
        self.events.append(value)
        if not (self.reject_pause and value == "TSRC 5"):
            self.values[key] = float(raw)


class Camera:
    def __init__(self, events, fail_on=None):
        self.events = events
        self.fail_on = fail_on
        self.acq_status = "idle"

    def set_timeout_millis(self, timeout):
        pass

    def state(self):
        return "ON"

    def read_attribute(self, name):
        return SimpleNamespace(value={
            "camera_only_application": True, "application_running": True,
            "connected": True, "remoteex_status": self.acq_status.split(",")[0],
        }[name])

    def write_attribute(self, name, value):
        self.events.append((name, value))

    def command_inout(self, command, value=None):
        if command == "ExecuteRaw":
            return {
                "DevParamGet(TD,Mode)": "0,DevParamGet,Operate",
                "DevParamGet(TD,Time Range)": "0,DevParamGet,1 us",
                "AcqStatus()": f"0,AcqStatus,{self.acq_status}",
            }[value]
        self.events.append(command)
        if command == self.fail_on:
            raise RuntimeError("Synthetic camera failure")


@pytest.fixture
def rig(monkeypatch):
    events = []
    camera, dg645 = Camera(events), Generator(events)
    lamp = SimpleNamespace(
        state=lambda: "ON", set_timeout_millis=lambda timeout: None,
        read_attribute=lambda name: SimpleNamespace(value={"ids": [1], "states": [1]}[name]),
    )
    monkeypatch.setattr(api, "VD2_CAMERA_ONLY", True)
    monkeypatch.setattr(api, "DeviceProxy", lambda device: {
        api.STREAK_DEVICE: camera, api.DG645_DEVICE: dg645, api.ZABER_PDU_DEVICE: lamp,
    }[device])
    monkeypatch.setattr(api, "verify_timing", lambda proxy, profile: None)

    return camera, dg645, events


@pytest.mark.parametrize(("phase", "frame_count", "fail_on"), [
    ("ABSORPTION", 3, None), ("BASE", 1, None), ("BRUIT", 4, None),
    ("ABSORPTION", 4, "StartSequence"), ("ABSORPTION", 4, "SaveCurrentSequence"),
])
def test_standard_internal_sequence_stays_at_five_hz_and_pauses_before_saving(
    tmp_path, rig, phase, frame_count, fail_on,
):
    camera, dg645, events = rig
    camera.fail_on = fail_on
    protocol = Vd2MeasurementProtocol(
        lambda: camera, capture_clock=lambda proxy, request: optics.measurement_clock(api, proxy, request),
    )
    protocol.start(phase=phase, frames_per_his=frame_count, output_root=str(tmp_path), run_name="test")
    protocol.wait(5)
    assert {key: dg645.values[key] for key in ("BURM", "TSRC", "TRAT")} == {"BURM": 0, "TSRC": 5, "TRAT": 5}
    assert [event for event in events if isinstance(event, str) and " " in event] == ["TSRC 0", "TSRC 5"]
    assert ("sequence_loops", str(frame_count)) in events
    assert events.index("TSRC 0") < events.index("StartSequence") < events.index("TSRC 5")
    if fail_on != "StartSequence":
        assert events.index("WaitForIdle") < events.index("TSRC 5") < events.index("SaveCurrentSequence")
    if fail_on:
        assert "Synthetic camera failure" in protocol.status()["error"]
    else:
        assert protocol.status()["status"] == "completed"
        assert protocol.status()["capture_rate"] == 5


def test_unverified_standby_retains_capture_without_processing(tmp_path, rig):
    camera, dg645, events = rig
    dg645.reject_pause = True
    protocol = Vd2MeasurementProtocol(
        lambda: camera, capture_clock=lambda proxy, request: optics.measurement_clock(api, proxy, request),
        capture_validator=lambda *args: pytest.fail("Unverified clock must not reach conversion"),
    )
    protocol.start(phase="BASE", frames_per_his=4, output_root=str(tmp_path), run_name="test")
    protocol.wait(5)
    assert "pulse pause" in protocol.status()["error"]
    assert dg645.values["TSRC"] == 0
    assert events.index("TSRC 5") < events.index("SaveCurrentSequence")


def test_burst_on_is_reserved_for_managed_capture(rig):
    camera, _, events = rig
    with pytest.raises(ValueError, match="armed automatically"):
        optics.write_parameter(api, camera, "delay_burst_mode", "On")
    assert events == []


@pytest.mark.parametrize(("source", "edge"), [(1, "external_rising"), (2, "external_falling")])
def test_standard_sequence_preserves_external_sync(tmp_path, rig, source, edge):
    camera, dg645, events = rig
    dg645.values.update(TSRC=source, TRAT=0.001)
    machine = {}
    protocol = Vd2MeasurementProtocol(
        lambda: camera, capture_clock=lambda proxy, request: optics.measurement_clock(api, proxy, request),
        snapshot_reader=lambda proxy: machine,
    )
    protocol.start(phase="BASE", frames_per_his=3, output_root=str(tmp_path), run_name="test")
    protocol.wait(5)
    assert protocol.status()["status"] == "completed"
    assert protocol.status()["capture_rate"] == 5
    assert machine["vd2_clock"]["trigger_source"] == edge
    assert dg645.values["TSRC"] == source and dg645.values["BURM"] == 0
    assert events == [("sequence_loops", "3"), "StartSequence", "WaitForIdle", "SaveCurrentSequence"]


def test_standard_capture_checks_intervals_only_when_two_frames_exist(rig, monkeypatch):
    observed = []
    monkeypatch.setattr("vd2_his_timing.verify_frame_rate", lambda *args: observed.append(args))
    for frame_count in (1, 3):
        request = SimpleNamespace(phase="BRUIT", frames_per_his=frame_count, his_path="dark.his")
        optics.validate_saved_capture(api, request, {}, 5)
    assert observed == [("dark.his", 3, 5)]


def test_burst_is_blocked_on_unmanaged_sequence(rig):
    camera, dg645, events = rig
    dg645.values.update(BURM=1, TSRC=0)
    with pytest.raises(RuntimeError, match="reserved for paired"):
        api._verify_vd2_timing_ready(camera)
    assert events == []


def test_camera_restart_uses_only_the_camera_command(rig, monkeypatch):
    camera, dg645, events = rig
    monkeypatch.setattr(api, "_proxy", lambda: camera)
    monkeypatch.setattr(api, "_snapshot", lambda proxy: {})
    monkeypatch.setattr(api, "_approval_or_response", lambda *args: None)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    reply = app.test_client().post("/api/pump-probe-vd2/command/StartApplication", json={})
    assert reply.status_code == 200
    assert events == ["StartCameraOnlyApplication"]


def test_wavelength_readback_uses_kymera_without_remoteex(rig, monkeypatch):
    camera, dg645, events = rig
    kymera = SimpleNamespace(state=lambda: "ON", set_timeout_millis=lambda timeout: None,
                             read_attribute=lambda name: SimpleNamespace(value=550.0))
    monkeypatch.setattr(api, "DeviceProxy", lambda device: {api.KYMERA_DEVICE: kymera}[device])
    assert api._remoteex_readback(camera, "DevParamGet(Spec,Wavelength)") == "550.0"
    assert events == []


@pytest.mark.parametrize("acq_status", ["idle", "busy,live"])
def test_select_blaze_500_by_physical_grating_index(rig, monkeypatch, acq_status):
    camera, _, events = rig
    camera.acq_status = acq_status
    actual = {"grating": 2, "blaze_wavelength_nm": 800.0}

    def move(attribute, value):
        events.append((attribute, value))
        actual.update(grating=value, blaze_wavelength_nm=500.0)

    kymera = SimpleNamespace(state=lambda: "ON", set_timeout_millis=lambda timeout: None,
                             read_attribute=lambda name: SimpleNamespace(value=actual[name]),
                             write_attribute=move)
    monkeypatch.setattr(api, "_proxy", lambda: camera)
    monkeypatch.setattr(api, "DeviceProxy", lambda device: {api.KYMERA_DEVICE: kymera}[device])
    monkeypatch.setattr(api, "_snapshot", lambda proxy: {"values": {
        "grating_index": optics.read_external(api, "grating_index"), "blaze": actual["blaze_wavelength_nm"],
    }})
    approved = []
    monkeypatch.setattr(api, "_approval_or_response", lambda *args: approved.append(args))
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    client = app.test_client()
    path = "/api/pump-probe-vd2/parameter/grating_index"

    rejected = client.post(path, json={"value": 150})
    assert rejected.status_code == 400
    assert not events and not approved

    reply = client.post(path, json={"value": 3})
    assert reply.status_code == 200, reply.get_json()
    assert reply.get_json()["values"] == {"grating_index": 3, "blaze": 500.0}
    assert events == [("grating", 3)]
    assert approved[0][1:3] == (
        [api._target(api.KYMERA_DEVICE, "write_attribute:grating")],
        {"name": "grating_index", "value": 3},
    )


@pytest.mark.parametrize(
    ("acq_status", "phase", "target", "value", "result", "expected_events"),
    [
        ("busy,live", "idle", "delay_trigger_mode", "Internal", 200, ["TSRC 0"]),
        ("idle", "idle", "delay_trigger_mode", "Internal", 200, ["TSRC 5"]),
        ("busy,live", "idle", "delay_repetition_rate", 5, 200, ["TRAT 5"]),
        ("busy,live", "acquiring", "delay_repetition_rate", 5, 503, []),
        ("busy,sequence", "idle", "delay_repetition_rate", 5, 503, []),
        ("busy,sequence", "idle", "grating_index", 3, 503, []),
        ("busy,live", "idle", "time_range", "1 us", 503, []),
    ],
)
def test_manual_tango_settings_require_live_or_idle(
    rig, monkeypatch, acq_status, phase, target, value, result, expected_events,
):
    camera, dg645, events = rig
    camera.acq_status = acq_status
    dg645.values["TSRC"] = 1
    monkeypatch.setattr(api, "_proxy", lambda: camera)
    monkeypatch.setattr(api, "_protocol_hardware_phase", lambda: phase)
    monkeypatch.setattr(api, "_snapshot", lambda proxy: {})
    monkeypatch.setattr(api, "_approval_or_response", lambda *args: None)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)

    reply = app.test_client().post(f"/api/pump-probe-vd2/parameter/{target}", json={"value": value})

    assert reply.status_code == result, reply.get_json()
    assert events == expected_events


def test_alignment_opens_tango_kymera_shutter_with_live_running(rig, monkeypatch):
    camera, _, events = rig
    camera.acq_status = "busy,live"
    actual = {"shutter": "Closed"}

    def move(name, value):
        events.append((name, value))
        actual[name] = value

    native_query = camera.command_inout
    monkeypatch.setattr(camera, "command_inout", lambda command, value=None:
                        "0,DevParamGet,Open" if value == "DevParamGet(TD,Shutter)"
                        else native_query(command, value))
    kymera = SimpleNamespace(
        state=lambda: "ON",
        set_timeout_millis=lambda timeout: None,
        read_attribute=lambda name: SimpleNamespace(value=actual[name]),
        write_attribute=move,
    )
    monkeypatch.setattr(api, "DeviceProxy", lambda device: {api.KYMERA_DEVICE: kymera}[device])
    monkeypatch.setattr(api, "_proxy", lambda: camera)
    monkeypatch.setattr(api, "_approval_or_response", lambda *args: None)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)

    reply = app.test_client().post("/api/pump-probe-vd2/alignment/open-shutters", json={})

    assert reply.status_code == 200, reply.get_json()
    assert events == [("streak_shutter", "Open"), ("shutter", "Open")]


def test_stale_hpdta_wavelength_metadata_is_rejected():
    with pytest.raises(RuntimeError, match="do not match Tango Kymera"):
        optics.verify_image_optics({"wavelength_nm": "550", "grating": "150 g/mm"},
                                   {"wavelength_nm": 400, "lines_per_mm": 150, "grating": 2})


def test_camera_profile_follows_recorded_detector_and_kymera():
    from DeviceServers.cameras.hamamatsu_streak.spectral_calibration import (
        load_spectral_calibration, verified_wavelengths,
    )

    profile = load_spectral_calibration(
        Path(__file__).resolve().parents[2] / "web/pump_probe/config/vd2_spectral_calibration_550nm.json"
    )
    header = '[Camera],' + ','.join(f'{key}="{value}"' for key, value in profile['camera'].items())
    values = dict(profile['kymera'])
    machine = {'streak_spectral_calibration': profile,
               'devices': {api.KYMERA_DEVICE: {'values': values}}}
    axis, identity = verified_wavelengths(header, machine, api.KYMERA_DEVICE)
    assert len(axis) == 640 and identity == profile['id']
    assert profile["center_pixel"] == pytest.approx(425.548, abs=0.001)
    assert profile["dispersion_nm_per_pixel"] == pytest.approx(0.5155, abs=0.0001)
    values['wavelength_nm'] = 560.0
    with pytest.raises(ValueError, match='does not match Kymera wavelength_nm'):
        verified_wavelengths(header, machine, api.KYMERA_DEVICE)
    values['wavelength_nm'] = profile['kymera']['wavelength_nm']
    with pytest.raises(ValueError, match='does not match the HIS camera geometry'):
        verified_wavelengths(header.replace('HOffs="176"', 'HOffs="178"'), machine, api.KYMERA_DEVICE)
    machine['streak_spectral_calibration'] = {}
    with pytest.raises(ValueError, match='Camera spectral calibration is unavailable'):
        verified_wavelengths(header, machine, api.KYMERA_DEVICE)


def test_scanned_profile_preserves_dispersion_and_anchors_between_measured_settings(tmp_path):
    import json
    from DeviceServers.cameras.hamamatsu_streak.spectral_calibration import (
        load_spectral_calibration, verified_wavelengths,
    )

    profile = load_spectral_calibration(
        Path(__file__).resolve().parents[2] / "web/pump_probe/config/vd2_spectral_calibration_550nm.json"
    )
    profile["camera"]["HWidth"] = "4"
    profile["kymera"].pop("wavelength_nm")
    for key in ("wavelengths_nm", "center_pixel", "dispersion_nm_per_pixel"):
        profile.pop(key)
    profile["wavelength_settings"] = [
        {"wavelength_nm": 500, "wavelengths_nm": [480, 500, 522, 546]},
        {"wavelength_nm": 510, "wavelengths_nm": [495, 514, 537, 562]},
    ]
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    profile = load_spectral_calibration(path)
    assert [entry["center_pixel"] for entry in profile["wavelength_settings"]] == pytest.approx([1, 15 / 19])
    assert [entry["dispersion_nm_per_pixel"] for entry in profile["wavelength_settings"]] == [22, 19]

    header = '[Camera],' + ','.join(f'{key}="{value}"' for key, value in profile["camera"].items())
    values = {**profile["kymera"], "wavelength_nm": 505}
    machine = {"streak_spectral_calibration": profile, "devices": {api.KYMERA_DEVICE: {"values": values}}}
    assert verified_wavelengths(header, machine, api.KYMERA_DEVICE) == (
        (487.5, 507, 529.5, 554), profile["id"],
    )
    values["wavelength_nm"] = 510
    assert verified_wavelengths(header, machine, api.KYMERA_DEVICE)[0] == (495, 514, 537, 562)
    values["wavelength_nm"] = 520
    with pytest.raises(ValueError, match="outside the measured calibration scan"):
        verified_wavelengths(header, machine, api.KYMERA_DEVICE)


def test_paired_clock_keeps_external_source_through_warmup_and_capture(rig):
    camera, dg645, events = rig
    dg645.values["TSRC"] = 1

    class Stop:
        def wait(self, seconds):
            assert seconds == 10 and dg645.values["TSRC"] == 1 and dg645.values["BURM"] == 1
            events.append("warm")
            return False

        def is_set(self):
            return False

    def arm():
        assert dg645.values["TSRC"] == 1 and dg645.values["BURM"] == 1
        events.append("arm")

    with optics.paired_capture_clock(api, camera, 1, Stop(), arm) as running:
        assert running
        events.append("record")
    assert events == ["BURC 2", "BURP 0.1", "BURM 1", "warm", "arm", "record", "BURM 0"]
    assert dg645.values["TRAT"] == 5 and dg645.values["TSRC"] == 1


def test_cancel_during_paired_warmup_turns_burst_off_without_stopping_external_clock(rig):
    camera, dg645, events = rig
    dg645.values["TSRC"] = 1
    stop = SimpleNamespace(is_set=lambda: False, wait=lambda seconds: True)
    with optics.paired_capture_clock(api, camera, 1, stop, lambda: pytest.fail("Camera armed")) as running:
        assert not running
    assert events[-1] == "BURM 0" and dg645.values["TSRC"] == 1


def test_paired_clock_refuses_unselected_source_without_writing(rig):
    camera, dg645, events = rig
    with pytest.raises(ValueError, match="active DG645"):
        with optics.paired_capture_clock(api, camera, 1, None, lambda: None):
            pytest.fail("Capture started")
    assert not events
