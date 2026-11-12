"""No live equipment: exclusive HPD-TA / Kymera SDK ownership and cleanup."""

import json
from itertools import count
from types import SimpleNamespace

import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api


def rig(monkeypatch, *, busy=False, wrong_blaze=False, stop_error=False, auto_probe="0", stays_on=False):
    events = []
    values = {"application_running": True, "remoteex_status": "idle",
              "streak_shutter": "Open", "spectrograph_shutter": "Open", "connected": True}

    class Streak:
        def set_timeout_millis(self, timeout):
            assert timeout == 30000

        def read_attribute(self, name):
            return SimpleNamespace(value=values[name])

        def write_attribute(self, name, value):
            events.append((name, value))
            values[name] = value

        def command_inout(self, name, value=None):
            events.append((name, value))
            if name == "ExecuteRaw":
                assert value == "AcqStatus()"
                return "0,AcqStatus,busy" if busy else "0,AcqStatus,idle"
            if name == "StopApplication":
                values["application_running"] = False
            else:
                assert name == "StopRemoteEx"
                assert not values["application_running"]
                values["connected"] = False

    class Kymera:
        current_state = "ON"

        def set_timeout_millis(self, timeout):
            assert timeout in {2000, 45000}

        def state(self):
            return self.current_state

        def get_property(self, names):
            return {name: [auto_probe] if auto_probe is not None else [] for name in names}

        def command_inout(self, name):
            events.append((name, None))
            assert not values["application_running"]
            if name == "PrepareVD2Grating":
                return json.dumps({"grating": 2, "blaze": 300 if wrong_blaze else 800, "ruling": 150})
            assert name == "turn_off"
            if stop_error:
                raise RuntimeError("SDK ownership was not released")
            if not stays_on:
                self.current_state = "OFF"

    def ensure(device, steps):
        assert device == api.KYMERA_DEVICE
        assert not values["application_running"]
        assert not values["connected"]
        assert values["streak_shutter"] == values["spectrograph_shutter"] == "Closed"
        events.append(("start Kymera", None))
        return Kymera()

    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(api, "_ensure_server", ensure)
    monkeypatch.setattr(api, "_astor", lambda *args: object())
    monkeypatch.setattr(api, "stop_managed_server", lambda *_args, **_kwargs: pytest.fail("Retain Kymera server; release SDK only"))
    return Streak(), events, values


def test_handoff_closes_shutters_and_stops_hpdta_before_sdk_access(monkeypatch):
    streak, events, values = rig(monkeypatch)
    steps = []
    api._prepare_kymera_for_vd2(streak, steps)
    assert events == [
        ("ExecuteRaw", "AcqStatus()"),
        ("streak_shutter", "Closed"), ("spectrograph_shutter", "Closed"),
        ("StopApplication", None), ("StopRemoteEx", None), ("start Kymera", None),
        ("PrepareVD2Grating", None), ("turn_off", None),
    ]
    assert not values["application_running"]
    assert steps[-1]["status"] == "SDK deinitialized; server retained; released to HPD-TA"


def test_active_acquisition_is_not_stopped_or_reconfigured(monkeypatch):
    streak, events, _ = rig(monkeypatch, busy=True)
    with pytest.raises(RuntimeError, match="acquisition is not confirmed idle"):
        api._prepare_kymera_for_vd2(streak, [])
    assert events == [("ExecuteRaw", "AcqStatus()")]


def test_bad_grating_readback_still_releases_sdk_but_does_not_report_ready(monkeypatch):
    streak, events, _ = rig(monkeypatch, wrong_blaze=True)
    steps = []
    with pytest.raises(RuntimeError, match="readback mismatch"):
        api._prepare_kymera_for_vd2(streak, steps)
    assert events[-1:] == [("turn_off", None)]
    assert not any(step["step"] == "Kymera SDK ownership" for step in steps)


def test_failed_sdk_release_prevents_hpdta_restart(monkeypatch):
    streak, events, _ = rig(monkeypatch, stop_error=True)
    with pytest.raises(RuntimeError, match="ownership was not released"):
        api._prepare_kymera_for_vd2(streak, [])
    assert not any(name == "StartApplication" for name, _ in events)


@pytest.mark.parametrize("auto_probe", ["1", None, "invalid"])
def test_unknown_or_enabled_background_sdk_probe_blocks_handoff(monkeypatch, auto_probe):
    streak, events, _ = rig(monkeypatch, auto_probe=auto_probe)
    with pytest.raises((RuntimeError, ValueError)):
        api._prepare_kymera_for_vd2(streak, [])
    assert ("PrepareVD2Grating", None) not in events
    assert events[-1] == ("turn_off", None)
    assert not any(name == "StartApplication" for name, _ in events)


def test_on_state_after_close_never_claims_sdk_release(monkeypatch):
    streak, events, _ = rig(monkeypatch, stays_on=True)
    ticks = count(0, 21)
    monkeypatch.setattr(api.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="HPD-TA startup blocked"):
        api._prepare_kymera_for_vd2(streak, [])
    assert events[-1] == ("turn_off", None)


def test_recording_protocol_blocks_preparation_before_power_or_recall(monkeypatch):
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "acquiring"}))
    monkeypatch.setattr(api, "_ensure_server", lambda *args: pytest.fail("must not touch hardware"))
    with pytest.raises(RuntimeError, match="Stop the VD2 measurement"):
        api._initialize_experiment()


def test_remoteex_that_did_not_release_blocks_sdk_start(monkeypatch):
    streak, events, values = rig(monkeypatch)
    real_command = streak.command_inout

    def command(name, value=None):
        result = real_command(name, value)
        if name == "StopRemoteEx":
            values["connected"] = True
        return result

    streak.command_inout = command
    with pytest.raises(RuntimeError, match="RemoteEx ownership was not released"):
        api._prepare_kymera_for_vd2(streak, [])
    assert ("start Kymera", None) not in events


def test_false_application_cache_cannot_hide_an_active_acquisition(monkeypatch):
    streak, events, values = rig(monkeypatch, busy=True)
    values["application_running"] = False
    with pytest.raises(RuntimeError, match="acquisition is not confirmed idle"):
        api._prepare_kymera_for_vd2(streak, [])
    assert events == [("ExecuteRaw", "AcqStatus()")]


def test_cold_optics_do_not_launch_remoteex_before_exclusive_kymera_preparation(monkeypatch):
    events = []
    values = {"application_running": False, "connected": False, "remoteex_status": "disconnected"}
    class Streak:
        def set_timeout_millis(self, _):
            pass
        def state(self):
            return "ON"
        def read_attribute(self, name):
            return SimpleNamespace(value=values[name])
        def command_inout(self, command):
            assert events and events[0] == "Kymera prepared and SDK released"
            events.append(command)
            if command == "StartRemoteEx":
                values.update(connected=True, remoteex_status="idle")
            elif command == "StartApplication":
                values["application_running"] = True
            else:
                pytest.fail(command)
    streak = Streak()
    monkeypatch.setattr(api, "_prepare_kymera_for_vd2", lambda *_: events.append("Kymera prepared and SDK released"))
    monkeypatch.setattr(api, "_remoteex_readback", lambda *_: "1 us")
    monkeypatch.setattr(api, "_apply_vd2_timing", lambda *_: events.append("Calibrated timing verified"))
    monkeypatch.setattr(api, "_snapshot", lambda _: {"ready": True})
    assert api._start_vd2_optics(streak, []) == {"ready": True}
    assert events == ["Kymera prepared and SDK released", "StartRemoteEx", "StartApplication", "Calibrated timing verified"]


@pytest.mark.parametrize("error, allowed", [
    ("3,AcqStatus,Application not running", True),
    ("AcqStatus() timed out", False),
])
def test_cold_connected_preflight_requires_explicit_not_running_reply(monkeypatch, error, allowed):
    streak, events, values = rig(monkeypatch)
    values["application_running"] = False

    def command(name, value=None):
        assert (name, value) == ("ExecuteRaw", "AcqStatus()")
        raise RuntimeError(error)

    streak.command_inout = command
    if allowed:
        api._assert_preparation_idle(streak)
    else:
        with pytest.raises(RuntimeError, match="Cannot confirm"):
            api._assert_preparation_idle(streak)
