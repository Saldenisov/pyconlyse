"""Prepare distinguishes a running process from initialized hardware."""
from types import SimpleNamespace
import pytest
from tests.web.test_pump_probe_vd2_api import vd2_api_module as api

DEVICES = [api.DG645_DEVICE, api.KYMERA_DEVICE, api.OWIS_CONTROLLER_DEVICE]

class Instrument:
    def __init__(self, device, state="ON", error=None):
        self.device, self.current_state, self.error = device, state, error
        self.commands = []
    def state(self):
        return self.current_state
    def set_timeout_millis(self, timeout):
        pass
    def read_attribute(self, name):
        return SimpleNamespace(value=2 if name == "grating" else 12.5)
    def get_command_list(self):
        return ["Init", "recover", "turn_on", "scpi_query"]
    def command_inout(self, command, argument=None):
        self.commands.append((command, argument))
        if command == "scpi_query":
            return "SRS,DG645,123,1.0"
        assert command != "Init", "Do not replay process/device Init"
        if self.error:
            raise RuntimeError(self.error)
        self.current_state = "ON"
        return 0

@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("state", ["OFF", "STANDBY"])
def test_exported_cold_equipment_initializes_once_without_process_restart(monkeypatch, device, state):
    proxy = Instrument(device, state)
    monkeypatch.setattr(api, "_wait_for_device", lambda *_a, **_k: proxy)
    monkeypatch.setattr(api, "_restart_server", lambda *_a, **_k: pytest.fail("existing server retained"))
    assert api._ensure_server(device, []) is proxy
    mutations = [name for name, _ in proxy.commands if name != "scpi_query"]
    assert mutations == ["turn_on"]

@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("error", ["initialization failed", "API_DeviceTimedOut: TRANSIENT_CallTimedout"])
def test_failed_or_timed_out_initialization_does_not_restart_process(monkeypatch, device, error):
    proxy = Instrument(device, "STANDBY", error)
    monkeypatch.setattr(api, "_wait_for_device", lambda *_a, **_k: proxy)
    monkeypatch.setattr(api, "_wait_for_healthy_device", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("readback unavailable")))
    monkeypatch.setattr(api, "_observe_kymera_startup", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("readback unavailable")))
    monkeypatch.setattr(api, "_restart_server", lambda *_a, **_k: pytest.fail("no restart or replay"))
    with pytest.raises(RuntimeError):
        api._ensure_server(device, [])
    assert proxy.commands == [("turn_on", None)]

@pytest.mark.parametrize("device", DEVICES)
def test_running_but_unreachable_server_is_observed_not_restarted(monkeypatch, device):
    calls = []
    class Starter:
        def command_inout(self, command, argument):
            calls.append((command, argument))
            assert command == "DevGetRunningServers"
            return [api.VD2_SERVERS[device]]
    monkeypatch.setattr(api, "_astor", lambda *_a: Starter())
    monkeypatch.setattr(api, "_wait_for_device", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("API_DeviceTimedOut")))
    monkeypatch.setattr(api, "_wait_for_healthy_device", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("controller unreachable")))
    steps = []
    with pytest.raises(RuntimeError, match="controller unreachable"):
        api._ensure_server(device, steps)
    assert calls and all(name == "DevGetRunningServers" for name, _ in calls)

@pytest.mark.parametrize("device", DEVICES)
def test_absent_process_is_started_once_and_hardware_initialized(monkeypatch, device):
    calls = []
    proxy = Instrument(device, "STANDBY")
    class Starter:
        def command_inout(self, command, argument):
            calls.append((command, argument))
            if command == "DevGetRunningServers":
                return []
            assert (command, argument) == ("DevStart", api.VD2_SERVERS[device])
    def exported(*_a, **_k):
        if not any(name == "DevStart" for name, _ in calls):
            raise RuntimeError("not exported")
        return proxy
    monkeypatch.setattr(api, "_astor", lambda *_a: Starter())
    monkeypatch.setattr(api, "_wait_for_device", exported)
    monkeypatch.setattr(api, "_wait_for_healthy_device", lambda *_a, **_k: proxy)
    assert api._ensure_server(device, []) is proxy
    assert calls.count(("DevStart", api.VD2_SERVERS[device])) == 1
    assert not any(name == "DevStop" for name, _ in calls)
    assert proxy.commands == ([("turn_on", None), ("scpi_query", "*IDN?")] if device == api.DG645_DEVICE else [("turn_on", None)])
