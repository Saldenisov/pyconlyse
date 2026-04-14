from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .remoteex_client import RemoteExClient
from .remoteex_protocol import (
    RemoteExCommandError,
    RemoteExResponse,
    build_app_start_command,
    build_command,
)


@dataclass
class AsyncStatus:
    pending: bool = False
    preparing: bool = False
    active: bool = False
    command: str = ""


@dataclass
class HamamatsuStreakSnapshot:
    remoteex_status: str = "disconnected"
    busy_command: str = ""
    application_version: str = ""
    live_exposure_time: str = ""
    acquire_exposure_time: str = ""
    analog_integration_exposure_time: str = ""
    live_rt_backsub: str = ""
    live_rt_shading: str = ""
    live_rolling_average_enabled: str = ""
    live_rolling_average_number: str = ""
    analog_integration_count: str = ""
    sequence_acquisition_mode: str = ""
    sequence_loops: str = ""
    sequence_acquisition_speed: str = ""
    current_time_range: str = ""
    current_streak_mode: str = ""
    current_gate_mode: str = ""
    current_mcp_gain: str = ""
    current_streak_shutter: str = ""
    current_streak_trig_mode: str = ""
    current_streak_trigger_status: str = ""
    current_focus_time_over: str = ""
    current_wavelength: str = ""
    current_grating: str = ""
    current_blaze: str = ""
    current_ruling: str = ""
    current_exit_mirror: str = ""
    current_turret: str = ""
    current_slit_width: str = ""
    current_spectrograph_shutter: str = ""
    current_focus_mirror: str = ""
    current_side_entry_iris: str = ""
    current_delay_trig_mode: str = ""
    current_delay_repetition_rate: str = ""
    current_delay_setting: str = ""
    current_delay_a: str = ""
    current_delay_b: str = ""
    current_delay_c: str = ""
    current_delay_d: str = ""
    current_delay_e: str = ""
    current_delay_f: str = ""
    current_delay_g: str = ""
    current_delay_h: str = ""
    current_delay_ss_trigger: str = ""
    current_delay_burst_mode: str = ""
    current_delay_manual_control: str = ""
    last_saved_image_path: str = ""
    last_saved_sequence_path: str = ""
    application_running: bool = False


class HamamatsuStreakController:
    """High-level HPD-TA control facade on top of RemoteEx."""

    def __init__(
        self,
        client: RemoteExClient,
        *,
        ini_path: str = "",
        default_save_dir: str = "",
        async_timeout: float = 120.0,
    ):
        self.client = client
        self.ini_path = ini_path
        self.default_save_dir = default_save_dir
        self.async_timeout = float(async_timeout)
        self.snapshot = HamamatsuStreakSnapshot()
        self.last_command = ""
        self.last_response_text = ""
        self.last_messages: List[str] = []

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected

    def connect(self, connect_data_port: bool = False) -> None:
        self.client.connect(connect_data_port=connect_data_port)
        self.snapshot.remoteex_status = "idle"

    def disconnect(self) -> None:
        self.client.close()
        self.snapshot.remoteex_status = "disconnected"
        self.snapshot.application_running = False

    def execute_raw(self, command: str) -> RemoteExResponse:
        response = self.client.send_command_checked(command)
        self.last_command = command
        self.last_response_text = response.raw_line
        self.last_messages = [message.raw_line for message in self.client.last_messages]
        return response

    def start_application(
        self,
        *,
        visible: bool = True,
        ini_path: Optional[str] = None,
        no_dialogs: bool = True,
        encoding: str = "ASCII",
    ) -> RemoteExResponse:
        command = build_app_start_command(
            visible=visible,
            ini_path=self.ini_path if ini_path is None else ini_path,
            no_dialogs=no_dialogs,
            encoding=encoding,
        )
        response = self.execute_raw(command)
        self.snapshot.application_running = True
        return response

    def stop_application(self) -> RemoteExResponse:
        response = self.execute_raw("AppEnd()")
        self.snapshot.application_running = False
        return response

    def shutdown_remoteex(self) -> RemoteExResponse:
        response = self.execute_raw("Shutdown()")
        self.snapshot.application_running = False
        return response

    def status(self) -> HamamatsuStreakSnapshot:
        response = self.execute_raw("Status()")
        self.snapshot.remoteex_status = response.parameter(0, "unknown") or "unknown"
        self.snapshot.busy_command = response.parameter(1, "") or ""
        return self.snapshot

    def get_async_status(self) -> AsyncStatus:
        response = self.execute_raw("AsyncCommandStatus()")
        return AsyncStatus(
            pending=bool(int(response.parameter(0, "0") or "0")),
            preparing=bool(int(response.parameter(1, "0") or "0")),
            active=bool(int(response.parameter(2, "0") or "0")),
            command=response.parameter(3, "") or "",
        )

    def wait_for_async_idle(
        self, timeout: Optional[float] = None, poll_interval: float = 0.05
    ) -> AsyncStatus:
        deadline = time.monotonic() + float(timeout or self.async_timeout)
        status = AsyncStatus()
        while time.monotonic() < deadline:
            status = self.get_async_status()
            if not status.pending:
                return status
            time.sleep(poll_interval)
        raise TimeoutError(
            f"RemoteEx async command did not become idle within {timeout or self.async_timeout:.1f}s"
        )

    def get_main_param(self, parameter: str) -> str:
        response = self.execute_raw(build_command("MainParamGet", parameter))
        return response.parameter(0, "") or ""

    def get_app_info(self, parameter: str) -> str:
        response = self.execute_raw(build_command("AppInfo", parameter))
        return response.parameter(0, "") or ""

    def list_device_parameters(self, location: str) -> List[str]:
        response = self.execute_raw(build_command("DevParamsList", location))
        count = int(response.parameter(0, "0") or "0")
        params = response.parameters[1 : 1 + count]
        return params

    def get_device_parameter(self, location: str, parameter: str) -> str:
        response = self.execute_raw(build_command("DevParamGet", location, parameter))
        return response.parameter(0, "") or ""

    def get_camera_parameter(self, location: str, parameter: str) -> str:
        response = self.execute_raw(build_command("CamParamGet", location, parameter))
        return response.parameter(0, "") or ""

    def set_camera_parameter(
        self, location: str, parameter: str, value: object
    ) -> RemoteExResponse:
        return self.execute_raw(build_command("CamParamSet", location, parameter, value))

    def get_sequence_parameter(self, parameter: str) -> str:
        response = self.execute_raw(build_command("SeqParamGet", parameter))
        return response.parameter(0, "") or ""

    def set_sequence_parameter(self, parameter: str, value: object) -> RemoteExResponse:
        return self.execute_raw(build_command("SeqParamSet", parameter, value))

    def set_device_parameter(
        self, location: str, parameter: str, value: object
    ) -> RemoteExResponse:
        return self.execute_raw(build_command("DevParamSet", location, parameter, value))

    def set_live_exposure_time(self, value: str) -> str:
        self.set_camera_parameter("Live", "Exposure", value)
        self.snapshot.live_exposure_time = self.get_camera_parameter("Live", "Exposure")
        return self.snapshot.live_exposure_time

    def set_acquire_exposure_time(self, value: str) -> str:
        self.set_camera_parameter("Acquire", "Exposure", value)
        self.snapshot.acquire_exposure_time = self.get_camera_parameter(
            "Acquire", "Exposure"
        )
        return self.snapshot.acquire_exposure_time

    def set_analog_integration_exposure_time(self, value: str) -> str:
        self.set_camera_parameter("AI", "Exposure", value)
        self.snapshot.analog_integration_exposure_time = self.get_camera_parameter(
            "AI", "Exposure"
        )
        return self.snapshot.analog_integration_exposure_time

    def set_analog_integration_count(self, value: object) -> str:
        self.set_camera_parameter("AI", "NrExposures", value)
        self.snapshot.analog_integration_count = self.get_camera_parameter(
            "AI", "NrExposures"
        )
        return self.snapshot.analog_integration_count

    def set_live_rt_backsub(self, value: object) -> str:
        self.set_camera_parameter("Live", "DoRTBacksub", value)
        self.snapshot.live_rt_backsub = self.get_camera_parameter("Live", "DoRTBacksub")
        return self.snapshot.live_rt_backsub

    def set_live_rt_shading(self, value: object) -> str:
        self.set_camera_parameter("Live", "DoRTShading", value)
        self.snapshot.live_rt_shading = self.get_camera_parameter("Live", "DoRTShading")
        return self.snapshot.live_rt_shading

    def set_live_rolling_average_enabled(self, value: object) -> str:
        self.set_camera_parameter("Live", "RecurFilter", value)
        self.snapshot.live_rolling_average_enabled = self.get_camera_parameter(
            "Live", "RecurFilter"
        )
        return self.snapshot.live_rolling_average_enabled

    def set_live_rolling_average_number(self, value: object) -> str:
        self.set_camera_parameter("Live", "RecurNumber", value)
        self.snapshot.live_rolling_average_number = self.get_camera_parameter(
            "Live", "RecurNumber"
        )
        return self.snapshot.live_rolling_average_number

    def set_sequence_acquisition_mode(self, value: object) -> str:
        self.set_sequence_parameter("AcquisitionMode", value)
        self.snapshot.sequence_acquisition_mode = self.get_sequence_parameter(
            "AcquisitionMode"
        )
        return self.snapshot.sequence_acquisition_mode

    def set_sequence_loops(self, value: object) -> str:
        self.set_sequence_parameter("NoOfLoops", value)
        self.snapshot.sequence_loops = self.get_sequence_parameter("NoOfLoops")
        return self.snapshot.sequence_loops

    def set_sequence_acquisition_speed(self, value: object) -> str:
        self.set_sequence_parameter("AcquisitionSpeed", value)
        self.snapshot.sequence_acquisition_speed = self.get_sequence_parameter(
            "AcquisitionSpeed"
        )
        return self.snapshot.sequence_acquisition_speed

    def set_time_range(self, value: str) -> str:
        self.set_device_parameter("TD", "Time Range", value)
        self.snapshot.current_time_range = self.get_device_parameter("TD", "Time Range")
        return self.snapshot.current_time_range

    def set_streak_mode(self, value: str) -> str:
        self.set_device_parameter("TD", "Mode", value)
        self.snapshot.current_streak_mode = self.get_device_parameter("TD", "Mode")
        return self.snapshot.current_streak_mode

    def set_gate_mode(self, value: str) -> str:
        self.set_device_parameter("TD", "Gate Mode", value)
        self.snapshot.current_gate_mode = self.get_device_parameter("TD", "Gate Mode")
        return self.snapshot.current_gate_mode

    def set_mcp_gain(self, value: object) -> str:
        try:
            self.set_device_parameter("TD", "MCP Gain", value)
            self.snapshot.current_mcp_gain = self.get_device_parameter("TD", "MCP Gain")
        except RemoteExCommandError:
            self.set_device_parameter("TD", "II-Gain", value)
            self.snapshot.current_mcp_gain = self.get_device_parameter("TD", "II-Gain")
        return self.snapshot.current_mcp_gain

    def set_streak_shutter(self, value: object) -> str:
        self.set_device_parameter("TD", "Shutter", value)
        self.snapshot.current_streak_shutter = self.get_device_parameter("TD", "Shutter")
        return self.snapshot.current_streak_shutter

    def set_streak_trigger_mode(self, value: object) -> str:
        self.set_device_parameter("TD", "Trig. Mode", value)
        self.snapshot.current_streak_trig_mode = self.get_device_parameter(
            "TD", "Trig. Mode"
        )
        return self.snapshot.current_streak_trig_mode

    def set_focus_time_over(self, value: object) -> str:
        self.set_device_parameter("TD", "FocusTimeOver", value)
        self.snapshot.current_focus_time_over = self.get_device_parameter(
            "TD", "FocusTimeOver"
        )
        return self.snapshot.current_focus_time_over

    def set_wavelength_nm(self, value_nm: float) -> str:
        text_value = self._format_numeric(value_nm)
        self.set_device_parameter("Spec", "Wavelength", text_value)
        self.snapshot.current_wavelength = self.get_device_parameter("Spec", "Wavelength")
        return self.snapshot.current_wavelength

    def set_grating(self, value: object) -> str:
        self.set_device_parameter("Spec", "Grating", value)
        self.snapshot.current_grating = self.get_device_parameter("Spec", "Grating")
        return self.snapshot.current_grating

    def set_slit_width_um(self, value_um: float) -> str:
        text_value = self._format_numeric(value_um)
        self.set_device_parameter("Spec", "Slit Width", text_value)
        self.snapshot.current_slit_width = self.get_device_parameter("Spec", "Slit Width")
        return self.snapshot.current_slit_width

    def set_spectrograph_shutter(self, value: object) -> str:
        self.set_device_parameter("Spec", "Shutter", value)
        self.snapshot.current_spectrograph_shutter = self.get_device_parameter(
            "Spec", "Shutter"
        )
        return self.snapshot.current_spectrograph_shutter

    def set_exit_mirror(self, value: object) -> str:
        self.set_device_parameter("Spec", "Exit Mirror", value)
        self.snapshot.current_exit_mirror = self.get_device_parameter(
            "Spec", "Exit Mirror"
        )
        return self.snapshot.current_exit_mirror

    def set_turret(self, value: object) -> str:
        self.set_device_parameter("Spec", "Turret", value)
        self.snapshot.current_turret = self.get_device_parameter("Spec", "Turret")
        return self.snapshot.current_turret

    def set_focus_mirror(self, value: object) -> str:
        self.set_device_parameter("Spec", "Focus Mirror", value)
        self.snapshot.current_focus_mirror = self.get_device_parameter(
            "Spec", "Focus Mirror"
        )
        return self.snapshot.current_focus_mirror

    def set_side_entry_iris(self, value: object) -> str:
        self.set_device_parameter("Spec", "Side Entry Iris", value)
        self.snapshot.current_side_entry_iris = self.get_device_parameter(
            "Spec", "Side Entry Iris"
        )
        return self.snapshot.current_side_entry_iris

    def set_delay_trigger_mode(self, value: object) -> str:
        self.set_device_parameter("Del", "Trig. Mode", value)
        self.snapshot.current_delay_trig_mode = self.get_device_parameter(
            "Del", "Trig. Mode"
        )
        return self.snapshot.current_delay_trig_mode

    def set_delay_repetition_rate(self, value: object) -> str:
        self.set_device_parameter("Del", "Repetition Rate", value)
        self.snapshot.current_delay_repetition_rate = self.get_device_parameter(
            "Del", "Repetition Rate"
        )
        return self.snapshot.current_delay_repetition_rate

    def set_delay_setting(self, value: object) -> str:
        self.set_device_parameter("Del", "Setting", value)
        self.snapshot.current_delay_setting = self.get_device_parameter("Del", "Setting")
        return self.snapshot.current_delay_setting

    def set_delay_channel(self, channel_name: str, value: object) -> str:
        self.set_device_parameter("Del", channel_name, value)
        mapped = {
            "Delay A": "current_delay_a",
            "Delay B": "current_delay_b",
            "Delay C": "current_delay_c",
            "Delay D": "current_delay_d",
            "Delay E": "current_delay_e",
            "Delay F": "current_delay_f",
            "Delay G": "current_delay_g",
            "Delay H": "current_delay_h",
        }
        attr_name = mapped[channel_name]
        setattr(self.snapshot, attr_name, self.get_device_parameter("Del", channel_name))
        return getattr(self.snapshot, attr_name)

    def set_delay_burst_mode(self, value: object) -> str:
        self.set_device_parameter("Del", "Burst Mode", value)
        self.snapshot.current_delay_burst_mode = self.get_device_parameter(
            "Del", "Burst Mode"
        )
        return self.snapshot.current_delay_burst_mode

    def set_delay_manual_control(self, value: object) -> str:
        self.set_device_parameter("Del", "Man.Ctrl", value)
        self.snapshot.current_delay_manual_control = self.get_device_parameter(
            "Del", "Man.Ctrl"
        )
        return self.snapshot.current_delay_manual_control

    def acquire_single(self, wait: bool = True) -> None:
        self.execute_raw("AcqStart(SingleLive)")
        if wait:
            self.wait_for_async_idle()

    def start_acquire(self, wait: bool = True) -> None:
        self.execute_raw("AcqStart(Acquire)")
        if wait:
            self.wait_for_async_idle()

    def start_live(self) -> None:
        self.execute_raw("AcqStart(Live)")

    def start_analog_integration(self, wait: bool = True) -> None:
        self.execute_raw("AcqStart(AI)")
        if wait:
            self.wait_for_async_idle()

    def start_sequence(self, wait: bool = False) -> None:
        self.execute_raw("SeqStart()")
        if wait:
            self.wait_for_async_idle()

    def stop_acquisition(self) -> None:
        self.execute_raw("AcqStop()")

    def stop_sequence(self) -> None:
        self.execute_raw("SeqStop()")

    def save_current_image(self, path: str, overwrite: bool = True) -> str:
        self.execute_raw(
            build_command("ImgSave", "Current", "IMG", path, int(bool(overwrite)))
        )
        self.snapshot.last_saved_image_path = path
        return path

    def save_current_sequence_his(self, path: str, overwrite: bool = True) -> str:
        self.execute_raw(build_command("SeqSave", "HIS", path, int(bool(overwrite))))
        self.wait_for_async_idle()
        self.snapshot.last_saved_sequence_path = path
        return path

    def dump_current_image_data(self, path: str, data_type: str = "Data") -> str:
        self.execute_raw(build_command("ImgDataDump", "Current", data_type, path))
        return path

    def refresh_cached_state(self) -> HamamatsuStreakSnapshot:
        self.status()
        self.snapshot.application_version = self._safe_query(self.get_app_info, "Version")
        self.snapshot.application_running = bool(self.snapshot.application_version)
        self.snapshot.live_exposure_time = self._safe_query(
            self.get_camera_parameter, "Live", "Exposure"
        )
        self.snapshot.acquire_exposure_time = self._safe_query(
            self.get_camera_parameter, "Acquire", "Exposure"
        )
        self.snapshot.analog_integration_exposure_time = self._safe_query(
            self.get_camera_parameter, "AI", "Exposure"
        )
        self.snapshot.live_rt_backsub = self._safe_query(
            self.get_camera_parameter, "Live", "DoRTBacksub"
        )
        self.snapshot.live_rt_shading = self._safe_query(
            self.get_camera_parameter, "Live", "DoRTShading"
        )
        self.snapshot.live_rolling_average_enabled = self._safe_query(
            self.get_camera_parameter, "Live", "RecurFilter"
        )
        self.snapshot.live_rolling_average_number = self._safe_query(
            self.get_camera_parameter, "Live", "RecurNumber"
        )
        self.snapshot.analog_integration_count = self._safe_query(
            self.get_camera_parameter, "AI", "NrExposures"
        )
        self.snapshot.sequence_acquisition_mode = self._safe_query(
            self.get_sequence_parameter, "AcquisitionMode"
        )
        self.snapshot.sequence_loops = self._safe_query(
            self.get_sequence_parameter, "NoOfLoops"
        )
        self.snapshot.sequence_acquisition_speed = self._safe_query(
            self.get_sequence_parameter, "AcquisitionSpeed"
        )
        self.snapshot.current_time_range = self._safe_query(
            self.get_device_parameter, "TD", "Time Range"
        )
        self.snapshot.current_streak_mode = self._safe_query(
            self.get_device_parameter, "TD", "Mode"
        )
        self.snapshot.current_gate_mode = self._safe_query(
            self.get_device_parameter, "TD", "Gate Mode"
        )
        self.snapshot.current_mcp_gain = self._safe_query_with_fallback(
            [
                ("TD", "MCP Gain"),
                ("TD", "II-Gain"),
            ]
        )
        self.snapshot.current_streak_shutter = self._safe_query(
            self.get_device_parameter, "TD", "Shutter"
        )
        self.snapshot.current_streak_trig_mode = self._safe_query(
            self.get_device_parameter, "TD", "Trig. Mode"
        )
        self.snapshot.current_streak_trigger_status = self._safe_query(
            self.get_device_parameter, "TD", "Trigger status"
        )
        self.snapshot.current_focus_time_over = self._safe_query(
            self.get_device_parameter, "TD", "FocusTimeOver"
        )
        self.snapshot.current_wavelength = self._safe_query(
            self.get_device_parameter, "Spec", "Wavelength"
        )
        self.snapshot.current_grating = self._safe_query(
            self.get_device_parameter, "Spec", "Grating"
        )
        self.snapshot.current_blaze = self._safe_query(
            self.get_device_parameter, "Spec", "Blaze"
        )
        self.snapshot.current_ruling = self._safe_query(
            self.get_device_parameter, "Spec", "Ruling"
        )
        self.snapshot.current_exit_mirror = self._safe_query(
            self.get_device_parameter, "Spec", "Exit Mirror"
        )
        self.snapshot.current_turret = self._safe_query(
            self.get_device_parameter, "Spec", "Turret"
        )
        self.snapshot.current_slit_width = self._safe_query(
            self.get_device_parameter, "Spec", "Slit Width"
        )
        self.snapshot.current_spectrograph_shutter = self._safe_query(
            self.get_device_parameter, "Spec", "Shutter"
        )
        self.snapshot.current_focus_mirror = self._safe_query(
            self.get_device_parameter, "Spec", "Focus Mirror"
        )
        self.snapshot.current_side_entry_iris = self._safe_query(
            self.get_device_parameter, "Spec", "Side Entry Iris"
        )
        self.snapshot.current_delay_trig_mode = self._safe_query(
            self.get_device_parameter, "Del", "Trig. Mode"
        )
        self.snapshot.current_delay_repetition_rate = self._safe_query(
            self.get_device_parameter, "Del", "Repetition Rate"
        )
        self.snapshot.current_delay_setting = self._safe_query(
            self.get_device_parameter, "Del", "Setting"
        )
        self.snapshot.current_delay_a = self._safe_query(
            self.get_device_parameter, "Del", "Delay A"
        )
        self.snapshot.current_delay_b = self._safe_query(
            self.get_device_parameter, "Del", "Delay B"
        )
        self.snapshot.current_delay_c = self._safe_query(
            self.get_device_parameter, "Del", "Delay C"
        )
        self.snapshot.current_delay_d = self._safe_query(
            self.get_device_parameter, "Del", "Delay D"
        )
        self.snapshot.current_delay_e = self._safe_query(
            self.get_device_parameter, "Del", "Delay E"
        )
        self.snapshot.current_delay_f = self._safe_query(
            self.get_device_parameter, "Del", "Delay F"
        )
        self.snapshot.current_delay_g = self._safe_query(
            self.get_device_parameter, "Del", "Delay G"
        )
        self.snapshot.current_delay_h = self._safe_query(
            self.get_device_parameter, "Del", "Delay H"
        )
        self.snapshot.current_delay_ss_trigger = self._safe_query(
            self.get_device_parameter, "Del", "Ss Trigger"
        )
        self.snapshot.current_delay_burst_mode = self._safe_query(
            self.get_device_parameter, "Del", "Burst Mode"
        )
        self.snapshot.current_delay_manual_control = self._safe_query(
            self.get_device_parameter, "Del", "Man.Ctrl"
        )
        return self.snapshot

    def _safe_query(self, func, *args) -> str:
        try:
            return str(func(*args))
        except Exception:
            return ""

    def _safe_query_with_fallback(self, fallbacks: List[tuple]) -> str:
        for location, parameter in fallbacks:
            value = self._safe_query(self.get_device_parameter, location, parameter)
            if value:
                return value
        return ""

    @staticmethod
    def _format_numeric(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
