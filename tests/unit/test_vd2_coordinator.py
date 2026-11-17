import importlib
import json
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def rig(monkeypatch):
    tango = sys.modules["tango"]
    monkeypatch.setattr(tango.server.Device, "set_status", lambda self, status: None, raising=False)
    module = importlib.import_module("DeviceServers.experiments.DS_VD2")
    device = module.DS_VD2()
    device.init_device()
    events = []
    now = [100.0]
    monkeypatch.setattr(module, "monotonic", lambda: now[0])

    class Camera:
        current_state = tango.DevState.OFF
        SweepFrameCount = 0
        AcquisitionActive = False
        reject_start = False

        def state(self):
            return self.current_state

        def ReadoutConfiguration(self):
            return '{"exposure_ms": 10.0075}'

        def command_inout(self, command, value=None):
            events.append((command, value))
            if command == "OpenReadout":
                self.current_state = tango.DevState.ON
            elif command == "SetROI":
                return (*value, value[-1])
            elif command in {"StartSynchronizedLiveWithOpenShutterAt", "StartSynchronizedDark"}:
                if self.reject_start:
                    raise RuntimeError("Test CCD refused Live")
                self.current_state = tango.DevState.RUNNING
                self.AcquisitionActive = True
            elif command in {"CloseReadout", "CloseReadoutKeepShutter"}:
                self.current_state = tango.DevState.OFF
                self.AcquisitionActive = False

    class Generator:
        settings = {**{f"DLAY? {i}": "0,+0.0" for i in range(3,10)},
                    "TSRC?": "5", "TRAT?": "5", "BURM?": "0", "DLAY? 2": "0,+0.0020417",
                    "DLAY? 6": "0,+0.0022065", "*OPC?": "1"}

        def state(self):
            return tango.DevState.ON

        def command_inout(self, method, value):
            if method == "scpi_query":
                return self.settings[value]
            events.append(value)
            if value.startswith("DLAY 6,"):
                self.settings["DLAY? 6"] = value.removeprefix("DLAY 6,")
            elif value.startswith("TRAT "):
                self.settings["TRAT?"] = value.removeprefix("TRAT ")
            else:
                self.settings["TSRC?"] = value.removeprefix("TSRC ")

    def head_readback(command, value=None):
        events.append((command, value))
        return value

    ccd, generator = Camera(), Generator()
    lamp = SimpleNamespace(ids=[1, 2, 3, 4], names=["Flash Lamp", "Xe-lamp-CW", "Zaber", "NO plug"], states=[1, 1, 1, 0])
    def write_lamp(command, actions):
        assert command == "set_channels_states"
        events.append(tuple(actions))
        lamp.states[0] = actions[0]
    lamp.command_inout = write_lamp
    kymera = SimpleNamespace(state=lambda: tango.DevState.ON, shutter="Closed", wavelength_nm=550.,
                             grating=3, blaze_wavelength_nm=500.)
    kymera.read_attributes = lambda names: [SimpleNamespace(name=name, value=getattr(kymera, name, 0)) for name in names]
    devices = {device.ccd_device: ccd, device.dg645_device: generator,
               device.kymera_device: kymera, device.lamp_pdu_device: lamp,
               device.camera_pdu_device: SimpleNamespace(ids=[1, 2], states=[1, 1]),
               device.head_device: SimpleNamespace(command_inout=head_readback)}
    monkeypatch.setattr(device, "_proxy", lambda name, timeout=6000: devices[name])
    return device, events, ccd, generator, kymera, lamp, now


def test_range_updates_head_and_e_then_starts_clock_only_after_arming_camera(rig):
    vd2, events, ccd, generator, kymera, _, _ = rig
    vd2.Prepare()
    events.clear()
    assert vd2.SetTimeRange("2 µs") == "2 us"
    assert events == [("ConfigureSweep", "2 us"), "DLAY 6,0,0.0022054"]
    assert generator.settings["DLAY? 2"] == "0,+0.0020417"
    vd2.StartLive()
    assert events[-2:] == [("StartSynchronizedLiveWithOpenShutterAt", "2 us"), "TSRC 0"]
    assert ccd.ExposureMs == 10.0
    assert kymera.shutter == "Open"
    with pytest.raises(RuntimeError, match="Stop the current"):
        vd2.SetTimeRange("1 us")
    vd2.StopLive()
    assert events[-2:] == ["TSRC 5", ("CloseReadoutKeepShutter", None)]
    assert kymera.shutter == "Open"
    assert json.loads(vd2.GetState())["phase"] == "idle"


@pytest.mark.parametrize("rate", [5, 10])
def test_internal_trigger_and_warmup_follow_selected_rate(rig, rate):
    vd2, events, ccd, generator, _, lamp, now = rig
    generator.settings["TSRC?"] = "1"
    lamp.states[0] = 0
    with pytest.raises(RuntimeError, match="flashlamp"):
        vd2.PrepareMeasurement()
    assert events == []
    lamp.states[0] = 1
    assert vd2.SetRate(rate) == rate
    vd2.Prepare()
    vd2.PrepareMeasurement()
    assert json.loads(vd2.GetState())["phase"] == "warming"
    now[0] += 10
    ccd.SweepFrameCount = rate * 10 - 1
    assert json.loads(vd2.GetState())["phase"] == "waiting_for_trigger"
    ccd.SweepFrameCount = rate * 10
    assert json.loads(vd2.GetState())["phase"] == "measurement_ready"
    vd2.Unprepare()
    assert generator.settings["TSRC?"] == "5"
    assert int(generator.settings["TRAT?"]) == rate
    assert events[-3:] == ["TSRC 5", ("CloseReadoutKeepShutter", None), ("Park", None)]
    assert not json.loads(vd2.GetState())["prepared"]


def test_ccd_start_failure_releases_handles_without_emitting_pulses(rig):
    vd2, events, ccd, _, kymera, _, _ = rig
    vd2.Prepare()
    ccd.reject_start = True
    with pytest.raises(RuntimeError, match="refused Live"):
        vd2.StartLive()
    assert events[-1] == ("CloseReadout", None)
    assert "TSRC 0" not in events
    assert kymera.shutter == "Closed"
    assert json.loads(vd2.GetState())["phase"] == "fault"


def test_bruit_keeps_dg_in_standby_and_leaves_shutters_and_power_alone(rig):
    vd2, events, _, generator, kymera, lamp, _ = rig
    vd2.Prepare()
    config = json.loads(vd2.StartPhase("BRUIT"))
    assert config["dg_trigger_source"] == 5 and config["ccd_trigger"] == "software"
    assert lamp.states == [1, 1, 1, 0] and kymera.shutter == "Open"
    assert ("StartSynchronizedDark", 5) in events and "TSRC 0" not in events
    vd2.StopLive()
    assert lamp.states[0] == 1 and kymera.shutter == "Open" and generator.settings["TSRC?"] == "5"
    assert json.loads(vd2.StartPhase("BASE"))["dg_trigger_source"] == 0
