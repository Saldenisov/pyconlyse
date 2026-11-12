"""Software-only checks of instrument ownership and managed Burst acquisition."""
from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from vd2_measurement_protocol import Vd2MeasurementProtocol
import vd2_tango_optics as optics


class Generator:
    def __init__(self, events, **settings):
        self.events = events
        self.values = {"BURM": 0, "TSRC": 5, "TRAT": 5, "BURC": 2, "BURP": 0.1, "BURD": 0, **settings}
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

    def set_timeout_millis(self, timeout):
        pass

    def state(self):
        return "ON"

    def read_attribute(self, name):
        return SimpleNamespace(value={
            "camera_only_application": True, "application_running": True,
            "connected": True, "remoteex_status": "idle",
        }[name])

    def write_attribute(self, name, value):
        self.events.append((name, value))

    def command_inout(self, command, value=None):
        if command == "ExecuteRaw":
            return {
                "DevParamGet(TD,Mode)": "0,DevParamGet,Operate",
                "DevParamGet(TD,Time Range)": "0,DevParamGet,1 us",
                "AcqStatus()": "0,AcqStatus,idle",
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


def test_stale_hpdta_wavelength_metadata_is_rejected():
    with pytest.raises(RuntimeError, match="do not match Tango Kymera"):
        optics.verify_image_optics({"wavelength_nm": "550", "grating": "150 g/mm"},
                                   {"wavelength_nm": 400, "lines_per_mm": 150, "grating": 2})


def test_paired_clock_warms_arms_with_no_pulses_and_switches_to_external(rig):
    camera, dg645, events = rig

    class Stop:
        def wait(self, seconds):
            assert seconds == 10 and dg645.values["TSRC"] == 0 and dg645.values["BURM"] == 1
            events.append("warm")
            return False

        def is_set(self):
            return False

    def arm():
        assert dg645.values["TSRC"] == 5
        events.append("arm")

    with optics.paired_capture_clock(api, camera, 1, Stop(), arm) as running:
        assert running and dg645.values["TSRC"] == 1
        events.append("record")
    assert events.index("warm") < events.index("arm") < events.index("TSRC 1") < events.index("record")
    assert events[-2:] == ["TSRC 5", "BURM 0"]
    assert dg645.values["TRAT"] == 5


def test_cancel_during_paired_warmup_disarms_without_starting_camera(rig):
    camera, dg645, events = rig
    stop = SimpleNamespace(is_set=lambda: False, wait=lambda seconds: True)
    with optics.paired_capture_clock(api, camera, 0, stop, lambda: pytest.fail("Camera armed")) as running:
        assert not running
    assert events[-2:] == ["TSRC 5", "BURM 0"]
