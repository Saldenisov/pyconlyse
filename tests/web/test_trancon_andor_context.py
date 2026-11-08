"""Pending camera replies belong only to the active local acquisition context."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import zlib

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
sys.path.insert(0, str(BACKEND))
import pump_probe_v0_api as api


class Camera:
    def __init__(self):
        self.commands = []
        self.next_order = 11
        self.ready = set()
        rows = [[500, 600], [10, 20], [20, 40], [30, 40], [40, 60]]
        self.payload = repr(zlib.compress(np.asarray(rows, dtype=np.float32).tobytes()))

    def state(self):
        return "ON"

    def read_attribute(self, name):
        assert name == "wavelengths_axis"
        return SimpleNamespace(value=[500, 600])

    def command_inout(self, name, argument=None):
        self.commands.append((name, argument))
        if name == "start_grabbing":
            return None
        if name == "register_order":
            assert argument == [api.SPECTROMETER_BURST]
            order = self.next_order
            self.next_order += 1
            return order
        if name == "is_order_ready":
            return argument in self.ready
        if name == "give_order":
            assert argument in self.ready
            return self.payload
        pytest.fail(f"Unexpected camera command: {name}")


@pytest.fixture
def acquisition(monkeypatch):
    monkeypatch.setattr(api, "PIXELS", 2)
    controller = api.PumpProbeV0Controller()
    controller._settings["point_count"] = 2
    controller._reset_locked()
    controller._hardware_config["control_mode"] = "tango"
    camera = Camera()
    monkeypatch.setattr(api, "_tango_proxy", lambda *_args, **_kwargs: camera)
    return controller, camera


def sample_state(controller):
    return deepcopy((controller._wavelengths, controller._last_spectra,
                     controller._spectrometer_frames, controller._current_index,
                     controller._heatmap, controller._live_od))


@pytest.mark.parametrize("action", ["stop", "realtime_off"])
def test_stop_or_realtime_off_discards_order_and_late_reply(acquisition, action):
    controller, camera = acquisition
    controller._running = action == "stop"
    controller._real_time = action == "realtime_off"
    controller.state(advance_active=True)
    old_order = controller._andor_order
    assert old_order == 11
    camera.ready.add(old_order)
    calls = list(camera.commands)

    if action == "stop":
        controller.set_running(False)
    else:
        controller.set_real_time(False)

    assert controller._andor_order is None
    assert camera.commands == calls  # Invalidation sends no remote cancellation.
    paused = sample_state(controller)
    controller.state(advance_active=True)
    assert sample_state(controller) == paused
    assert camera.commands == calls

    controller.set_real_time(True)
    assert controller._andor_order == 12
    controller.state(advance_active=True)
    assert sample_state(controller) == paused
    assert ("give_order", old_order) not in camera.commands
    assert ("is_order_ready", old_order) not in camera.commands[len(calls):]


@pytest.mark.parametrize("action", ["reset_locked", "reset", "configure"])
def test_reset_or_configure_cannot_reuse_order_at_new_scan_context(acquisition, action):
    controller, camera = acquisition
    controller._real_time = True
    controller.state(advance_active=True)
    old_order = controller._andor_order
    camera.ready.add(old_order)
    calls = list(camera.commands)

    if action == "reset_locked":
        with controller._lock:
            controller._reset_locked()
    elif action == "reset":
        controller.reset()
    else:
        controller.configure({"point_count": 2, "delay_step_ps": 2,
                              "hardware_config": {"andor_device": "test/camera/new"}})
        assert controller._delays == [-25.0, -23.0]

    assert controller._andor_order is None
    assert camera.commands == calls
    new_context = sample_state(controller)
    if not controller._real_time:
        controller.set_real_time(True)
    else:
        controller.state(advance_active=True)
    assert controller._andor_order == 12
    assert sample_state(controller) == new_context
    assert ("give_order", old_order) not in camera.commands
    assert ("is_order_ready", old_order) not in camera.commands[len(calls):]


def test_active_context_retains_pending_order_and_commits_its_complete_reply(acquisition):
    controller, camera = acquisition
    controller._real_time = True
    controller.state(advance_active=True)
    pending = controller._andor_order
    unchanged = sample_state(controller)

    controller.state(advance_active=True)
    assert controller._andor_order == pending
    assert sample_state(controller) == unchanged
    assert sum(command == "register_order" for command, _ in camera.commands) == 1

    camera.ready.add(pending)
    controller.state(advance_active=True)
    assert controller._andor_order is None
    assert controller._wavelengths == [500.0, 600.0]
    assert controller._last_spectra["reference"] == [20.0, 30.0]
    assert controller._last_spectra["signal"] == [30.0, 50.0]
    assert controller._spectrometer_frames == 2
    assert controller._current_index == 0
    assert camera.commands[-1] == ("give_order", pending)


def test_passive_state_preserves_active_pending_context_without_camera_poll(acquisition):
    controller, camera = acquisition
    controller._real_time = True
    controller.state(advance_active=True)
    pending = controller._andor_order
    calls = list(camera.commands)
    controller.state()
    assert controller._andor_order == pending
    assert camera.commands == calls


def test_realtime_off_during_run_keeps_run_active_but_replaces_its_order(acquisition):
    controller, camera = acquisition
    controller._running = True
    controller._real_time = True
    controller.state(advance_active=True)
    old_order = controller._andor_order
    camera.ready.add(old_order)
    calls = list(camera.commands)

    controller.set_real_time(False)
    assert controller._running is True
    assert controller._real_time is False
    assert controller._andor_order is None
    assert camera.commands == calls
    current_point = sample_state(controller)

    controller.state(advance_active=True)
    assert controller._andor_order == 12
    assert sample_state(controller) == current_point
    assert ("give_order", old_order) not in camera.commands
