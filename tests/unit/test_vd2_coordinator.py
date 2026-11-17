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

        def command_inout(self, command, value=None):
            events.append((command, value))
            if command == "OpenReadout":
                self.current_state = tango.DevState.ON
            elif command == "SetROI":
                return (*value, value[-1])
            elif command == "StartSynchronizedLiveAt":
                if self.reject_start:
                    raise RuntimeError("Test CCD refused Live")
                self.current_state = tango.DevState.RUNNING
                self.AcquisitionActive = True
            elif command == "CloseReadout":
                self.current_state = tango.DevState.OFF
                self.AcquisitionActive = False

    class Generator:
        settings = {"TSRC?": "5", "TRAT?": "5", "BURM?": "0", "DLAY? 2": "0,+0.0020417",
                    "DLAY? 6": "0,+0.0022065", "*OPC?": "1"}

        def state(self):
            return tango.DevState.ON

        def command_inout(self, method, value):
            if method == "scpi_query":
                return self.settings[value]
            events.append(value)
            if value.startswith("DLAY 6,"):
                self.settings["DLAY? 6"] = value.removeprefix("DLAY 6,")
            else:
                self.settings["TSRC?"] = value.removeprefix("TSRC ")

    def head_readback(command, value):
        events.append((command, value))
        return value

    ccd, generator = Camera(), Generator()
    lamp = SimpleNamespace(ids=[1, 2], states=[1, 1])
    kymera = SimpleNamespace(shutter="Closed", wavelength_nm=550., grating=3, blaze_wavelength_nm=500.)
    devices = {device.ccd_device: ccd, device.dg645_device: generator,
               device.kymera_device: kymera, device.lamp_pdu_device: lamp,
               device.head_device: SimpleNamespace(command_inout=head_readback)}
    monkeypatch.setattr(device, "_proxy", lambda name, timeout=6000: devices[name])
    return device, events, ccd, generator, kymera, lamp, now


def test_range_updates_head_and_e_then_starts_clock_only_after_arming_camera(rig):
    vd2, events, ccd, generator, kymera, _, _ = rig
    assert vd2.SetTimeRange("2 µs") == "2 us"
    assert events == [("ConfigureSweep", "2 us"), "DLAY 6,0,0.0022054"]
    assert generator.settings["DLAY? 2"] == "0,+0.0020417"
    vd2.StartLive()
    assert events[-2:] == [("StartSynchronizedLiveAt", "2 us"), "TSRC 0"]
    assert ccd.ExposureMs == 10.0
    assert kymera.shutter == "Open"
    with pytest.raises(RuntimeError, match="Stop the current"):
        vd2.SetTimeRange("1 us")
    vd2.StopLive()
    assert events[-2:] == ["TSRC 5", ("CloseReadout", None)]
    assert kymera.shutter == "Closed"
    assert json.loads(vd2.GetState())["phase"] == "idle"


def test_external_trigger_and_warmup_keep_operator_clock(rig):
    vd2, events, ccd, generator, _, lamp, now = rig
    generator.settings["TSRC?"] = "1"
    lamp.states[0] = 0
    with pytest.raises(RuntimeError, match="flashlamp"):
        vd2.PrepareMeasurement()
    assert events == []
    lamp.states[0] = 1
    vd2.PrepareMeasurement()
    assert json.loads(vd2.GetState())["phase"] == "warming"
    now[0] += 10
    ccd.SweepFrameCount = 49
    assert json.loads(vd2.GetState())["phase"] == "waiting_for_trigger"
    ccd.SweepFrameCount = 50
    assert json.loads(vd2.GetState())["phase"] == "measurement_ready"
    vd2.StopLive()
    assert generator.settings["TSRC?"] == "1"
    assert not any(item in ("TSRC 0", "TSRC 5") for item in events)


def test_ccd_start_failure_releases_handles_without_emitting_pulses(rig):
    vd2, events, ccd, _, kymera, _, _ = rig
    ccd.reject_start = True
    with pytest.raises(RuntimeError, match="refused Live"):
        vd2.StartLive()
    assert events[-1] == ("CloseReadout", None)
    assert "TSRC 0" not in events
    assert kymera.shutter == "Closed"
    assert json.loads(vd2.GetState())["phase"] == "fault"
