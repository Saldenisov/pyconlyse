"""Controller-level lifecycle tests with no Tango database or hardware I/O."""

import importlib
import threading
import time

import pytest


class FakeController:
    def __init__(self, **_kwargs):
        self.connected = False
        self.counters = [10, 20, 30, 40]
        self.done = [True] * 4
        self.calls = []
        self.fail_move = False
        self.fail_read = False
        self.fail_connect = False
        self.error = 0

    def connect(self):
        self.calls.append("connect")
        if self.fail_connect:
            raise RuntimeError("reconnect failed")
        self.connected = True
        return "New_Focus 8742 v1.9 10/23/12 SN10001"

    def close(self):
        self.calls.append("close")
        self.connected = False

    def position(self, axis):
        if self.fail_read:
            raise RuntimeError("lost read")
        return self.counters[axis - 1]

    def motion_done(self, axis):
        return self.done[axis - 1]

    def move_relative(self, axis, steps):
        self.calls.append(("PR", axis, steps))
        self.done[axis - 1] = False
        if self.fail_move:
            self.connected = False
            raise RuntimeError("write outcome unknown")

    def move_absolute(self, axis, steps):
        self.calls.append(("PA", axis, steps))
        self.done[axis - 1] = False

    def stop(self, axis):
        self.calls.append(("ST", axis))

    def abort(self):
        self.calls.append("AB")

    def error_code(self):
        return self.error


@pytest.fixture
def rig(monkeypatch):
    module = importlib.import_module("DeviceServers.motion.picomotor.DS_Picomotor8742")
    monkeypatch.setattr(module, "Picomotor8742", FakeController)
    monkeypatch.setattr(
        module.DS_Picomotor8742,
        "set_status",
        lambda self, value: setattr(self, "_status", value),
        raising=False,
    )
    monitor_implementation = module.DS_Picomotor8742._start_monitor
    monkeypatch.setattr(module.DS_Picomotor8742, "_start_monitor", lambda self: None)
    device = module.DS_Picomotor8742()
    device.host = "confirmed-controller.example"
    device.step_limits = [-1000, 1000] * 4
    device.init_device()
    device._real_start_monitor = lambda: monitor_implementation(device)
    return device, device._controller, module


def test_startup_and_reconnect_only_read(rig):
    device, controller, _module = rig
    assert controller.calls == ["connect"]
    assert device.positions_steps() == [10, 20, 30, 40]
    device.Reconnect()
    assert controller.calls == ["connect", "close", "connect"]


def test_move_returns_pending_and_stop_waits_for_all_axes_idle(rig):
    device, controller, module = rig
    device.motion_enabled = True
    device.MoveRelative([2, -5])
    assert controller.calls[-1] == ("PR", 2, -5)
    assert device.get_state() == module.DevState.MOVING
    device.Stop(2)
    device._tick()
    assert device.get_state() == module.DevState.MOVING
    controller.done = [True] * 4
    controller.counters[1] = 18  # An interrupted move need not reach its target.
    device._tick()
    assert device.get_state() == module.DevState.ON
    assert device._active is None


@pytest.mark.parametrize(
    "args", ([0, 10], [5, 10], [1, 0.5], [True, 5], [1, 2**31], [1])
)
def test_invalid_input_sends_no_motion(rig, args):
    device, controller, _module = rig
    device.motion_enabled = True
    with pytest.raises(ValueError):
        device.MoveRelative(args)
    assert controller.calls == ["connect"]


def test_disable_busy_and_limits_block_motion(rig):
    device, controller, _module = rig
    with pytest.raises(RuntimeError, match="motion_enabled"):
        device.MoveRelative([1, 5])
    device.motion_enabled = True
    with pytest.raises(ValueError, match="limits"):
        device.MoveAbsolute([1, 1001])
    controller.done[3] = False
    with pytest.raises(RuntimeError, match="already moving"):
        device.MoveRelative([1, 5])
    assert controller.calls == ["connect"]


def test_missing_limits_fail_before_motion(rig):
    device, controller, _module = rig
    device.motion_enabled = True
    device.step_limits = []
    with pytest.raises(ValueError, match="eight"):
        device.MoveRelative([1, 5])
    assert controller.calls == ["connect"]


def test_lost_move_never_replayed_and_reconnect_preserves_pending_motion(rig):
    device, controller, module = rig
    device.motion_enabled = True
    controller.fail_move = True
    with pytest.raises(RuntimeError, match="unknown"):
        device.MoveRelative([1, 5])
    device._tick()
    assert device.get_state() == module.DevState.FAULT
    device.Reconnect()
    assert device.get_state() == module.DevState.MOVING
    assert device._active[1] is None
    assert controller.calls.count(("PR", 1, 5)) == 1


def test_known_move_blocks_reconnect_and_reinit(rig):
    device, controller, _module = rig
    device.motion_enabled = True
    device.MoveRelative([1, 5])
    with pytest.raises(RuntimeError, match="confirm idle"):
        device.Reconnect()
    with pytest.raises(RuntimeError, match="active"):
        device.init_device()
    assert "close" not in controller.calls


def test_failed_reconnect_keeps_unresolved_move(rig):
    device, controller, module = rig
    device.motion_enabled = True
    controller.fail_move = True
    with pytest.raises(RuntimeError):
        device.MoveRelative([2, 5])
    controller.fail_connect = True
    with pytest.raises(RuntimeError, match="reconnect failed"):
        device.Reconnect()
    assert device._active is not None
    assert device._active[0] == 2
    controller.fail_connect = False
    device.Reconnect()
    assert device.get_state() == module.DevState.MOVING
    assert device._active is not None
    assert device._active[1] is None


def test_external_motion_stop_has_a_confirmation_deadline(rig):
    device, controller, module = rig
    controller.done[2] = False
    device.Stop(3)
    assert device._active is not None
    device._active = (3, None, time.monotonic() - 1)
    device._tick()
    assert controller.calls.count("AB") == 1
    assert device.get_state() == module.DevState.FAULT


def test_timeout_aborts_once_and_latches_fault(rig):
    device, controller, module = rig
    device.motion_enabled = True
    device.MoveRelative([1, 5])
    device._active = (1, 15, time.monotonic() - 1)
    device._tick()
    device._tick()
    assert controller.calls.count("AB") == 1
    assert device.get_state() == module.DevState.FAULT
    with pytest.raises(RuntimeError):
        device.positions_steps()
    assert device._active is not None
    device.Reconnect()
    assert device._active is not None
    assert device.get_state() == module.DevState.MOVING


def test_completion_requires_counter_and_controller_error_check(rig):
    device, controller, module = rig
    device.motion_enabled = True
    device.MoveRelative([1, 5])
    controller.done = [True] * 4
    device._tick()
    assert device.get_state() == module.DevState.FAULT
    assert "differs" in device.last_error()


def test_completion_reads_counter_after_idle_confirmation(rig):
    device, controller, module = rig
    device.motion_enabled = True
    device.MoveRelative([1, 5])
    original_done = controller.motion_done

    def finish_move(axis):
        controller.counters[0] = 15
        controller.done[0] = True
        return original_done(axis)

    controller.motion_done = finish_move
    device._tick()
    assert device.get_state() == module.DevState.ON
    assert device._active is None
    assert device.positions_steps()[0] == 15


def test_delayed_controller_error_latches_fault(rig):
    device, controller, module = rig
    device.motion_enabled = True
    device.MoveRelative([1, 5])
    controller.counters[0] = 15
    controller.done = [True] * 4
    controller.error = 108
    device._tick()
    assert device.get_state() == module.DevState.FAULT
    assert "108" in device.last_error()


def test_read_failure_cannot_return_stale_counter(rig):
    device, controller, module = rig
    controller.fail_read = True
    with pytest.raises(RuntimeError, match="lost read"):
        device.positions_steps()
    controller.fail_read = False
    device._tick()
    assert device.get_state() == module.DevState.FAULT
    cause = device.last_error()
    for _ in range(3):
        with pytest.raises(RuntimeError):
            device.positions_steps()
    assert device.last_error() == cause == "lost read"


def test_abort_is_allowed_with_motion_disabled_and_confirms_idle(rig):
    device, controller, module = rig
    controller.done[2] = False
    device.Abort()
    assert controller.calls[-1] == "AB"
    device._tick()
    assert device.get_state() == module.DevState.MOVING
    controller.done = [True] * 4
    device._tick()
    assert device.get_state() == module.DevState.ON


def test_monitor_restart_uses_a_fresh_stop_event(rig):
    device, _controller, module = rig
    device.poll_interval_s = 0.01
    device._quit.set()
    ticks = threading.Event()
    device._tick = ticks.set
    device._real_start_monitor()
    try:
        assert ticks.wait(1)
    finally:
        device._stop_monitor()
    assert not device._monitor.is_alive()


def test_registration_default_is_pure(capsys, monkeypatch):
    module = importlib.import_module(
        "DeviceServers.motion.picomotor.add_ds_Picomotor8742"
    )
    import sys

    monkeypatch.setitem(sys.modules, "tango", None)
    assert (
        module.main(
            [
                "--device",
                "test/pico/controller",
                "--instance",
                "pico_test",
                "--controller-host",
                "confirmed.example",
                "--server-host",
                "testhost",
            ]
        )
        == 0
    )
    assert '"motion_enabled": false' in capsys.readouterr().out


def test_registration_rejects_existing_server_before_writes(monkeypatch):
    module = importlib.import_module(
        "DeviceServers.motion.picomotor.add_ds_Picomotor8742"
    )
    import sys
    import types

    class FakeDatabase:
        def get_server_list(self, _pattern):
            return ["DS_Picomotor8742/pico_test"]

        def __getattr__(self, name):
            raise AssertionError(f"Database operation reached after conflict: {name}")

    monkeypatch.setitem(
        sys.modules,
        "tango",
        types.SimpleNamespace(
            Database=FakeDatabase,
            DbDevInfo=types.SimpleNamespace,
            DbServerInfo=types.SimpleNamespace,
        ),
    )
    with pytest.raises(RuntimeError, match="Server instance already registered"):
        module.main(
            [
                "--device",
                "test/pico/new_device",
                "--instance",
                "pico_test",
                "--controller-host",
                "confirmed.example",
                "--server-host",
                "testhost",
                "--apply",
            ]
        )
