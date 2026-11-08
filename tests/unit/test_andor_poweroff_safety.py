"""No real SDK: verify native warm-up semantics and fail-closed readback."""

import ast
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

import pytest

from DeviceServers.cameras.andor.poweroff_safety import begin_safe_poweroff, read_poweroff_safety


class Camera:
    def __init__(self, temperature=-50):
        self.temperature = temperature
        self.cooler = True
        self.acquiring = True
        self.calls = []
        self.stop_failed = False
        self.close_failed = False

    def get_temperature(self):
        return self.temperature

    def get_temperature_status(self):
        return "off" if not self.cooler else "stabilized"

    def is_cooler_on(self):
        return self.cooler

    def acquisition_in_progress(self):
        return self.acquiring

    def stop_acquisition(self):
        self.calls.append("stop_acquisition")
        if not self.stop_failed:
            self.acquiring = False

    def set_cooler(self, enabled):
        self.calls.append(("set_cooler", enabled))
        self.cooler = enabled

    def close(self):
        self.calls.append("close")
        if self.close_failed:
            raise RuntimeError("SDK close failed")


def test_warmup_stops_acquisition_and_disables_cooler_but_never_closes_camera():
    camera = Camera()
    status = begin_safe_poweroff(camera)
    assert camera.calls == ["stop_acquisition", ("set_cooler", False)]
    assert status["temperature_c"] == -50
    assert status["fresh_sdk_readback"] is True
    assert not status["cooler_on"] and not status["acquisition_active"]


def test_failed_stop_preserves_cooler_and_sdk():
    camera = Camera()
    camera.stop_failed = True
    with pytest.raises(RuntimeError, match="did not stop"):
        begin_safe_poweroff(camera)
    assert camera.calls == ["stop_acquisition"]
    assert camera.cooler is True


@pytest.mark.parametrize("temperature", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_temperature_is_not_a_shutdown_certificate(temperature):
    with pytest.raises(RuntimeError, match="not finite"):
        read_poweroff_safety(Camera(temperature))


def test_missing_sdk_does_not_open_or_guess_camera_temperature():
    for function in (begin_safe_poweroff, read_poweroff_safety):
        with pytest.raises(RuntimeError, match="SDK handle is absent"):
            function(None)


def native_release(camera):
    # Exercise the actual server method without importing a Tango server or DLL.
    source = Path(__file__).resolve().parents[2] / "DeviceServers/cameras/andor/DS_ANDOR_CCD.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    method = next(node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "DS_ANDOR_CCD"
                  for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "ReleaseAfterWarmup")
    method.decorator_list = []
    namespace = {"read_poweroff_safety": read_poweroff_safety, "DevState": SimpleNamespace(OFF="OFF")}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    lock = RLock()
    device = SimpleNamespace(camera=camera, _get_lifecycle_lock=lambda: lock,
                             set_state=lambda state: setattr(device, "state", state))
    device.state = "ON"
    return namespace["ReleaseAfterWarmup"], device


@pytest.mark.parametrize("temperature,cooling,acquiring", [(-1, False, False), (2, True, False), (2, False, True)])
def test_actual_release_command_never_closes_cold_or_active_camera(temperature, cooling, acquiring):
    camera = Camera(temperature)
    camera.cooler, camera.acquiring = cooling, acquiring
    method, device = native_release(camera)
    with pytest.raises(RuntimeError, match="remains cold"):
        method(device)
    assert not camera.calls and device.camera is camera and device.state == "ON"


def test_actual_release_command_checks_warm_sdk_before_closing_and_confirming_off():
    camera = Camera(1)
    camera.cooler = camera.acquiring = False
    method, device = native_release(camera)
    assert "verified warm-up" in method(device)
    assert camera.calls == ["close"]
    assert device.camera is None and device.state == "OFF"


def test_sdk_close_error_is_not_swallowed_or_misreported_as_off():
    camera = Camera(1)
    camera.cooler = camera.acquiring = False
    camera.close_failed = True
    method, device = native_release(camera)
    with pytest.raises(RuntimeError, match="SDK close failed"):
        method(device)
    assert device.camera is camera and device.state == "ON"
