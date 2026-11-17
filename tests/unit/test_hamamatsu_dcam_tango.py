import importlib
import json
import sys
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest


class FakeCamera:
    def __init__(self):
        self.trigger = "ext"
        self.running = False
        self.closed = False
        self.frame = None
        self.pending_frames = []
        self.properties = {}
        self.geometry = (0, 2, 0, 2, 1, 1)
        self.exposure = 0.025
        self.threads = set()

    def record_thread(self):
        self.threads.add(threading.get_ident())

    def close(self):
        self.record_thread()
        self.closed = True

    def get_detector_size(self):
        self.record_thread()
        return (2048, 2048)

    def get_roi(self):
        self.record_thread()
        return self.geometry

    def set_roi(self, *geometry):
        self.record_thread()
        self.geometry = geometry

    def get_exposure(self):
        self.record_thread()
        return self.exposure

    def set_exposure(self, seconds):
        self.record_thread()
        self.exposure = seconds + 0.000004

    def acquisition_in_progress(self):
        self.record_thread()
        return self.running

    def get_attribute_value(self, name):
        self.record_thread()
        return self.properties.get(name, 0)

    def set_attribute_value(self, name, value):
        self.record_thread()
        if name == "TRIGGER GLOBAL EXPOSURE" and getattr(self, "buffer_allocated", False):
            raise RuntimeError("Release buffers before changing global exposure")
        self.properties[name] = value

    def read_oldest_image(self, *, peek, return_info):
        self.record_thread()
        assert self.running and not peek and return_info
        return self.pending_frames.pop(0) if self.pending_frames else None

    def get_trigger_mode(self):
        self.record_thread()
        return self.trigger

    def set_trigger_mode(self, value):
        self.record_thread()
        self.trigger = value
        return value

    def start_acquisition(self, *, mode, nframes):
        self.record_thread()
        assert mode == "sequence" and nframes == 8
        self.running = True
        self.buffer_allocated = True

    def stop_acquisition(self):
        self.record_thread()
        self.running = False

    def clear_acquisition(self):
        self.stop_acquisition()
        self.buffer_allocated = False

    def read_newest_image(self, *, peek, return_info):
        self.record_thread()
        assert peek and return_info and self.running
        return self.frame


@pytest.fixture
def session(monkeypatch):
    tango = sys.modules["tango"]
    monkeypatch.setattr(tango, "DevUShort", int, raising=False)
    monkeypatch.setattr(tango, "DevLong64", int, raising=False)
    monkeypatch.setattr(tango.server.Device, "delete_device", lambda self: None, raising=False)
    monkeypatch.setattr(tango.server.Device, "set_status", lambda self, status: None, raising=False)
    dcam = importlib.import_module("DeviceServers.cameras.hamamatsu_streak.DS_HAMAMATSU_DCAM")
    camera = FakeCamera()
    opened = []

    def open_camera():
        camera.record_thread()
        opened.append(True)
        return camera, SimpleNamespace(model="C13440-20CU", serial_number="S/N: 303256")

    monkeypatch.setattr(dcam, "open_readout", open_camera)
    device = dcam.DS_HAMAMATSU_DCAM()
    device.init_device()
    try:
        yield dcam, device, camera, opened
    finally:
        device.delete_device()


def test_explicit_lifecycle_and_full_resolution_unsigned_readback(session):
    dcam, proxy, camera, opened = session
    assert proxy.get_state() == dcam.DevState.OFF
    assert opened == []
    with pytest.raises(RuntimeError, match="OpenReadout"):
        proxy.StartLive()
    proxy.OpenReadout()
    proxy.OpenReadout()
    assert opened == [True]
    assert proxy.model() == "C13440-20CU"
    assert proxy.get_state() == dcam.DevState.ON
    assert not proxy.acquisition_active()
    proxy.StartLive()
    assert proxy.get_state() == dcam.DevState.RUNNING
    assert proxy.acquisition_active()
    assert camera.trigger == "int"
    with pytest.raises(RuntimeError, match="Waiting for a DCAM frame"):
        _ = proxy.raw_frame()
    assert proxy.get_state() == dcam.DevState.RUNNING
    assert proxy.frame_stamp() == -1
    image = np.array([[0, 65535], [1234, 49999]], dtype=np.uint16)
    camera.frame = (image, SimpleNamespace(timestamp_us=17_941_000_000_123_456, framestamp=42))
    np.testing.assert_array_equal(proxy.raw_frame(), image)
    assert proxy.raw_frame().dtype == np.uint16
    assert proxy.frame_timestamp_us() == 17_941_000_000_123_456
    assert proxy.frame_stamp() == 42
    proxy.StopLive()
    assert proxy.get_state() == dcam.DevState.ON
    assert proxy.frame_stamp() == -1
    assert not camera.running
    assert camera.trigger == "ext"
    proxy.CloseReadout()
    assert proxy.get_state() == dcam.DevState.OFF
    assert camera.closed
    assert len(camera.threads) == 1


def test_roi_and_exposure_are_read_back_and_match_frame_geometry(session):
    _, proxy, camera, _ = session
    proxy.OpenReadout()
    assert proxy.detector_size() == (2048, 2048)
    with pytest.raises(ValueError, match="within"):
        proxy.SetROI([0, 2049, 0, 2048, 1])
    assert camera.geometry == (0, 2, 0, 2, 1, 1)
    expected_roi = (352, 1632, 516, 1532, 2, 2)
    assert proxy.SetROI(expected_roi[:5]) == expected_roi
    assert proxy.sensor_roi() == expected_roi
    proxy.write_exposure_ms(10)
    assert proxy.exposure_ms() == pytest.approx(10.004)
    proxy.StartLive()
    with pytest.raises(RuntimeError, match="StopLive"):
        proxy.SetROI([0, 2048, 0, 2048, 1])
    with pytest.raises(RuntimeError, match="StopLive"):
        proxy.write_exposure_ms(25)
    camera.frame = (np.zeros((508, 640), dtype=np.uint16), SimpleNamespace(timestamp_us=123, framestamp=7))
    assert proxy.raw_frame().shape == (508, 640)
    proxy.StopLive()
    assert len(camera.threads) == 1


def test_rejects_other_model_and_closes_it(session, monkeypatch):
    dcam, proxy, camera, _ = session
    monkeypatch.setattr(dcam, "open_readout", lambda: (camera, SimpleNamespace(model="C11440-36U")))
    with pytest.raises(RuntimeError, match="Expected C13440-20CU"):
        proxy.OpenReadout()
    assert camera.closed
    assert proxy.get_state() == dcam.DevState.FAULT
    proxy.CloseReadout()
    assert proxy.get_state() == dcam.DevState.OFF


def test_synchronized_sweep_rearms_once_per_camera_frame_without_client_reads(session, monkeypatch):
    dcam, proxy, camera, _ = session
    camera.properties = dict.fromkeys(dcam.SWEEP_SENSOR_PROPERTIES, 0)
    head_values = {"ALL": "verified", "OPE": "OPE", "VSR": "VSR 1US", "SHT": "SHT C", "MCP": "MCP 0",
                   "GMD": "GMD N", "VTM": "VTM S", "VTS": "VTS P", "VTL": "VTL 1.0V"}
    commands = []
    received = threading.Event()

    class Head:
        def read(self, key):
            return head_values[key]

        def write(self, value):
            commands.append(value)
            head_values["SHT"] = value

        def rearm(self):
            commands.append("VRT")
            if commands.count("VRT") == 3:
                received.set()

        def close(self):
            commands.append("closed")

    monkeypatch.setattr(dcam, "C13410Usb", Head)
    proxy.OpenReadout()
    proxy.write_exposure_ms(10)
    proxy.StartSynchronizedLive()
    assert camera.trigger == "ext"
    assert camera.properties == dcam.SWEEP_SENSOR_PROPERTIES
    for stamp in (7, 8):
        frame = np.ones((2, 2), dtype=np.uint16)
        camera.pending_frames.append((frame, SimpleNamespace(timestamp_us=stamp * 200_000, framestamp=stamp)))
    assert received.wait(1)
    deadline = time.monotonic() + 1
    while proxy.sweep_frame_count() != 2 and time.monotonic() < deadline:
        time.sleep(.001)
    assert proxy.sweep_frame_count() == 2
    for _ in range(2):
        np.testing.assert_array_equal(proxy.raw_frame(), frame)
    assert proxy.frame_stamp() == 8
    assert proxy.sweep_vrt_count() == 3
    proxy.StopLive()
    assert commands == ["SHT O", "VRT", "VRT", "VRT", "SHT C", "closed"]
    assert camera.properties == dict.fromkeys(dcam.SWEEP_SENSOR_PROPERTIES, 0)
    assert len(camera.threads) == 1


@pytest.fixture
def gain_live(session, monkeypatch):
    dcam, device, camera, _ = session

    class Head:
        values = {"ALL": "verified", "OPE": "OPE", "VSR": "VSR 1US", "SHT": "SHT C", "MCP": "MCP 0",
                  "GMD": "GMD N", "VTM": "VTM S", "VTS": "VTS P", "VTL": "VTL 1.0V"}
        events = []
        unknown_gain = False
        reject_reset = False

        def read(self, key):
            camera.record_thread()
            if key == "MCP" and self.unknown_gain:
                return "invalid"
            return self.values[key]

        def write(self, command):
            camera.record_thread()
            self.events.append(command)
            if command == "MCP 2" and self.reject_reset:
                self.unknown_gain = True
            if command == "MCP 0" and not self.reject_reset:
                self.unknown_gain = False
            self.values[command.split()[0]] = command

        def rearm(self):
            camera.record_thread()
            self.events.append("VRT")

        def close(self):
            camera.record_thread()
            self.events.append("close")

    head = Head()
    monkeypatch.setattr(dcam, "C13410Usb", lambda: head)
    device.OpenReadout()
    device.write_exposure_ms(10)
    device.StartSynchronizedLive()
    return dcam, device, camera, head


def test_live_mcp_gain_requires_a_configured_limit_and_uses_the_live_owner(gain_live):
    dcam, device, camera, head = gain_live
    assert device.live_mcp_gain_limit() == 0
    with pytest.raises(ValueError, match="Only gain 0"):
        device.SetLiveMcpGain(2)
    device.live_mcp_gain_max = 64
    with pytest.raises(ValueError, match="Only gain 0"):
        device.SetLiveMcpGain(2)
    assert head.events == ["SHT O", "VRT"]

    device.live_mcp_gain_max = 4
    with pytest.raises(ValueError, match="between 0 and 4"):
        device.SetLiveMcpGain(5)
    assert device.SetLiveMcpGain(2) == 2
    assert json.loads(device.ReadoutConfiguration())["mcp_gain"] == 2
    assert device.get_state() == dcam.DevState.RUNNING
    assert camera.running

    device.CloseReadoutKeepShutter()
    assert head.events == ["SHT O", "VRT", "MCP 2", "MCP 0", "close"]
    assert head.values["SHT"] == "SHT O"
    assert len(camera.threads) == 1


def test_live_mcp_gain_blocks_changes_during_sequence(gain_live):
    dcam, device, _, head = gain_live
    device.live_mcp_gain_max = 4
    device.BufferSequence(2)
    with pytest.raises(RuntimeError, match="Finish the VD2 recording"):
        device.SetLiveMcpGain(2)
    assert device.get_state() == dcam.DevState.RUNNING
    assert head.events == ["SHT O", "VRT"]


def test_unverified_gain_fault_closes_shutter_and_retains_head_until_zero(gain_live):
    dcam, device, camera, head = gain_live
    device.live_mcp_gain_max = 4
    head.reject_reset = True
    try:
        with pytest.raises(RuntimeError, match="Acquisition cleanup failed.*did not verify MCP 0"):
            device.SetLiveMcpGain(2)
        assert device.get_state() == dcam.DevState.FAULT
        assert head.events == ["SHT O", "VRT", "MCP 2", "SHT C", "MCP 0"]
        assert head.values["SHT"] == "SHT C"
        assert not camera.running
        assert json.loads(device.ReadoutConfiguration())["mcp_gain"] is None
    finally:
        head.reject_reset = False
    device.CloseReadout()
    assert head.events[-2:] == ["MCP 0", "close"]
    assert device.get_state() == dcam.DevState.OFF


def test_timed_out_gain_turns_off_and_resets_after_the_native_write_returns(gain_live, monkeypatch):
    dcam, device, camera, head = gain_live
    device.live_mcp_gain_max = 4
    release = threading.Event()
    write = head.write

    def slow_gain_write(command):
        if command == "MCP 2":
            assert release.wait(2)
        write(command)

    monkeypatch.setattr(dcam, "SDK_TIMEOUT_S", .05)
    monkeypatch.setattr(head, "write", slow_gain_write)
    try:
        with pytest.raises(RuntimeError, match="timed out"):
            device.SetLiveMcpGain(2)
        with pytest.raises(RuntimeError, match="still running"):
            device.CloseReadout()
    finally:
        release.set()
    device._pending.result(timeout=1)
    assert head.events[-4:] == ["MCP 2", "SHT C", "MCP 0", "close"]
    assert not camera.running


def test_close_refuses_to_race_a_timed_out_call(session, monkeypatch):
    dcam, proxy, camera, _ = session
    release = threading.Event()
    returned = threading.Event()

    def slow_open():
        try:
            assert release.wait(2)
            return camera, SimpleNamespace(model="C13440-20CU", serial_number="S/N: 303256")
        finally:
            returned.set()

    monkeypatch.setattr(dcam, "OPEN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(dcam, "open_readout", slow_open)
    try:
        with pytest.raises(RuntimeError, match="timed out"):
            proxy.OpenReadout()
        assert proxy.get_state() == dcam.DevState.FAULT
        with pytest.raises(RuntimeError, match="still running"):
            proxy.CloseReadout()
        assert not camera.closed
    finally:
        release.set()
    assert returned.wait(1)
    proxy._pending.result(timeout=1)
    proxy.CloseReadout()
    assert camera.closed
    assert proxy.get_state() == dcam.DevState.OFF
