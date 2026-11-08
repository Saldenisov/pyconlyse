"""Software-only OWIS admission: readiness must not replay initialization."""

from types import SimpleNamespace

import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api


OWIS_DEVICES = [api.OWIS_CONTROLLER_DEVICE, api.OWIS_SAMPLE_DEVICE, api.OWIS_LEGACY_DEVICE]


class Owis:
    def __init__(self, state="ON", position=12.5, timeout=False, fail=False, initialization="SUCCEEDED"):
        self.current_state = state
        self.position = position
        self.timeout = timeout
        self.fail = fail
        self.initialization = initialization
        self.commands = []
        self.timeouts = []

    def state(self):
        return self.current_state

    def set_timeout_millis(self, value):
        self.timeouts.append(value)

    def read_attribute(self, name):
        if name == "initialization_state":
            return SimpleNamespace(value=self.initialization)
        assert name == "pos2"
        return SimpleNamespace(value=self.position)

    def get_attribute_list(self):
        return ["pos2", "initialization_state"]

    def get_command_list(self):
        return ["recover", "Init", "turn_on"]

    def command_inout(self, command):
        self.commands.append(command)
        if command == "Init":
            pytest.fail("OWIS Init must not reset an exported controller")
        if command == "recover":
            self.current_state = "STANDBY"
            self.initialization = "NOT_REQUESTED"
            return "Recovered"
        assert command == "turn_on"
        assert self.timeouts[-1] == 60000
        if self.timeout:
            self.current_state = "INIT"
            self.initialization = "IN_PROGRESS"
            raise RuntimeError("API_DeviceTimedOut: TRANSIENT_CallTimedout")
        self.current_state = "FAULT" if self.fail else "ON"
        self.initialization = "FAILED" if self.fail else "SUCCEEDED"
        return "initialization failed" if self.fail else 0


@pytest.fixture
def attach(monkeypatch):
    def bind(proxy):
        monkeypatch.setattr(api, "_wait_for_device", lambda *_args, **_kwargs: proxy)
        monkeypatch.setattr(api, "_restart_server", lambda *_args, **_kwargs: pytest.fail("no restart expected"))
        return proxy
    return bind


@pytest.mark.parametrize("device", OWIS_DEVICES)
@pytest.mark.parametrize("state", ["ON", "MOVING", "RUNNING"])
def test_repeated_ensure_preserves_running_owis(attach, device, state):
    proxy = attach(Owis(state))
    steps = []
    for _ in range(2):
        assert api._ensure_server(device, steps) is proxy
    assert proxy.commands == []
    assert all(step["status"] == "already running" for step in steps)


@pytest.mark.parametrize("device", OWIS_DEVICES)
@pytest.mark.parametrize("state", ["OFF", "STANDBY"])
def test_connected_cold_owis_is_activated_once_without_init_or_restart(attach, device, state):
    proxy = attach(Owis(state))
    assert api._ensure_server(device, []) is proxy
    assert proxy.commands == ["turn_on"]


@pytest.mark.parametrize("device", OWIS_DEVICES)
def test_faulted_owis_recovers_transport_then_activates_once(attach, device):
    proxy = attach(Owis("FAULT"))
    assert api._ensure_server(device, []) is proxy
    assert proxy.commands == ["recover", "turn_on"]


@pytest.mark.parametrize("state,position", [("INIT", 12.5), ("ON", float("nan")), ("MOVING", float("nan"))])
def test_existing_initialization_or_readback_gap_is_only_observed(attach, monkeypatch, state, position):
    proxy = attach(Owis(state, position))
    observed = []

    def wait(device, **_kwargs):
        observed.append(device)
        proxy.current_state, proxy.position = "ON", 12.5
        return proxy

    monkeypatch.setattr(api, "_wait_for_healthy_device", wait)
    assert api._ensure_server(api.OWIS_CONTROLLER_DEVICE, []) is proxy
    assert observed == [api.OWIS_CONTROLLER_DEVICE]
    assert proxy.commands == []


def test_timed_out_activation_waits_without_replay_or_restart(attach, monkeypatch):
    proxy = attach(Owis("STANDBY", timeout=True))

    def wait(device, **_kwargs):
        assert device == api.OWIS_CONTROLLER_DEVICE
        assert proxy.current_state == "INIT"
        proxy.current_state = "ON"
        proxy.initialization = "SUCCEEDED"
        return proxy

    monkeypatch.setattr(api, "_wait_for_healthy_device", wait)
    assert api._ensure_server(api.OWIS_CONTROLLER_DEVICE, []) is proxy
    assert proxy.commands == ["turn_on"]


@pytest.mark.parametrize("state,timeout", [("INIT", False), ("STANDBY", True)])
def test_unresolved_initialization_reports_unknown_result_without_restart(attach, monkeypatch, state, timeout):
    proxy = attach(Owis(state, timeout=timeout))
    monkeypatch.setattr(api, "_wait_for_healthy_device", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(RuntimeError("readback still unavailable")))
    steps = []
    with pytest.raises(RuntimeError, match="no restart or initialization replay"):
        api._ensure_server(api.OWIS_CONTROLLER_DEVICE, steps)
    assert proxy.commands == (["turn_on"] if timeout else [])
    assert steps[-1]["status"] == "failed"


@pytest.mark.parametrize("device", OWIS_DEVICES)
def test_restart_rechecks_recovered_owis_before_touching_starter(monkeypatch, device):
    proxy = Owis()
    monkeypatch.setattr(api, "_wait_for_device", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(api, "_astor", lambda *_args: pytest.fail("healthy server must be retained"))
    assert api._restart_server(device, api.VD2_SERVERS[device], []) is proxy
    assert proxy.commands == []


def test_definite_activation_failure_retains_the_running_server(attach, monkeypatch):
    proxy = attach(Owis("STANDBY", fail=True))
    with pytest.raises(RuntimeError, match="server retained"):
        api._ensure_server(api.OWIS_CONTROLLER_DEVICE, [])
    assert proxy.commands == ["turn_on"]


@pytest.mark.parametrize("initialization", ["UNKNOWN", "NOT_REQUESTED", "PENDING", "IN_PROGRESS", "FAILED"])
def test_on_with_unfinished_lifecycle_does_not_claim_readiness_or_reinitialize(attach, monkeypatch, initialization):
    proxy = attach(Owis("ON", initialization=initialization))
    assert not api._is_healthy_device(proxy, api.OWIS_CONTROLLER_DEVICE)

    def wait(device, **_kwargs):
        proxy.initialization = "SUCCEEDED"
        return proxy

    monkeypatch.setattr(api, "_wait_for_healthy_device", wait)
    assert api._ensure_server(api.OWIS_CONTROLLER_DEVICE, []) is proxy
    assert proxy.commands == []
