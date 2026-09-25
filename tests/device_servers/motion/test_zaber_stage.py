"""Contract tests for millimetre-only Zaber control without a serial port."""

from types import SimpleNamespace

import pytest
from zaber_motion.binary import CommandCode

from DeviceServers.motion.zaber.stage import ZaberStage


class FakeDevice:
    def __init__(self, *, controller_id=30111, peripheral_id=43021):
        self.values = {
            CommandCode.RETURN_DEVICE_ID: controller_id,
            (CommandCode.RETURN_SETTING, 66): peripheral_id,
            (CommandCode.RETURN_SETTING, 37): 64,
            (CommandCode.RETURN_SETTING, 106): 0,
            (CommandCode.RETURN_SETTING, 44): 1_066_667,
            CommandCode.RETURN_CURRENT_POSITION: 100_000,
            CommandCode.RETURN_STATUS: 0,
        }
        self.calls = []

    def generic_command(self, command, data=0):
        self.calls.append((command, data))
        value = self.values.get((command, data), self.values.get(command))
        return SimpleNamespace(device_address=1, data=value)

    def move_absolute(self, position, **kwargs):
        self.calls.append(("move_absolute", position, kwargs))
        return position

    def home(self, **kwargs):
        self.calls.append(("home", kwargs))
        return 0

    def stop(self, **kwargs):
        self.calls.append(("stop", kwargs))
        return self.values[CommandCode.RETURN_CURRENT_POSITION]


class FakeConnection:
    def __init__(self, device):
        self.device = device
        self.closed = False

    def get_device(self, address):
        assert address == 1
        return self.device

    def close(self):
        self.closed = True


def make_stage(device):
    connection = FakeConnection(device)
    stage = ZaberStage(connection_factory=lambda port, baud_rate: connection)
    return stage, connection


def test_connection_reads_identity_limits_and_position_without_motion():
    device = FakeDevice()
    stage, connection = make_stage(device)

    snapshot = stage.connect()

    assert snapshot.position_mm == pytest.approx(4.7625)
    assert snapshot.minimum_mm == 0
    assert snapshot.maximum_mm == pytest.approx(50.800015875)
    assert snapshot.resolution == 64
    assert all(call[0] not in {"home", "move_absolute", "stop"} for call in device.calls)
    stage.close()
    assert connection.closed


def test_rejects_wrong_peripheral_and_closes_port():
    stage, connection = make_stage(FakeDevice(peripheral_id=99999))

    with pytest.raises(RuntimeError, match="Unexpected Zaber hardware"):
        stage.connect()

    assert connection.closed
    assert not stage.connected


def test_absolute_command_converts_mm_to_native_and_checks_limits():
    device = FakeDevice()
    stage, _ = make_stage(device)
    stage.connect()

    result = stage.move_absolute_mm(12.7)

    assert result == pytest.approx(12.7, abs=0.00005)
    moves = [call for call in device.calls if call[0] == "move_absolute"]
    assert len(moves) == 1
    assert moves[0][1] == round(12.7 / 0.000047625)
    for target in (-0.1, 50.9, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            stage.move_absolute_mm(target)
    assert len([call for call in device.calls if call[0] == "move_absolute"]) == 1


def test_busy_axis_rejects_new_motion():
    device = FakeDevice()
    stage, _ = make_stage(device)
    stage.connect()
    device.values[CommandCode.RETURN_STATUS] = 1

    with pytest.raises(RuntimeError, match="idle"):
        stage.move_absolute_mm(1)
    assert not any(call[0] == "move_absolute" for call in device.calls)


def test_home_is_only_issued_by_explicit_home_method():
    device = FakeDevice()
    stage, _ = make_stage(device)
    stage.connect()
    assert not any(call[0] == "home" for call in device.calls)

    assert stage.home() == 0
    assert len([call for call in device.calls if call[0] == "home"]) == 1
