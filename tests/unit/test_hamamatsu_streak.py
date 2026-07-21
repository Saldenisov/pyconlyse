import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
)
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import (
    RemoteExCommandError,
    RemoteExResponse,
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
