import importlib
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest


class FakeCamera:
    def __init__(self):
        self.trigger = "ext"
        self.running = False
        self.closed = False
        self.frame = None
        self.threads = set()

    def record_thread(self):
        self.threads.add(threading.get_ident())

    def close(self):
        self.record_thread()
        self.closed = True

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

    def stop_acquisition(self):
        self.record_thread()
        self.running = False

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
        return camera, SimpleNamespace(model="C13440-20CU")

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
    proxy.StartLive()
    assert proxy.get_state() == dcam.DevState.RUNNING
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


def test_rejects_other_model_and_closes_it(session, monkeypatch):
    dcam, proxy, camera, _ = session
    monkeypatch.setattr(dcam, "open_readout", lambda: (camera, SimpleNamespace(model="C11440-36U")))
    with pytest.raises(RuntimeError, match="Expected C13440-20CU"):
        proxy.OpenReadout()
    assert camera.closed
    assert proxy.get_state() == dcam.DevState.FAULT
    proxy.CloseReadout()
    assert proxy.get_state() == dcam.DevState.OFF


def test_close_refuses_to_race_a_timed_out_call(session, monkeypatch):
    dcam, proxy, camera, _ = session
    release = threading.Event()
    returned = threading.Event()

    def slow_open():
        try:
            assert release.wait(2)
            return camera, SimpleNamespace(model="C13440-20CU")
        finally:
            returned.set()

    monkeypatch.setattr(dcam, "SDK_TIMEOUT_S", 0.05)
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
    monkeypatch.setattr(dcam, "SDK_TIMEOUT_S", 5.0)
    proxy.CloseReadout()
    assert camera.closed
    assert proxy.get_state() == dcam.DevState.OFF
