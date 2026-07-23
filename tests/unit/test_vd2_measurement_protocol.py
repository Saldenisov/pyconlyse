import sys
from pathlib import Path


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


def test_phase_protocol_writes_noise_his_after_sequence():
    proxy = FakeProxy()
    protocol = Vd2MeasurementProtocol(lambda: proxy)

    state = protocol.start(
        phase="brew",
        frames_per_his=25,
        output_root=r"E:\DATA_VD2",
        run_name="LiCl_001",
    )
    protocol.wait(1)

    assert state["phase"] == "BREW"
    assert state["his_path"] == r"E:\DATA_VD2\LiCl_001\NOISE.his"
    assert protocol.status()["status"] == "completed"
    assert ("write", "sequence_loops", "25") in proxy.calls
    assert ("command", "StartSequence", None) in proxy.calls
    assert ("command", "WaitForIdle", None) in proxy.calls
    assert ("command", "SaveCurrentSequence", r"E:\DATA_VD2\LiCl_001\NOISE.his") in proxy.calls


def test_phase_protocol_rejects_invalid_run_name():
    protocol = Vd2MeasurementProtocol(FakeProxy)

    try:
        protocol.start(phase="BASE", frames_per_his=1, run_name="../unsafe")
    except Vd2ProtocolError as exc:
        assert "Run name" in str(exc)
    else:
        raise AssertionError("Expected invalid run name to fail")
