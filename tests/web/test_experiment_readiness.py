"""Preparation must observe Starter transitions instead of relying on delays."""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import experiment_readiness as readiness


@pytest.mark.parametrize("healthy", [True, False])
def test_start_only_mode_never_stops_an_existing_server(healthy):
    calls = []
    class Starter:
        def command_inout(self, command, argument):
            calls.append((command, argument))
            assert command == "DevGetRunningServers"
            return ["server"]
    def observe():
        if not healthy:
            raise RuntimeError("hardware not ready; server retained")
        return "verified"
    if healthy:
        assert readiness.start_managed_server(Starter(), "server", observe, restart_existing=False) == "verified"
    else:
        with pytest.raises(RuntimeError, match="server retained"):
            readiness.start_managed_server(Starter(), "server", observe, restart_existing=False)
    assert calls == [("DevGetRunningServers", True)]


def test_start_race_observes_new_owner_without_replaying_initialization():
    calls = []
    class Starter:
        running = False
        def command_inout(self, command, argument):
            calls.append(command)
            if command == "DevGetRunningServers":
                return ["server"] if self.running else []
            assert command == "DevStart"
            self.running = True
            raise RuntimeError("ALREADY_RUNNING")
    assert readiness.start_managed_server(
        Starter(), "server", lambda: pytest.fail("Do not initialize another owner's server"),
        restart_existing=False, observe_existing=lambda: "observed",
    ) == "observed"
    assert calls == ["DevGetRunningServers", "DevStart", "DevGetRunningServers"]


def test_start_waits_until_starter_confirms_previous_process_stopped(monkeypatch):
    calls = []

    class Starter:
        remaining = 3
        stopping = False

        def command_inout(self, name, argument):
            calls.append(name)
            if name == "DevGetRunningServers":
                if self.stopping:
                    self.remaining -= 1
                return ["DS_DG645/1"] if self.remaining > 0 else []
            if name == "DevStop":
                self.stopping = True
            if name == "DevStart":
                assert self.remaining == 0

    monkeypatch.setattr(readiness.time, "sleep", lambda _seconds: None)
    assert readiness.start_managed_server(Starter(), "DS_DG645/1", lambda: "hardware ready") == "hardware ready"
    assert calls.count("DevStop") == 1
    assert calls.count("DevStart") == 1
    assert calls.index("DevStart") > calls.index("DevStop") + 2


def test_stop_timeout_does_not_attempt_start_or_force_kill(monkeypatch):
    calls = []

    class Starter:
        def command_inout(self, name, argument):
            calls.append(name)
            return ["DS_DG645/1"] if name == "DevGetRunningServers" else None

    ticks = iter([0.0, 26.0])
    monkeypatch.setattr(readiness.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="did not stop"):
        readiness.start_managed_server(Starter(), "DS_DG645/1", lambda: None)
    assert "DevStart" not in calls
    assert "HardKillServer" not in calls


@pytest.mark.parametrize("error", ["ALREADY_RUNNING", "server is already running"])
def test_already_running_requires_actual_hardware_readiness(error):
    class Starter:
        started = False

        def command_inout(self, name, argument):
            if name == "DevGetRunningServers":
                return ["server"] if self.started else []
            self.started = True
            raise RuntimeError(error)

    assert readiness.start_managed_server(Starter(), "server", lambda: "verified") == "verified"
    with pytest.raises(RuntimeError, match="instrument offline"):
        readiness.start_managed_server(
            Starter(), "server", lambda: (_ for _ in ()).throw(RuntimeError("instrument offline"))
        )


def test_sdk_stop_waits_for_all_servers_inventory(monkeypatch):
    calls = []

    class Starter:
        remaining = 2

        def command_inout(self, name, argument):
            calls.append((name, argument))
            if name == "DevGetRunningServers":
                assert argument is True
                self.remaining -= 1
                return ["Kymera/2"] if self.remaining else []

    monkeypatch.setattr(readiness.time, "sleep", lambda _seconds: None)
    readiness.stop_managed_server(Starter(), "Kymera/2")
    assert calls == [("DevStop", "Kymera/2"), ("DevGetRunningServers", True), ("DevGetRunningServers", True)]


def test_sdk_stop_timeout_does_not_start_another_owner(monkeypatch):
    calls = []

    class Starter:
        def command_inout(self, name, argument):
            calls.append(name)
            return ["Kymera/2"] if name == "DevGetRunningServers" else None

    ticks = iter([0.0, 26.0])
    monkeypatch.setattr(readiness.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="SDK ownership was not released"):
        readiness.stop_managed_server(Starter(), "Kymera/2")
    assert calls == ["DevStop", "DevGetRunningServers"]


def test_timed_out_recovery_is_not_followed_by_another_mutation():
    calls = []

    class Device:
        def get_command_list(self):
            return ["turn_on", "Init"]

        def command_inout(self, command):
            calls.append(command)
            raise RuntimeError("API_DeviceTimedOut")

    ready, errors = readiness.recover_device(Device(), lambda _: False, ("turn_on", "Init"))
    assert not ready
    assert len(errors) == 1
    assert calls == ["turn_on"]


@pytest.mark.parametrize("still_running", [False, True])
def test_unexported_server_stop_requires_confirmed_process_exit(monkeypatch, still_running):
    class Starter:
        def command_inout(self, name, argument):
            if name == "DevStop":
                raise RuntimeError("API_DeviceNotExported")
            assert (name, argument) == ("DevGetRunningServers", True)
            return ["Kymera/2"] if still_running else []

    ticks = iter([0.0, 26.0])
    monkeypatch.setattr(readiness.time, "monotonic", lambda: next(ticks))
    if still_running:
        with pytest.raises(RuntimeError, match="SDK ownership was not released"):
            readiness.stop_managed_server(Starter(), "Kymera/2")
    else:
        readiness.stop_managed_server(Starter(), "Kymera/2")


def test_start_retries_only_rejected_already_running_transition(monkeypatch):
    calls = []

    class Starter:
        pending_exit = True

        def command_inout(self, name, argument):
            calls.append(name)
            if name == "DevGetRunningServers":
                return []
            assert name == "DevStart"
            if self.pending_exit:
                self.pending_exit = False
                raise RuntimeError("ALREADY_RUNNING")

    monkeypatch.setattr(readiness.time, "sleep", lambda _seconds: None)
    assert readiness.start_managed_server(Starter(), "server", lambda: "ready") == "ready"
    assert calls == ["DevGetRunningServers", "DevStart", "DevGetRunningServers", "DevStart"]


def test_recovery_reports_each_failure_attempt_and_verified_success():
    reports = []
    class Device:
        ready = False
        def get_command_list(self):
            return ["recover", "Init"]
        def command_inout(self, command):
            if command == "recover":
                raise RuntimeError("instrument offline")
            self.ready = True
    ready, errors = readiness.recover_device(Device(), lambda device: device.ready, on_progress=reports.append)
    assert ready
    assert errors == ["recover: instrument offline"]
    assert reports == ["Attempting device recovery command recover", "Recovery recover failed: instrument offline",
                       "Attempting device recovery command Init", "Recovery Init succeeded; hardware readiness verified"]


def test_unsettled_start_race_does_not_call_device_recovery(monkeypatch):
    class Starter:
        def command_inout(self, name, argument):
            if name == "DevGetRunningServers":
                return []
            raise RuntimeError("ALREADY_RUNNING")

    ticks = iter([0.0, 26.0])
    monkeypatch.setattr(readiness.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="transition did not settle"):
        readiness.start_managed_server(Starter(), "server", lambda: pytest.fail("must not touch device"))
