"""VD2 preparation against a stateful RemoteEx instrument model."""

import json
from types import SimpleNamespace

import pytest

from tests._tango_stub import install_tango_stub


class _CollectionMonkeyPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(_CollectionMonkeyPatch())

from tango import DevState
from DeviceServers.cameras.hamamatsu_streak.DS_HAMAMATSU_STREAK import (
    DS_HAMAMATSU_STREAK,
)
from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
)
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import (
    RemoteExCommandError,
    RemoteExTransportError,
    RemoteExResponse,
)


class ProfileClient:
    def __init__(self):
        self.is_connected = True
        self.last_messages = []
        self.last_response = None
        self.sent_commands = []
        self.sent_timeouts = {}
        self.application_running = True
        self.acquisition_active = False
        self.blaze_after_selection = "800"
        self.fail_open_readback = False
        self.open_camera_with_spectrograph = False
        self.values = {
            ("TD", "Shutter"): "Open",
            ("Spec", "Shutter"): "Open",
            # Kymera's SDK server already selected index 2 before AppStart.
            ("Spec", "Grating"): "150 g/mm",
            ("Spec", "Blaze"): "800",
            ("Spec", "Ruling"): "150",
            ("Spec", "Wavelength"): "700",
            ("TD", "Time Range"): "10 us",
            ("TD", "Mode"): "Focus",
        }

    def send_command_checked(self, command, timeout=None):
        self.sent_commands.append(command)
        self.sent_timeouts[command] = timeout
        name, text = command[:-1].split("(", 1)
        args = text.split(",")
        parameters = []
        if name == "Status":
            parameters = ["1", "AcqStart(Live)"] if self.acquisition_active else ["0", ""]
        elif name == "AppInfo":
            parameters = ["9.5" if self.application_running else ""]
        elif name == "DevParamSet":
            location, parameter, value = args
            self.values[(location, parameter)] = value
            if (location, parameter) == ("Spec", "Grating"):
                self.values[("Spec", "Blaze")] = self.blaze_after_selection
                self.values[("Spec", "Ruling")] = "150"
            if (location, parameter, value) == ("Spec", "Shutter", "Open"):
                if self.open_camera_with_spectrograph:
                    self.values[("TD", "Shutter")] = "Open"
        elif name == "DevParamGet":
            key = tuple(args)
            if key == ("Spec", "Shutter") and self.values[key] == "Open" and self.fail_open_readback:
                self.fail_open_readback = False
                response = RemoteExResponse("8,DevParamGet,readback failed", 8, name, ["readback failed"])
                raise RemoteExCommandError("readback failed", response)
            parameters = [self.values.get(key, "")]
        else:
            parameters = [""]
        self.last_response = RemoteExResponse(
            ",".join(["0", name, *parameters]), 0, name, parameters
        )
        return self.last_response

    @property
    def writes(self):
        return [command for command in self.sent_commands if command.startswith("DevParamSet(")]


def test_optical_write_timeout_is_not_replayed_and_names_failed_command():
    class SlowShutter(ProfileClient):
        def close(self):
            self.is_connected = False

        def connect(self):
            self.is_connected = True

        def send_command_checked(self, command, timeout=None):
            if command == "DevParamSet(Spec,Shutter,Open)":
                self.sent_commands.append(command)
                self.sent_timeouts[command] = timeout
                raise RemoteExTransportError("timed out")
            return super().send_command_checked(command, timeout=timeout)

    rig = SlowShutter()
    controller = HamamatsuStreakController(rig)
    with pytest.raises(RemoteExTransportError, match=r"DevParamSet\(Spec,Shutter,Open\)"):
        controller.configure_vd2_startup()
    assert rig.sent_commands.count("DevParamSet(Spec,Shutter,Open)") == 1
    assert rig.values[("Spec", "Shutter")] == "Closed"
    assert rig.values[("TD", "Shutter")] == "Closed"


def test_preparation_verifies_optics_before_opening_kymera_and_keeps_camera_closed():
    rig = ProfileClient()
    controller = HamamatsuStreakController(rig)

    snapshot = controller.configure_vd2_startup()
    assert rig.sent_timeouts["DevParamSet(Spec,Shutter,Open)"] == 30.0
    assert rig.sent_timeouts["DevParamSet(Spec,Wavelength,550)"] == 30.0

    assert rig.writes == [
        "DevParamSet(TD,Shutter,Closed)",
        "DevParamSet(Spec,Shutter,Closed)",
        "DevParamSet(Spec,Wavelength,550)",
        "DevParamSet(TD,Time Range,1 us)",
        "DevParamSet(TD,Mode,Operate)",
        "DevParamSet(Spec,Shutter,Open)",
    ]
    assert snapshot.current_blaze == "800"
    assert snapshot.current_wavelength == "550"
    assert snapshot.current_time_range == "1 us"
    assert snapshot.current_streak_mode == "Operate"
    assert snapshot.current_streak_shutter == "Closed"
    assert snapshot.current_spectrograph_shutter == "Open"
    assert not any(command.startswith(("AcqStart(", "SeqStart(")) for command in rig.sent_commands)
    assert not any(command.startswith("DevParamSet(Spec,Grating,") for command in rig.sent_commands)


@pytest.mark.parametrize("busy", [True, False])
def test_preparation_refuses_active_acquisition_or_stopped_application_without_writes(busy):
    rig = ProfileClient()
    rig.acquisition_active = busy
    rig.application_running = busy

    with pytest.raises(RuntimeError, match="Cannot prepare VD2|HPD-TA must be running"):
        HamamatsuStreakController(rig).configure_vd2_startup()

    assert rig.writes == []


def test_wrong_grating_blaze_fails_with_both_shutters_closed(monkeypatch):
    rig = ProfileClient()
    rig.values[("Spec", "Blaze")] = "500"
    ticks = iter([0.0, 21.0])
    monkeypatch.setattr(
        "DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller.time.monotonic",
        lambda: next(ticks),
    )

    with pytest.raises(RuntimeError, match="blaze 800 / ruling 150"):
        HamamatsuStreakController(rig).configure_vd2_startup()

    assert "DevParamSet(Spec,Shutter,Open)" not in rig.writes
    assert rig.values[("TD", "Shutter")] == "Closed"
    assert rig.values[("Spec", "Shutter")] == "Closed"


def test_wrong_remoteex_grating_label_never_triggers_an_ambiguous_selection():
    rig = ProfileClient()
    rig.values[("Spec", "Grating")] = "600 g/mm"
    with pytest.raises(RuntimeError, match="Kymera device server"):
        HamamatsuStreakController(rig).configure_vd2_startup()
    assert not any(command.startswith("DevParamSet(Spec,Grating,") for command in rig.writes)
    assert rig.values[("TD", "Shutter")] == "Closed"
    assert rig.values[("Spec", "Shutter")] == "Closed"


@pytest.mark.parametrize("failure", ["open_readback", "camera_open"])
def test_final_shutter_readback_failure_closes_both_shutters(failure):
    rig = ProfileClient()
    # Initial refresh is allowed; inject the fault after the profile is applied.
    rig.values[("Spec", "Shutter")] = "Closed"
    rig.fail_open_readback = failure == "open_readback"
    rig.open_camera_with_spectrograph = failure == "camera_open"

    with pytest.raises((RuntimeError, RemoteExCommandError), match="readback"):
        HamamatsuStreakController(rig).configure_vd2_startup()

    assert rig.values[("TD", "Shutter")] == "Closed"
    assert rig.values[("Spec", "Shutter")] == "Closed"


def test_repeat_preparation_does_not_move_verified_grating_or_change_timing():
    rig = ProfileClient()
    controller = HamamatsuStreakController(rig)
    controller.configure_vd2_startup()
    rig.sent_commands.clear()

    controller.configure_vd2_startup()

    assert rig.writes == [
        "DevParamSet(Spec,Shutter,Closed)",
        "DevParamSet(Spec,Shutter,Open)",
    ]


def test_preparation_worker_reports_fault_when_profile_verification_fails():
    controller = SimpleNamespace(
        configure_vd2_startup=lambda: (_ for _ in ()).throw(RuntimeError("Blaze mismatch")),
        snapshot=SimpleNamespace(application_running=True),
    )
    states = []
    device = SimpleNamespace(set_state=states.append, set_status=lambda value: None)

    DS_HAMAMATSU_STREAK._configure_vd2_startup_background(device, controller)

    assert states == [DevState.FAULT]
    assert "Blaze mismatch" in device._startup_configuration_error
    assert device.application_running_value is True


def test_status_poll_does_not_interrupt_background_optical_preparation():
    device = SimpleNamespace(
        _live_start_thread=None,
        _application_start_thread=SimpleNamespace(is_alive=lambda: True),
        connected_value=True,
        application_running_value=True,
        remoteex_status_value="preparing",
        busy_command_value="VD2 startup configuration",
        _require_controller=lambda: (_ for _ in ()).throw(AssertionError("must use cached state")),
    )

    result = json.loads(DS_HAMAMATSU_STREAK.RefreshStatus(device))

    assert result["remoteex_status"] == "preparing"
