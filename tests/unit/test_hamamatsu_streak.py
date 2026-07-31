import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tango import DevState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
)
from DeviceServers.cameras.hamamatsu_streak.DS_HAMAMATSU_STREAK import (
    DS_HAMAMATSU_STREAK,
)
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import (
    RemoteExCommandError,
    RemoteExResponse,
    RemoteExTransportError,
    build_app_start_command,
    parse_response_line,
)


class FakeRemoteExClient:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.sent_commands = []
        self.is_connected = False
        self.last_messages = []
        self.last_response = None

    def connect(self, connect_data_port=False):
        self.is_connected = True

    def close(self):
        self.is_connected = False

    def send_command_checked(self, command, timeout=None):
        self.sent_commands.append(command)
        queue = self.responses.get(command)
        if not queue:
            raise AssertionError(f"No fake response configured for {command!r}")
        response = queue.pop(0)
        self.last_response = response
        if not response.is_ok:
            raise RemoteExCommandError("fake RemoteEx command error", response)
        return response


class TestRemoteExProtocol(unittest.TestCase):
    def test_parse_response_line(self):
        response = parse_response_line("0,DevParamGet,600")
        self.assertEqual(response.error_code, 0)
        self.assertEqual(response.command_name, "DevParamGet")
        self.assertEqual(response.parameters, ["600"])
        self.assertTrue(response.is_ok)

    def test_build_app_start_command_uses_empty_form_without_ini(self):
        self.assertEqual(build_app_start_command(), "AppStart()")

    def test_build_app_start_command_uses_full_form_with_ini(self):
        command = build_app_start_command(
            ini_path=r"C:\ProgramData\Hamamatsu\HPDTA\HPDTA8.INI"
        )
        self.assertEqual(
            command,
            r"AppStart(1,C:\ProgramData\Hamamatsu\HPDTA\HPDTA8.INI,1,ASCII)",
        )


class TestHamamatsuStreakController(unittest.TestCase):
    def test_power_off_keeps_tango_launcher_on_but_reports_hardware_off(self):
        calls = []
        device = SimpleNamespace(
            _power_probe_pending=True,
            _power_probe_due_at=10.0,
            _mark_hardware_power_off=lambda message, **kwargs: calls.append(
                (message, kwargs)
            ),
        )

        DS_HAMAMATSU_STREAK._handle_power_dependency_off(device, "PDU output 1")

        self.assertFalse(device._power_probe_pending)
        self.assertEqual(device._power_probe_due_at, 0.0)
        self.assertEqual(
            calls,
            [
                (
                    "Streak hardware power is OFF (PDU output 1); "
                    "RemoteEx service remains available.",
                    {"tango_state": DevState.ON},
                )
            ],
        )

    def test_status_skips_remoteex_when_streak_power_is_confirmed_off(self):
        calls = []
        device = SimpleNamespace(
            _observe_power_dependency=lambda: SimpleNamespace(
                configured=True, powered=False
            ),
            send_state_archive=lambda: calls.append("archive"),
            get_controller_status_local=lambda: (_ for _ in ()).throw(
                AssertionError("must not query RemoteEx while hardware is unpowered")
            ),
        )

        result = DS_HAMAMATSU_STREAK.get_controller_status(device)

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["archive"])

    def test_start_remoteex_attaches_before_starting_scheduled_task(self):
        class AttachOnlyDevice:
            controller = None
            client = None
            connected_value = False
            application_running_value = True
            remoteex_status_value = "disconnected"
            busy_command_value = "old-command"

            def _connect_remoteex(self):
                self.controller = SimpleNamespace(is_connected=True)
                self.connected_value = True

            def set_state(self, state):
                self.state = state

        device = AttachOnlyDevice()

        DS_HAMAMATSU_STREAK.StartRemoteEx(device)

        self.assertTrue(device.connected_value)
        self.assertFalse(device.application_running_value)
        self.assertEqual(device.remoteex_status_value, "idle")
        self.assertEqual(device.busy_command_value, "")

    def test_stop_remoteex_uses_elevated_stop_task(self):
        class StopDevice:
            application_running_value = False
            controller = None
            remoteex_stop_task_name = "Pyconlyse-Stop-TaRemoteEx"
            connected_value = True
            remoteex_status_value = "idle"
            busy_command_value = "Status()"
            last_command_value = ""
            last_response_value = ""

            def __init__(self):
                self._process_states = iter([True, False, False])

            def _windows_process_running(self, _name):
                return next(self._process_states)

            def set_state(self, state):
                self.state = state

        device = StopDevice()
        completed = SimpleNamespace(returncode=0, stdout="started", stderr="")

        with patch(
            "DeviceServers.cameras.hamamatsu_streak.DS_HAMAMATSU_STREAK.subprocess.run",
            return_value=completed,
        ) as run:
            DS_HAMAMATSU_STREAK.StopRemoteEx(device)

        run.assert_called_once_with(
            ["schtasks.exe", "/run", "/tn", "\\Pyconlyse-Stop-TaRemoteEx"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertFalse(device.connected_value)
        self.assertEqual(device.remoteex_status_value, "disconnected")
        self.assertEqual(device.state, DevState.ON)

    def test_refresh_cached_state_does_not_poll_controls_while_live_is_busy(self):
        fake = FakeRemoteExClient(
            {
                "Status()": [
                    RemoteExResponse(
                        raw_line="0,Status,1,AcqStart(Live)",
                        error_code=0,
                        command_name="Status",
                        parameters=["1", "AcqStart(Live)"],
                    )
                ]
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()

        snapshot = controller.refresh_cached_state()

        self.assertEqual(snapshot.remoteex_status, "busy")
        self.assertEqual(snapshot.busy_command, "AcqStart(Live)")
        self.assertEqual(fake.sent_commands, ["Status()"])

    def test_wait_for_async_idle(self):
        fake = FakeRemoteExClient(
            {
                "AsyncCommandStatus()": [
                    RemoteExResponse(
                        raw_line="0,AsyncCommandStatus,1,1,0,AcqStart",
                        error_code=0,
                        command_name="AsyncCommandStatus",
                        parameters=["1", "1", "0", "AcqStart"],
                    ),
                    RemoteExResponse(
                        raw_line="0,AsyncCommandStatus,0,0,0,AcqStart",
                        error_code=0,
                        command_name="AsyncCommandStatus",
                        parameters=["0", "0", "0", "AcqStart"],
                    ),
                ]
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()
        status = controller.wait_for_async_idle(timeout=1.0, poll_interval=0.0)
        self.assertFalse(status.pending)
        self.assertEqual(
            fake.sent_commands,
            ["AsyncCommandStatus()", "AsyncCommandStatus()"],
        )

    def test_start_live_uses_remoteex_live_command(self):
        fake = FakeRemoteExClient(
            {
                "AcqStart(Live)": [
                    RemoteExResponse(
                        raw_line="0,AcqStart",
                        error_code=0,
                        command_name="AcqStart",
                        parameters=[],
                    )
                ]
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()

        controller.start_live()

        self.assertEqual(
            fake.sent_commands,
            ["AcqStart(Live)"],
        )

    def test_start_live_accepts_hpdta_async_live_transition(self):
        fake = FakeRemoteExClient(
            {
                "AcqStart(Live)": [
                    RemoteExResponse(
                        raw_line="7,AcqStart,async command pending,HAcq_mLive",
                        error_code=7,
                        command_name="AcqStart",
                        parameters=["async command pending", "HAcq_mLive"],
                    )
                ]
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()

        controller.start_live()

        self.assertEqual(controller.snapshot.remoteex_status, "busy")
        self.assertEqual(controller.last_response_text, "7,AcqStart,async command pending,HAcq_mLive")

    def test_shutdown_remoteex_closes_the_local_control_socket(self):
        fake = FakeRemoteExClient(
            {
                "Shutdown()": [
                    RemoteExResponse(
                        raw_line="0,Shutdown",
                        error_code=0,
                        command_name="Shutdown",
                        parameters=[],
                    )
                ]
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()

        controller.shutdown_remoteex()

        self.assertEqual(fake.sent_commands, ["Shutdown()"])
        self.assertFalse(fake.is_connected)
        self.assertEqual(controller.snapshot.remoteex_status, "disconnected")

    def test_save_current_sequence_uses_his(self):
        fake = FakeRemoteExClient(
            {
                r"SeqSave(HIS,D:\Test\run01.his,1)": [
                    RemoteExResponse(
                        raw_line=r"0,SeqSave",
                        error_code=0,
                        command_name="SeqSave",
                        parameters=[],
                    )
                ],
                "AsyncCommandStatus()": [
                    RemoteExResponse(
                        raw_line="0,AsyncCommandStatus,0,0,0,SeqSave",
                        error_code=0,
                        command_name="AsyncCommandStatus",
                        parameters=["0", "0", "0", "SeqSave"],
                    )
                ],
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()
        saved = controller.save_current_sequence_his(r"D:\Test\run01.his")
        self.assertEqual(saved, r"D:\Test\run01.his")
        self.assertEqual(controller.snapshot.last_saved_sequence_path, r"D:\Test\run01.his")
        self.assertEqual(
            fake.sent_commands,
            [r"SeqSave(HIS,D:\Test\run01.his,1)", "AsyncCommandStatus()"],
        )

    def test_save_sequence_waits_through_a_transport_reset_without_replaying(self):
        class ResetDuringAsyncClient(FakeRemoteExClient):
            def __init__(self):
                super().__init__(
                    {
                        r"SeqSave(HIS,D:\Test\run02.his,1)": [
                            RemoteExResponse("0,SeqSave", 0, "SeqSave", [])
                        ],
                        "AsyncCommandStatus()": [
                            RemoteExResponse(
                                "0,AsyncCommandStatus,0,0,0,SeqSave",
                                0,
                                "AsyncCommandStatus",
                                ["0", "0", "0", "SeqSave"],
                            )
                        ],
                    }
                )
                self.reset_once = True

            def send_command_checked(self, command, timeout=None):
                if command == "AsyncCommandStatus()" and self.reset_once:
                    self.reset_once = False
                    self.is_connected = False
                    raise RemoteExTransportError("socket reset during HIS flush")
                return super().send_command_checked(command, timeout=timeout)

        fake = ResetDuringAsyncClient()
        controller = HamamatsuStreakController(fake)
        fake.connect()

        saved = controller.save_current_sequence_his(r"D:\Test\run02.his")

        self.assertEqual(saved, r"D:\Test\run02.his")
        self.assertEqual(fake.sent_commands.count(r"SeqSave(HIS,D:\Test\run02.his,1)"), 1)
        self.assertEqual(fake.sent_commands.count("AsyncCommandStatus()"), 1)

    def test_refresh_cached_state_reads_key_parameters(self):
        fake = FakeRemoteExClient(
            {
                "Status()": [
                    RemoteExResponse(
                        raw_line="0,Status,idle",
                        error_code=0,
                        command_name="Status",
                        parameters=["idle"],
                    )
                ],
                "AppInfo(Version)": [
                    RemoteExResponse(
                        raw_line="0,AppInfo,9.5",
                        error_code=0,
                        command_name="AppInfo",
                        parameters=["9.5"],
                    )
                ],
                "CamParamGet(Live,Exposure)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,100 ms",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["100 ms"],
                    )
                ],
                "CamParamGet(Acquire,Exposure)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,100 ms",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["100 ms"],
                    )
                ],
                "CamParamGet(AI,Exposure)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,100 ms",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["100 ms"],
                    )
                ],
                "CamParamGet(Live,DoRTBacksub)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,1",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["1"],
                    )
                ],
                "CamParamGet(Live,DoRTShading)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,1",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["1"],
                    )
                ],
                "CamParamGet(Live,RecurFilter)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,0",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["0"],
                    )
                ],
                "CamParamGet(Live,RecurNumber)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,2",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["2"],
                    )
                ],
                "CamParamGet(AI,NrExposures)": [
                    RemoteExResponse(
                        raw_line="0,CamParamGet,10",
                        error_code=0,
                        command_name="CamParamGet",
                        parameters=["10"],
                    )
                ],
                "SeqParamGet(AcquisitionMode)": [
                    RemoteExResponse(
                        raw_line="0,SeqParamGet,Live",
                        error_code=0,
                        command_name="SeqParamGet",
                        parameters=["Live"],
                    )
                ],
                "SeqParamGet(NoOfLoops)": [
                    RemoteExResponse(
                        raw_line="0,SeqParamGet,100",
                        error_code=0,
                        command_name="SeqParamGet",
                        parameters=["100"],
                    )
                ],
                "SeqParamGet(AcquisitionSpeed)": [
                    RemoteExResponse(
                        raw_line="0,SeqParamGet,Full speed",
                        error_code=0,
                        command_name="SeqParamGet",
                        parameters=["Full speed"],
                    )
                ],
                "DevParamGet(TD,Time Range)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,1 us",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["1 us"],
                    )
                ],
                "DevParamGet(TD,Mode)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,Operate",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["Operate"],
                    )
                ],
                "DevParamGet(TD,Gate Mode)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,Focus",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["Focus"],
                    )
                ],
                "DevParamGet(TD,MCP Gain)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,650",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["650"],
                    )
                ],
                "DevParamGet(Spec,Wavelength)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,600",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["600"],
                    )
                ],
                "DevParamGet(Spec,Grating)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,2",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["2"],
                    )
                ],
                "DevParamGet(Spec,Slit Width)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,20",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["20"],
                    )
                ],
                "DevParamGet(Spec,Shutter)": [
                    RemoteExResponse(
                        raw_line="0,DevParamGet,Closed",
                        error_code=0,
                        command_name="DevParamGet",
                        parameters=["Closed"],
                    )
                ],
            }
        )
        controller = HamamatsuStreakController(fake)
        fake.connect()
        snapshot = controller.refresh_cached_state()
        self.assertEqual(snapshot.remoteex_status, "idle")
        self.assertEqual(snapshot.application_version, "9.5")
        self.assertEqual(snapshot.live_exposure_time, "100 ms")
        self.assertEqual(snapshot.sequence_loops, "100")
        self.assertEqual(snapshot.current_time_range, "1 us")
        self.assertEqual(snapshot.current_wavelength, "600")
        self.assertEqual(snapshot.current_slit_width, "20")


if __name__ == "__main__":
    unittest.main(verbosity=2)
