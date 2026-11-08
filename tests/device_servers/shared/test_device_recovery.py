from types import SimpleNamespace

import pytest

from DeviceServers.shared.device_recovery import (
    DeviceRecoveryError,
    get_power_cycle_config,
    power_cycle_device,
    restart_device_server,
)


class FakeDatabase:
    def __init__(self, properties=None):
        self.properties = properties or {}

    def get_device_property(self, _device_name, names):
        return {name: self.properties.get(name, []) for name in names}

    def get_device_info(self, _device_name):
        return SimpleNamespace(ds_full_name="DS_Test/one")

    def get_device_exported(self, _pattern):
        return ["tango/admin/test-host"]


class FakeStarter:
    def __init__(self, running=True):
        self.running = {"DS_Test/one"} if running else set()
        self.stopped = set() if running else {"DS_Test/one"}
        self.calls = []

    def set_timeout_millis(self, _timeout):
        pass

    def command_inout(self, command, argument):
        self.calls.append((command, argument))
        if command == "DevGetRunningServers":
            return sorted(self.running)
        if command == "DevGetStopServers":
            return sorted(self.stopped)
        if command == "DevStop":
            self.running.discard(argument)
            self.stopped.add(argument)
            return None
        if command == "DevStart":
            self.stopped.discard(argument)
            self.running.add(argument)
            return None
        raise AssertionError(command)


class FakeAttribute:
    def __init__(self, value):
        self.value = value


class FakePdu:
    def __init__(self, states):
        self.ids = [1, 2, 3]
        self.states = list(states)
        self.requests = []

    def set_timeout_millis(self, _timeout):
        pass

    def read_attribute(self, name):
        return FakeAttribute(list(getattr(self, name)))

    def command_inout(self, command, requested):
        assert command == "set_channels_states"
        self.requests.append(list(requested))
        self.states = list(requested)


class RestoreFailingPdu(FakePdu):
    def command_inout(self, command, requested):
        if requested[1] == 1:
            raise RuntimeError("PDU restore transport failed")
        super().command_inout(command, requested)


def test_power_cycle_config_requires_explicit_valid_mapping():
    configured = FakeDatabase(
        {
            "power_dependency_device": ["manip/V0/PDU_VO"],
            "power_dependency_output_id": ["3"],
            "power_on_settle_seconds": ["6.5"],
        }
    )
    config = get_power_cycle_config("test/device/one", database=configured)
    assert config.pdu_device == "manip/V0/PDU_VO"
    assert config.output_id == 3
    assert config.off_seconds == 3.0
    assert config.settle_seconds == 6.5

    assert get_power_cycle_config(
        "test/device/one", database=FakeDatabase()
    ) is None


def test_restart_uses_graceful_starter_stop_then_start_without_hard_kill():
    starter = FakeStarter(running=True)
    result = restart_device_server(
        "test/device/one",
        database=FakeDatabase(),
        proxy_factory=lambda _name: starter,
        sleeper=lambda _seconds: None,
    )

    mutation_calls = [
        call for call in starter.calls if call[0] in {"DevStop", "DevStart", "HardKillServer"}
    ]
    assert mutation_calls == [
        ("DevStop", "DS_Test/one"),
        ("DevStart", "DS_Test/one"),
    ]
    assert result["starter"] == "tango/admin/test-host"


def test_restart_starts_a_server_that_is_already_stopped():
    starter = FakeStarter(running=False)
    restart_device_server(
        "test/device/one",
        database=FakeDatabase(),
        proxy_factory=lambda _name: starter,
        sleeper=lambda _seconds: None,
    )
    assert ("DevStop", "DS_Test/one") not in starter.calls
    assert ("DevStart", "DS_Test/one") in starter.calls


def test_power_cycle_changes_only_configured_output_and_confirms_restore():
    pdu = FakePdu([1, 1, 0])
    sleeps = []
    config = get_power_cycle_config(
        "test/device/one",
        database=FakeDatabase(
            {
                "power_dependency_device": ["manip/V0/PDU_VO"],
                "power_dependency_output_id": ["2"],
                "power_on_settle_seconds": ["5"],
            }
        ),
    )

    result = power_cycle_device(
        "test/device/one",
        config=config,
        proxy_factory=lambda _name: pdu,
        sleeper=sleeps.append,
    )

    assert pdu.requests == [[1, 0, 0], [1, 1, 0]]
    assert pdu.states == [1, 1, 0]
    assert sleeps == [3.0, 5.0]
    assert result["output_id"] == 2


def test_power_cycle_does_not_turn_on_an_already_off_output():
    pdu = FakePdu([1, 0, 1])
    config = get_power_cycle_config(
        "test/device/one",
        database=FakeDatabase(
            {
                "power_dependency_device": ["manip/V0/PDU_VO"],
                "power_dependency_output_id": ["2"],
            }
        ),
    )

    with pytest.raises(DeviceRecoveryError, match="already OFF"):
        power_cycle_device(
            "test/device/one",
            config=config,
            proxy_factory=lambda _name: pdu,
            sleeper=lambda _seconds: None,
        )
    assert pdu.requests == []


def test_power_cycle_reports_when_emergency_restore_also_fails():
    pdu = RestoreFailingPdu([1, 1, 0])
    config = get_power_cycle_config(
        "test/device/one",
        database=FakeDatabase(
            {
                "power_dependency_device": ["manip/V0/PDU_VO"],
                "power_dependency_output_id": ["2"],
            }
        ),
    )

    with pytest.raises(DeviceRecoveryError, match="output may still be OFF"):
        power_cycle_device(
            "test/device/one",
            config=config,
            proxy_factory=lambda _name: pdu,
            sleeper=lambda _seconds: None,
        )
    assert pdu.states == [1, 0, 0]
