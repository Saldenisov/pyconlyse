import sys
from pathlib import Path
from threading import Event

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from vd2_measurement_protocol import Vd2MeasurementProtocol, Vd2ProtocolError


class FakeProxy:
    def __init__(self):
        self.calls = []

    def set_timeout_millis(self, value):
        self.calls.append(("timeout", value))

    def read_attribute(self, name):
        class Attribute:
            value = True
        self.calls.append(("read", name))
        return Attribute()

    def write_attribute(self, name, value):
        self.calls.append(("write", name, value))

    def command_inout(self, name, value=None):
        self.calls.append(("command", name, value))


def test_phase_protocol_writes_bruit_his_after_sequence():
    proxy = FakeProxy()
    protocol = Vd2MeasurementProtocol(lambda: proxy)

    state = protocol.start(
        phase="bruit",
        frames_per_his=25,
        output_root=r"E:\DATA_VD2",
        run_name="LiCl_001",
    )
    protocol.wait(1)

    assert state["phase"] == "BRUIT"
    assert state["his_path"] == r"E:\DATA_VD2\LiCl_001\BRUIT.his"
    assert protocol.status()["status"] == "completed"
    assert ("write", "sequence_loops", "25") in proxy.calls
    assert ("command", "StartSequence", None) in proxy.calls
    assert ("command", "WaitForIdle", None) in proxy.calls
    assert ("command", "SaveCurrentSequence", r"E:\DATA_VD2\LiCl_001\BRUIT.his") in proxy.calls


def test_phase_protocol_accepts_legacy_brew_name_as_bruit():
    protocol = Vd2MeasurementProtocol(FakeProxy)

    state = protocol.start(phase="brew", frames_per_his=1, run_name="legacy")
    protocol.wait(1)

    assert state["phase"] == "BRUIT"
    assert state["his_path"].endswith(r"legacy\BRUIT.his")


def test_failed_preflight_releases_ownership_and_retains_completed_job():
    proxy = FakeProxy()

    def preflight(request):
        if request.run_name == "unwritable":
            raise OSError("output folder is not writable")

    protocol = Vd2MeasurementProtocol(lambda: proxy, artifact_preflight=preflight)
    first = protocol.start(phase="BASE", frames_per_his=1, run_name="first")
    protocol.wait(1)
    calls = list(proxy.calls)

    with pytest.raises(OSError, match="not writable"):
        protocol.start(phase="BASE", frames_per_his=1, run_name="unwritable")

    assert proxy.calls == calls
    status = protocol.status()
    assert status["job_id"] == first["job_id"]
    assert status["status"] == "completed"
    assert not status["acquisition_active"]
    protocol.start(phase="BASE", frames_per_his=1, run_name="retry")
    protocol.wait(1)
    assert protocol.status()["status"] == "completed"


def test_overlapping_start_and_failed_processing_release_camera():
    processing = Event()
    release = Event()

    def failed_processing(request):
        processing.set()
        assert release.wait(2)
        raise ValueError("H5 conversion interrupted")

    protocol = Vd2MeasurementProtocol(FakeProxy, sequence_processor=failed_processing,
                                      max_pending_processing=1)
    protocol.start(phase="BASE", frames_per_his=1, run_name="first")
    try:
        assert processing.wait(1)
        with pytest.raises(Vd2ProtocolError, match="queue is full"):
            protocol.start(phase="BASE", frames_per_his=1, run_name="overlap")
        assert protocol.status()["queue_full"]
    finally:
        release.set()
        protocol.wait(1)

    status = protocol.status()
    assert status["status"] == "failed"
    assert status["error"] == "H5 conversion interrupted"
    assert not status["queue_full"]
    assert not status["acquisition_active"]


@pytest.mark.parametrize("changes", [
    {"phase": "unknown"},
    {"frames_per_his": "invalid"},
    {"frames_per_his": 0},
    {"sample_description": "x" * 4001},
    {"output_root": "relative/folder"},
])
def test_invalid_request_never_contacts_camera(changes):
    calls = []
    protocol = Vd2MeasurementProtocol(lambda: calls.append("camera"))
    request = {"phase": "BASE", "frames_per_his": 1, "run_name": "sample", **changes}
    with pytest.raises(Vd2ProtocolError):
        protocol.start(**request)
    assert calls == []
    assert protocol.status()["status"] == "idle"


def test_phase_protocol_rejects_invalid_run_name():
    protocol = Vd2MeasurementProtocol(FakeProxy)

    try:
        protocol.start(phase="BASE", frames_per_his=1, run_name="../unsafe")
    except Vd2ProtocolError as exc:
        assert "Run name" in str(exc)
    else:
        raise AssertionError("Expected invalid run name to fail")
