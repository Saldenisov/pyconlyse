#!/usr/bin/python3 -u
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Union

app_folder = Path(__file__).resolve().parents[3]
if str(app_folder) not in sys.path:
    sys.path.append(str(app_folder))

from tango import AttrWriteType, DevState
from tango.server import attribute, command, device_property

from DeviceServers.base.general import DS_General
from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
)
from DeviceServers.cameras.hamamatsu_streak.remoteex_client import RemoteExClient


class DS_HAMAMATSU_STREAK(DS_General):
    RULES = {**DS_General.RULES}

    _version_ = "0.1"
    _model_ = "Hamamatsu HPD-TA RemoteEx streak system"

    device_id = device_property(dtype=str, default_value="hamamatsu_streak")
    friendly_name = device_property(dtype=str, default_value="HamamatsuStreak")
    server_id = device_property(dtype=int, default_value=1)

    host = device_property(dtype=str, default_value="localhost")
    command_port = device_property(dtype=int, default_value=1001)
    data_port = device_property(dtype=int, default_value=1002)
    ini_path = device_property(dtype=str, default_value="")
    default_save_dir = device_property(dtype=str, default_value="")
    command_timeout_s = device_property(dtype=float, default_value=5.0)
    async_timeout_s = device_property(dtype=float, default_value=120.0)
    command_encoding = device_property(dtype=str, default_value="ascii")
    connect_data_port = device_property(dtype=int, default_value=0)
    start_application_on_turn_on = device_property(dtype=int, default_value=1)
    start_on_init = device_property(dtype=int, default_value=0)

    def init_device(self):
        self.client = None
        self.controller = None
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.busy_command_value = ""
        self.application_version_value = ""
        self.live_exposure_time_value = ""
        self.acquire_exposure_time_value = ""
        self.analog_integration_exposure_time_value = ""
        self.live_rt_backsub_value = ""
        self.live_rt_shading_value = ""
        self.live_rolling_average_enabled_value = ""
        self.live_rolling_average_number_value = ""
        self.analog_integration_count_value = ""
        self.sequence_acquisition_mode_value = ""
        self.sequence_loops_value = ""
        self.sequence_acquisition_speed_value = ""
        self.current_time_range_value = ""
        self.current_streak_mode_value = ""
        self.current_gate_mode_value = ""
        self.current_mcp_gain_value = ""
        self.current_streak_shutter_value = ""
        self.current_streak_trig_mode_value = ""
        self.current_streak_trigger_status_value = ""
        self.current_focus_time_over_value = ""
        self.current_wavelength_value = ""
        self.current_grating_value = ""
        self.current_blaze_value = ""
        self.current_ruling_value = ""
        self.current_exit_mirror_value = ""
        self.current_turret_value = ""
        self.current_slit_width_value = ""
        self.current_spectrograph_shutter_value = ""
        self.current_focus_mirror_value = ""
        self.current_side_entry_iris_value = ""
        self.current_delay_trig_mode_value = ""
        self.current_delay_repetition_rate_value = ""
        self.current_delay_setting_value = ""
        self.current_delay_a_value = ""
        self.current_delay_b_value = ""
        self.current_delay_c_value = ""
        self.current_delay_d_value = ""
        self.current_delay_e_value = ""
        self.current_delay_f_value = ""
        self.current_delay_g_value = ""
        self.current_delay_h_value = ""
        self.current_delay_ss_trigger_value = ""
        self.current_delay_burst_mode_value = ""
        self.current_delay_manual_control_value = ""
        self.last_saved_image_path_value = ""
        self.last_saved_sequence_path_value = ""
        self.last_command_value = ""
        self.last_response_value = ""
        super().init_device()
        self.register_variables_for_archive()
        if bool(int(self.start_on_init or 0)) and self._device_id_internal != -1:
            try:
                self.turn_on()
            except Exception as exc:
                self.warn(f"Hamamatsu streak auto-start failed: {exc}", True)

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state["Connected"] = (lambda: int(self.connected_value), "uint8")
        self.archive_state["ApplicationRunning"] = (
            lambda: int(self.application_running_value),
            "uint8",
        )
        self.archive_state["WavelengthNm"] = (
            lambda: self._float_or_zero(self.current_wavelength_value),
            "float32",
        )

    def find_device(self):
        arg_return = -1, b""
        try:
            temp_client = self._create_client()
            temp_client.connect(connect_data_port=bool(int(self.connect_data_port or 0)))
            uri = f"remoteex://{self.host}:{self.command_port}".encode("utf-8")
            arg_return = int(self.command_port), uri
            temp_client.close()
        except Exception as exc:
            self.warn(f"RemoteEx discovery failed: {exc}", True)
        self._device_id_internal, self._uri = arg_return

    def get_controller_status_local(self) -> Union[int, str]:
        if self.controller is None or not self.controller.is_connected:
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(DevState.OFF)
            return 0

        try:
            snapshot = self.controller.refresh_cached_state()
            self._sync_from_snapshot(snapshot)
            if self.remoteex_status_value.lower() == "busy":
                self.set_state(DevState.RUNNING)
            else:
                self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.connected_value = False
            self.application_running_value = False
            self.set_state(DevState.FAULT)
            return f"RemoteEx status refresh failed: {exc}"

    def turn_on_local(self) -> Union[int, str]:
        try:
            self.client = self._create_client()
            self.controller = HamamatsuStreakController(
                self.client,
                ini_path=str(self.ini_path or ""),
                default_save_dir=str(self.default_save_dir or ""),
                async_timeout=float(self.async_timeout_s or 120.0),
            )
            self.controller.connect(connect_data_port=bool(int(self.connect_data_port or 0)))
            self.connected_value = True

            if bool(int(self.start_application_on_turn_on or 0)):
                self.controller.start_application()

            snapshot = self.controller.refresh_cached_state()
            self._sync_from_snapshot(snapshot)
            self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.client = None
            self.controller = None
            self.connected_value = False
            self.application_running_value = False
            self.set_state(DevState.FAULT)
            return f"Could not start Hamamatsu streak RemoteEx layer: {exc}"

    def turn_off_local(self) -> Union[int, str]:
        try:
            if self.controller is not None:
                self.controller.disconnect()
        finally:
            self.controller = None
            self.client = None
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(DevState.OFF)
        return 0

    def _create_client(self) -> RemoteExClient:
        return RemoteExClient(
            host=str(self.host or "localhost"),
            command_port=int(self.command_port or 1001),
            data_port=int(self.data_port or 1002),
            timeout=float(self.command_timeout_s or 5.0),
            encoding=str(self.command_encoding or "ascii"),
        )

    def _require_controller(self) -> HamamatsuStreakController:
        if self.controller is None or not self.controller.is_connected:
            raise RuntimeError("Hamamatsu streak controller is not connected")
        return self.controller

    def _sync_from_snapshot(self, snapshot) -> None:
        self.connected_value = self.controller is not None and self.controller.is_connected
        self.application_running_value = bool(snapshot.application_running)
        self.remoteex_status_value = snapshot.remoteex_status
        self.busy_command_value = snapshot.busy_command
        self.application_version_value = snapshot.application_version
        self.live_exposure_time_value = snapshot.live_exposure_time
        self.acquire_exposure_time_value = snapshot.acquire_exposure_time
        self.analog_integration_exposure_time_value = (
            snapshot.analog_integration_exposure_time
        )
        self.live_rt_backsub_value = snapshot.live_rt_backsub
        self.live_rt_shading_value = snapshot.live_rt_shading
        self.live_rolling_average_enabled_value = snapshot.live_rolling_average_enabled
        self.live_rolling_average_number_value = snapshot.live_rolling_average_number
        self.analog_integration_count_value = snapshot.analog_integration_count
        self.sequence_acquisition_mode_value = snapshot.sequence_acquisition_mode
        self.sequence_loops_value = snapshot.sequence_loops
        self.sequence_acquisition_speed_value = snapshot.sequence_acquisition_speed
        self.current_time_range_value = snapshot.current_time_range
        self.current_streak_mode_value = snapshot.current_streak_mode
        self.current_gate_mode_value = snapshot.current_gate_mode
        self.current_mcp_gain_value = snapshot.current_mcp_gain
        self.current_streak_shutter_value = snapshot.current_streak_shutter
        self.current_streak_trig_mode_value = snapshot.current_streak_trig_mode
        self.current_streak_trigger_status_value = snapshot.current_streak_trigger_status
        self.current_focus_time_over_value = snapshot.current_focus_time_over
        self.current_wavelength_value = snapshot.current_wavelength
        self.current_grating_value = snapshot.current_grating
        self.current_blaze_value = snapshot.current_blaze
        self.current_ruling_value = snapshot.current_ruling
        self.current_exit_mirror_value = snapshot.current_exit_mirror
        self.current_turret_value = snapshot.current_turret
        self.current_slit_width_value = snapshot.current_slit_width
        self.current_spectrograph_shutter_value = snapshot.current_spectrograph_shutter
        self.current_focus_mirror_value = snapshot.current_focus_mirror
        self.current_side_entry_iris_value = snapshot.current_side_entry_iris
        self.current_delay_trig_mode_value = snapshot.current_delay_trig_mode
        self.current_delay_repetition_rate_value = snapshot.current_delay_repetition_rate
        self.current_delay_setting_value = snapshot.current_delay_setting
        self.current_delay_a_value = snapshot.current_delay_a
        self.current_delay_b_value = snapshot.current_delay_b
        self.current_delay_c_value = snapshot.current_delay_c
        self.current_delay_d_value = snapshot.current_delay_d
        self.current_delay_e_value = snapshot.current_delay_e
        self.current_delay_f_value = snapshot.current_delay_f
        self.current_delay_g_value = snapshot.current_delay_g
        self.current_delay_h_value = snapshot.current_delay_h
        self.current_delay_ss_trigger_value = snapshot.current_delay_ss_trigger
        self.current_delay_burst_mode_value = snapshot.current_delay_burst_mode
        self.current_delay_manual_control_value = snapshot.current_delay_manual_control
        self.last_saved_image_path_value = snapshot.last_saved_image_path
        self.last_saved_sequence_path_value = snapshot.last_saved_sequence_path
        if self.controller is not None:
            self.last_command_value = self.controller.last_command
            self.last_response_value = self.controller.last_response_text

    @staticmethod
    def _float_or_zero(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @attribute(label="connected", dtype=bool, access=AttrWriteType.READ)
    def connected(self):
        return bool(self.connected_value)

    @attribute(label="application running", dtype=bool, access=AttrWriteType.READ)
    def application_running(self):
        return bool(self.application_running_value)

    @attribute(label="RemoteEx status", dtype=str, access=AttrWriteType.READ)
    def remoteex_status(self):
        return str(self.remoteex_status_value)

    @attribute(label="busy command", dtype=str, access=AttrWriteType.READ)
    def busy_command(self):
        return str(self.busy_command_value)

    @attribute(label="application version", dtype=str, access=AttrWriteType.READ)
    def application_version(self):
        return str(self.application_version_value)

    @attribute(label="live exposure time", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_exposure_time(self):
        return str(self.live_exposure_time_value)

    def write_live_exposure_time(self, value: str):
        controller = self._require_controller()
        self.live_exposure_time_value = controller.set_live_exposure_time(str(value))

    @attribute(label="acquire exposure time", dtype=str, access=AttrWriteType.READ_WRITE)
    def acquire_exposure_time(self):
        return str(self.acquire_exposure_time_value)

    def write_acquire_exposure_time(self, value: str):
        controller = self._require_controller()
        self.acquire_exposure_time_value = controller.set_acquire_exposure_time(str(value))

    @attribute(
        label="analog integration exposure time",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def analog_integration_exposure_time(self):
        return str(self.analog_integration_exposure_time_value)

    def write_analog_integration_exposure_time(self, value: str):
        controller = self._require_controller()
        self.analog_integration_exposure_time_value = (
            controller.set_analog_integration_exposure_time(str(value))
        )

    @attribute(label="live RT backsub", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rt_backsub(self):
        return str(self.live_rt_backsub_value)

    def write_live_rt_backsub(self, value: str):
        controller = self._require_controller()
        self.live_rt_backsub_value = controller.set_live_rt_backsub(str(value))

    @attribute(label="live RT shading", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rt_shading(self):
        return str(self.live_rt_shading_value)

    def write_live_rt_shading(self, value: str):
        controller = self._require_controller()
        self.live_rt_shading_value = controller.set_live_rt_shading(str(value))

    @attribute(label="live rolling average", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rolling_average(self):
        return str(self.live_rolling_average_enabled_value)

    def write_live_rolling_average(self, value: str):
        controller = self._require_controller()
        self.live_rolling_average_enabled_value = (
            controller.set_live_rolling_average_enabled(str(value))
        )

    @attribute(
        label="live rolling average number",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def live_rolling_average_number(self):
        return str(self.live_rolling_average_number_value)

    def write_live_rolling_average_number(self, value: str):
        controller = self._require_controller()
        self.live_rolling_average_number_value = (
            controller.set_live_rolling_average_number(str(value))
        )

    @attribute(
        label="analog integration count",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def analog_integration_count(self):
        return str(self.analog_integration_count_value)

    def write_analog_integration_count(self, value: str):
        controller = self._require_controller()
        self.analog_integration_count_value = controller.set_analog_integration_count(
            str(value)
        )

    @attribute(
        label="sequence acquisition mode",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def sequence_acquisition_mode(self):
        return str(self.sequence_acquisition_mode_value)

    def write_sequence_acquisition_mode(self, value: str):
        controller = self._require_controller()
        self.sequence_acquisition_mode_value = controller.set_sequence_acquisition_mode(
            str(value)
        )

    @attribute(label="sequence loops", dtype=str, access=AttrWriteType.READ_WRITE)
    def sequence_loops(self):
        return str(self.sequence_loops_value)

    def write_sequence_loops(self, value: str):
        controller = self._require_controller()
        self.sequence_loops_value = controller.set_sequence_loops(str(value))

    @attribute(
        label="sequence acquisition speed",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def sequence_acquisition_speed(self):
        return str(self.sequence_acquisition_speed_value)

    def write_sequence_acquisition_speed(self, value: str):
        controller = self._require_controller()
        self.sequence_acquisition_speed_value = controller.set_sequence_acquisition_speed(
            str(value)
        )

    @attribute(label="time range", dtype=str, access=AttrWriteType.READ_WRITE)
    def time_range(self):
        return str(self.current_time_range_value)

    def write_time_range(self, value: str):
        controller = self._require_controller()
        self.current_time_range_value = controller.set_time_range(str(value))

    @attribute(label="streak mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_mode(self):
        return str(self.current_streak_mode_value)

    def write_streak_mode(self, value: str):
        controller = self._require_controller()
        self.current_streak_mode_value = controller.set_streak_mode(str(value))

    @attribute(label="gate mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def gate_mode(self):
        return str(self.current_gate_mode_value)

    def write_gate_mode(self, value: str):
        controller = self._require_controller()
        self.current_gate_mode_value = controller.set_gate_mode(str(value))

    @attribute(label="MCP gain", dtype=str, access=AttrWriteType.READ)
    def mcp_gain_text(self):
        return str(self.current_mcp_gain_value)

    @attribute(label="streak shutter", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_shutter(self):
        return str(self.current_streak_shutter_value)

    def write_streak_shutter(self, value: str):
        controller = self._require_controller()
        self.current_streak_shutter_value = controller.set_streak_shutter(str(value))

    @attribute(label="streak trig mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_trig_mode(self):
        return str(self.current_streak_trig_mode_value)

    def write_streak_trig_mode(self, value: str):
        controller = self._require_controller()
        self.current_streak_trig_mode_value = controller.set_streak_trigger_mode(
            str(value)
        )

    @attribute(label="streak trigger status", dtype=str, access=AttrWriteType.READ)
    def streak_trigger_status(self):
        return str(self.current_streak_trigger_status_value)

    @attribute(label="focus time over", dtype=str, access=AttrWriteType.READ_WRITE)
    def focus_time_over(self):
        return str(self.current_focus_time_over_value)

    def write_focus_time_over(self, value: str):
        controller = self._require_controller()
        self.current_focus_time_over_value = controller.set_focus_time_over(str(value))

    @attribute(label="wavelength nm", dtype=float, access=AttrWriteType.READ_WRITE)
    def wavelength_nm(self):
        try:
            return float(self.current_wavelength_value)
        except Exception:
            return 0.0

    def write_wavelength_nm(self, value: float):
        controller = self._require_controller()
        self.current_wavelength_value = controller.set_wavelength_nm(float(value))

    @attribute(label="grating", dtype=str, access=AttrWriteType.READ_WRITE)
    def grating(self):
        return str(self.current_grating_value)

    def write_grating(self, value: str):
        controller = self._require_controller()
        self.current_grating_value = controller.set_grating(str(value))

    @attribute(label="slit width um", dtype=float, access=AttrWriteType.READ_WRITE)
    def slit_width_um(self):
        try:
            return float(self.current_slit_width_value)
        except Exception:
            return 0.0

    def write_slit_width_um(self, value: float):
        controller = self._require_controller()
        self.current_slit_width_value = controller.set_slit_width_um(float(value))

    @attribute(label="spectrograph shutter", dtype=str, access=AttrWriteType.READ_WRITE)
    def spectrograph_shutter(self):
        return str(self.current_spectrograph_shutter_value)

    def write_spectrograph_shutter(self, value: str):
        controller = self._require_controller()
        self.current_spectrograph_shutter_value = controller.set_spectrograph_shutter(
            str(value)
        )

    @attribute(label="blaze", dtype=str, access=AttrWriteType.READ)
    def blaze(self):
        return str(self.current_blaze_value)

    @attribute(label="ruling", dtype=str, access=AttrWriteType.READ)
    def ruling(self):
        return str(self.current_ruling_value)

    @attribute(label="exit mirror", dtype=str, access=AttrWriteType.READ_WRITE)
    def exit_mirror(self):
        return str(self.current_exit_mirror_value)

    def write_exit_mirror(self, value: str):
        controller = self._require_controller()
        self.current_exit_mirror_value = controller.set_exit_mirror(str(value))

    @attribute(label="turret", dtype=str, access=AttrWriteType.READ_WRITE)
    def turret(self):
        return str(self.current_turret_value)

    def write_turret(self, value: str):
        controller = self._require_controller()
        self.current_turret_value = controller.set_turret(str(value))

    @attribute(label="focus mirror", dtype=str, access=AttrWriteType.READ_WRITE)
    def focus_mirror(self):
        return str(self.current_focus_mirror_value)

    def write_focus_mirror(self, value: str):
        controller = self._require_controller()
        self.current_focus_mirror_value = controller.set_focus_mirror(str(value))

    @attribute(label="side entry iris", dtype=str, access=AttrWriteType.READ_WRITE)
    def side_entry_iris(self):
        return str(self.current_side_entry_iris_value)

    def write_side_entry_iris(self, value: str):
        controller = self._require_controller()
        self.current_side_entry_iris_value = controller.set_side_entry_iris(str(value))

    @attribute(label="delay trig mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_trig_mode(self):
        return str(self.current_delay_trig_mode_value)

    def write_delay_trig_mode(self, value: str):
        controller = self._require_controller()
        self.current_delay_trig_mode_value = controller.set_delay_trigger_mode(str(value))

    @attribute(label="delay repetition rate", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_repetition_rate(self):
        return str(self.current_delay_repetition_rate_value)

    def write_delay_repetition_rate(self, value: str):
        controller = self._require_controller()
        self.current_delay_repetition_rate_value = controller.set_delay_repetition_rate(
            str(value)
        )

    @attribute(label="delay setting", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_setting(self):
        return str(self.current_delay_setting_value)

    def write_delay_setting(self, value: str):
        controller = self._require_controller()
        self.current_delay_setting_value = controller.set_delay_setting(str(value))

    @attribute(label="delay A", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_a(self):
        return str(self.current_delay_a_value)

    def write_delay_a(self, value: str):
        controller = self._require_controller()
        self.current_delay_a_value = controller.set_delay_channel("Delay A", str(value))

    @attribute(label="delay B", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_b(self):
        return str(self.current_delay_b_value)

    def write_delay_b(self, value: str):
        controller = self._require_controller()
        self.current_delay_b_value = controller.set_delay_channel("Delay B", str(value))

    @attribute(label="delay C", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_c(self):
        return str(self.current_delay_c_value)

    def write_delay_c(self, value: str):
        controller = self._require_controller()
        self.current_delay_c_value = controller.set_delay_channel("Delay C", str(value))

    @attribute(label="delay D", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_d(self):
        return str(self.current_delay_d_value)

    def write_delay_d(self, value: str):
        controller = self._require_controller()
        self.current_delay_d_value = controller.set_delay_channel("Delay D", str(value))

    @attribute(label="delay E", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_e(self):
        return str(self.current_delay_e_value)

    def write_delay_e(self, value: str):
        controller = self._require_controller()
        self.current_delay_e_value = controller.set_delay_channel("Delay E", str(value))

    @attribute(label="delay F", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_f(self):
        return str(self.current_delay_f_value)

    def write_delay_f(self, value: str):
        controller = self._require_controller()
        self.current_delay_f_value = controller.set_delay_channel("Delay F", str(value))

    @attribute(label="delay G", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_g(self):
        return str(self.current_delay_g_value)

    def write_delay_g(self, value: str):
        controller = self._require_controller()
        self.current_delay_g_value = controller.set_delay_channel("Delay G", str(value))

    @attribute(label="delay H", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_h(self):
        return str(self.current_delay_h_value)

    def write_delay_h(self, value: str):
        controller = self._require_controller()
        self.current_delay_h_value = controller.set_delay_channel("Delay H", str(value))

    @attribute(label="delay ss trigger", dtype=str, access=AttrWriteType.READ)
    def delay_ss_trigger(self):
        return str(self.current_delay_ss_trigger_value)

    @attribute(label="delay burst mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_burst_mode(self):
        return str(self.current_delay_burst_mode_value)

    def write_delay_burst_mode(self, value: str):
        controller = self._require_controller()
        self.current_delay_burst_mode_value = controller.set_delay_burst_mode(str(value))

    @attribute(label="delay manual control", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_manual_control(self):
        return str(self.current_delay_manual_control_value)

    def write_delay_manual_control(self, value: str):
        controller = self._require_controller()
        self.current_delay_manual_control_value = controller.set_delay_manual_control(
            str(value)
        )

    @attribute(label="last saved image path", dtype=str, access=AttrWriteType.READ)
    def last_saved_image_path(self):
        return str(self.last_saved_image_path_value)

    @attribute(label="last saved sequence path", dtype=str, access=AttrWriteType.READ)
    def last_saved_sequence_path(self):
        return str(self.last_saved_sequence_path_value)

    @attribute(label="last command", dtype=str, access=AttrWriteType.READ)
    def last_command(self):
        return str(self.last_command_value)

    @attribute(label="last response", dtype=str, access=AttrWriteType.READ)
    def last_response(self):
        return str(self.last_response_value)

    @command
    def Connect(self):
        self.turn_on()

    @command
    def Disconnect(self):
        self.turn_off()

    @command
    def RefreshStatus(self):
        controller = self._require_controller()
        snapshot = controller.refresh_cached_state()
        self._sync_from_snapshot(snapshot)
        return json.dumps(
            {
                "connected": self.connected_value,
                "application_running": self.application_running_value,
                "remoteex_status": self.remoteex_status_value,
                "busy_command": self.busy_command_value,
            }
        )

    @command
    def StartApplication(self):
        controller = self._require_controller()
        controller.start_application()
        snapshot = controller.refresh_cached_state()
        self._sync_from_snapshot(snapshot)
        return self.application_version_value

    @command
    def StopApplication(self):
        controller = self._require_controller()
        controller.stop_application()
        self.application_running_value = False

    @command
    def ShutdownRemoteEx(self):
        controller = self._require_controller()
        controller.shutdown_remoteex()
        self.application_running_value = False

    @command
    def AcquireSingle(self):
        controller = self._require_controller()
        controller.acquire_single()
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text

    @command
    def Acquire(self):
        controller = self._require_controller()
        controller.start_acquire()
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text

    @command
    def StartLive(self):
        controller = self._require_controller()
        controller.start_live()
        self.remoteex_status_value = "busy"
        self.set_state(DevState.RUNNING)

    @command
    def StartAnalogIntegration(self):
        controller = self._require_controller()
        controller.start_analog_integration()
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text

    @command
    def StartSequence(self):
        controller = self._require_controller()
        controller.start_sequence(wait=False)
        self.remoteex_status_value = "busy"
        self.set_state(DevState.RUNNING)

    @command
    def StopAcquisition(self):
        controller = self._require_controller()
        controller.stop_acquisition()
        self.get_controller_status()

    @command
    def StopSequence(self):
        controller = self._require_controller()
        controller.stop_sequence()
        self.get_controller_status()

    @command
    def WaitForIdle(self):
        controller = self._require_controller()
        controller.wait_for_async_idle()
        snapshot = controller.refresh_cached_state()
        self._sync_from_snapshot(snapshot)
        return self.remoteex_status_value

    @command(dtype_in=str, dtype_out=str)
    def SaveCurrentImage(self, path: str):
        controller = self._require_controller()
        saved = controller.save_current_image(path)
        self.last_saved_image_path_value = saved
        return saved

    @command(dtype_in=str, dtype_out=str)
    def SaveCurrentSequence(self, path: str):
        controller = self._require_controller()
        saved = controller.save_current_sequence_his(path)
        self.last_saved_sequence_path_value = saved
        self.get_controller_status()
        return saved

    @command(dtype_in=str, dtype_out=str)
    def DumpCurrentImageData(self, path: str):
        controller = self._require_controller()
        return controller.dump_current_image_data(path)

    @command(dtype_in=str, dtype_out=str)
    def ExecuteRaw(self, command_text: str):
        controller = self._require_controller()
        response = controller.execute_raw(command_text)
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text
        return response.raw_line

    @command(dtype_out=str)
    def ListStreakParameters(self):
        controller = self._require_controller()
        return json.dumps(controller.list_device_parameters("TD"))

    @command(dtype_out=str)
    def ListSpectrographParameters(self):
        controller = self._require_controller()
        return json.dumps(controller.list_device_parameters("Spec"))

    @command(dtype_out=str)
    def ListDelayParameters(self):
        controller = self._require_controller()
        return json.dumps(controller.list_device_parameters("Del"))

    @command(dtype_in=float, dtype_out=str)
    def SetWavelength(self, value_nm: float):
        controller = self._require_controller()
        self.current_wavelength_value = controller.set_wavelength_nm(float(value_nm))
        return self.current_wavelength_value

    @command(dtype_in=str, dtype_out=str)
    def SetTimeRange(self, value: str):
        controller = self._require_controller()
        self.current_time_range_value = controller.set_time_range(str(value))
        return self.current_time_range_value

    @command(dtype_in=float, dtype_out=str)
    def SetSlitWidth(self, value_um: float):
        controller = self._require_controller()
        self.current_slit_width_value = controller.set_slit_width_um(float(value_um))
        return self.current_slit_width_value

    @command(dtype_in=str, dtype_out=str)
    def SetMCPGain(self, value: str):
        controller = self._require_controller()
        self.current_mcp_gain_value = controller.set_mcp_gain(str(value))
        return self.current_mcp_gain_value


if __name__ == "__main__":
    DS_HAMAMATSU_STREAK.run_server()
