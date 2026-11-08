"""Cold power restoration must activate once after transport reconnects."""

from types import SimpleNamespace

import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from tests.web.test_vd2_owis_recovery import Owis


class ColdKymera:
    def __init__(self, delayed=False):
        self.current_state = "OFF"
        self.delayed = delayed
        self.commands = []
        self.timeouts = []
        self.observations = 0

    def set_timeout_millis(self, value):
        self.timeouts.append(value)

    def get_command_list(self):
        return ["turn_on"]

    def state(self):
        if self.current_state == "INIT":
            self.observations += 1
            if self.observations == 1:
                raise RuntimeError("IMP_LIMIT / API_CommunicationFailed")
            if self.observations >= 3:
                self.current_state = "ON"
        return self.current_state

    def read_attribute(self, name):
        assert name == "grating"
        return SimpleNamespace(value=2)

    def command_inout(self, name):
        assert name == "turn_on"
        self.commands.append(name)
        self.current_state = "INIT" if self.delayed else "ON"
        if self.delayed:
            raise RuntimeError("API_DeviceTimedOut: TRANSIENT_CallTimedout")


@pytest.mark.parametrize("delayed", [False, True])
def test_kymera_cold_activation_has_its_own_budget_and_never_replays_after_timeout(monkeypatch, delayed):
    proxy = ColdKymera(delayed)
    monkeypatch.setattr(api, "_wait_for_device", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(api, "DeviceProxy", lambda device: proxy if device == api.KYMERA_DEVICE else pytest.fail(device))
    monkeypatch.setattr(api.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(api, "_restart_server", lambda *_args: pytest.fail("No process restart for pending SDK open"))
    assert api._ensure_server(api.KYMERA_DEVICE, []) is proxy
    assert proxy.commands == ["turn_on"]
    assert 240000 in proxy.timeouts
    if delayed:
        assert proxy.observations == 3
        assert max(proxy.timeouts[1:]) <= 2000


def test_unresolved_kymera_observation_is_bounded_and_keeps_native_error_without_activation(monkeypatch):
    from itertools import count
    proxy = ColdKymera()
    proxy.state = lambda: (_ for _ in ()).throw(RuntimeError("IMP_LIMIT / API_CommunicationFailed"))
    monkeypatch.setattr(api, "DeviceProxy", lambda _: proxy)
    monkeypatch.setattr(api.time, "sleep", lambda *_args: None)
    clock = count(0, 1)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(clock))
    with pytest.raises(RuntimeError, match="no activation replay.*IMP_LIMIT"):
        api._observe_kymera_startup([], timeout_s=8)
    assert proxy.commands == []


class Generator:
    def __init__(self, state="STANDBY", timeout=False):
        self.current_state = state
        self.timeout = timeout
        self.commands = []

    def state(self):
        return self.current_state

    def set_timeout_millis(self, _value):
        pass

    def get_command_list(self):
        return ["turn_on", "Init", "recover"]

    def command_inout(self, command, argument=None):
        self.commands.append((command, argument))
        if command == "scpi_query":
            assert argument == "*IDN?"
            return "Stanford Research Systems,DG645,synthetic,1.0"
        assert command == "turn_on"
        self.current_state = "INIT" if self.timeout else "ON"
        if self.timeout:
            raise RuntimeError("API_DeviceTimedOut: TRANSIENT_CallTimedout")


def transient_transport(monkeypatch, proxy):
    waits = []

    def wait(device, timeout_s):
        assert device == api.DG645_DEVICE
        waits.append(timeout_s)
        if len(waits) == 1:
            raise RuntimeError("IMP_LIMIT / API_CommunicationFailed")
        return proxy

    class Starter:
        def command_inout(self, command, argument):
            assert (command, argument) == ("DevGetRunningServers", True)
            return [api.VD2_SERVERS[api.DG645_DEVICE]]

    monkeypatch.setattr(api, "_wait_for_device", wait)
    monkeypatch.setattr(api, "_astor", lambda *_args: Starter())
    monkeypatch.setattr(api, "_restart_server", lambda *_args: pytest.fail("No process transition after reconnect"))
    return waits


@pytest.mark.parametrize("state", ["OFF", "STANDBY"])
def test_generator_started_before_power_is_activated_once_after_transport_returns(monkeypatch, state):
    proxy = Generator(state)
    waits = transient_transport(monkeypatch, proxy)
    steps = []
    assert api._ensure_server(api.DG645_DEVICE, steps) is proxy
    assert waits == [2.0, 20.0]
    assert proxy.commands == [("turn_on", None), ("scpi_query", "*IDN?")]
    assert steps[-1]["status"] == "recovered"


def test_reconnected_operational_generator_preserves_settings(monkeypatch):
    proxy = Generator("ON")
    transient_transport(monkeypatch, proxy)
    assert api._ensure_server(api.DG645_DEVICE, []) is proxy
    assert proxy.commands == [("scpi_query", "*IDN?")]


def test_reconnected_initializing_generator_is_only_observed(monkeypatch):
    proxy = Generator("INIT")
    transient_transport(monkeypatch, proxy)
    observed = []
    monkeypatch.setattr(api, "_wait_for_healthy_device", lambda device: observed.append(device) or proxy)
    assert api._ensure_server(api.DG645_DEVICE, []) is proxy
    assert observed == [api.DG645_DEVICE]
    assert proxy.commands == []


def test_reconnected_generator_activation_timeout_never_replays_or_restarts(monkeypatch):
    proxy = Generator(timeout=True)
    transient_transport(monkeypatch, proxy)

    def unresolved(_device):
        raise RuntimeError("readiness remains unknown")

    monkeypatch.setattr(api, "_wait_for_healthy_device", unresolved)
    with pytest.raises(RuntimeError, match="readiness remains unknown"):
        api._ensure_server(api.DG645_DEVICE, [])
    assert proxy.commands == [("turn_on", None)]


def test_persistent_transport_failure_stays_bounded_without_activation(monkeypatch):
    waits = []

    def offline(_device, timeout_s):
        waits.append(timeout_s)
        raise RuntimeError("transport offline")

    monkeypatch.setattr(api, "_wait_for_device", offline)
    monkeypatch.setattr(api, "_restart_server", lambda *_args: (_ for _ in ()).throw(RuntimeError("server retained")))
    monkeypatch.setattr(api, "_recover_retained_instrument", lambda *_args: pytest.fail("No activation without transport"))
    with pytest.raises(RuntimeError, match="server retained"):
        api._ensure_server(api.DG645_DEVICE, [])
    assert waits == [2.0, 20.0]


def test_absent_generator_server_does_not_spend_grace_period_waiting_for_transport(monkeypatch):
    waits = []
    proxy = Generator("ON")

    def absent(_device, timeout_s):
        waits.append(timeout_s)
        raise RuntimeError("API_DeviceNotExported")

    class Starter:
        def command_inout(self, command, argument):
            assert (command, argument) == ("DevGetRunningServers", True)
            return []

    monkeypatch.setattr(api, "_astor", lambda *_args: Starter())
    monkeypatch.setattr(api, "_wait_for_device", absent)
    monkeypatch.setattr(api, "_restart_server", lambda *_args: proxy)
    assert api._ensure_server(api.DG645_DEVICE, []) is proxy
    assert waits == [2.0]
    assert proxy.commands == []


def test_failed_owis_activation_keeps_native_reason_in_preparation_error(monkeypatch):
    class FailedAxis(Owis):
        def get_attribute_list(self):
            return super().get_attribute_list() + ["hardware_lifecycle_status"]

        def read_attribute(self, name):
            if name == "hardware_lifecycle_status":
                return SimpleNamespace(value="axis 4 set_target_mode to ABS: communication error")
            return super().read_attribute(name)

    proxy = FailedAxis("STANDBY", fail=True)
    monkeypatch.setattr(api, "_wait_for_device", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(api, "_restart_server", lambda *_args: pytest.fail("No process restart"))
    steps = []
    with pytest.raises(RuntimeError, match="axis 4 set_target_mode to ABS: communication error"):
        api._ensure_server(api.OWIS_LEGACY_DEVICE, steps)
    assert proxy.commands == ["turn_on"]
    assert "initialization_state=FAILED" in steps[-1]["detail"]


def test_missing_diagnostic_attribute_does_not_replace_readiness_failure(monkeypatch):
    class FailedDiagnostic(Owis):
        def get_attribute_list(self):
            raise RuntimeError("attribute discovery unavailable")

    proxy = FailedDiagnostic("STANDBY", fail=True)
    monkeypatch.setattr(api, "_wait_for_device", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(api, "_restart_server", lambda *_args: pytest.fail("No process restart"))
    with pytest.raises(RuntimeError, match="server retained"):
        api._ensure_server(api.OWIS_LEGACY_DEVICE, [])
    assert proxy.commands == ["turn_on"]
