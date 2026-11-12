#!/usr/bin/python3 -u
from __future__ import annotations

from sys import modules as _refactor_modules

import base64
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Union

app_folder = Path(__file__).resolve().parents[3]
if str(app_folder) not in sys.path:
    sys.path.append(str(app_folder))

from DeviceServers.cameras.hamamatsu_streak.streak_camera_methods_power_dependency_ready_state import _bind_streak_camera_methods_power_dependency_ready_state
from DeviceServers.cameras.hamamatsu_streak.streak_camera_methods_write_delay_e import _bind_streak_camera_methods_write_delay_e

from tango import AttrWriteType, DevState, DeviceProxy
from tango.server import attribute, command, device_property

from DeviceServers.base.general import DS_General
from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
)
from DeviceServers.cameras.hamamatsu_streak.camera_only_profile import (
    DEFAULT_REMOTE_INI, checked_camera_only_ini, remoteex_process_identity,
)
from DeviceServers.cameras.hamamatsu_streak.remoteex_client import RemoteExClient
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import RemoteExTransportError


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
    camera_only_ini_path = device_property(dtype=str, default_value=DEFAULT_REMOTE_INI)
    remote_camera_only = device_property(dtype=bool, default_value=False)
    default_save_dir = device_property(dtype=str, default_value="")
    command_timeout_s = device_property(dtype=float, default_value=5.0)
    async_timeout_s = device_property(dtype=float, default_value=120.0)
    command_encoding = device_property(dtype=str, default_value="ascii")
    connect_data_port = device_property(dtype=int, default_value=0)
    start_application_on_turn_on = device_property(dtype=int, default_value=1)
    start_on_init = device_property(dtype=int, default_value=0)
    remoteex_task_name = device_property(
        dtype=str, default_value="Pyconlyse-TaRemoteEx"
    )
    remoteex_stop_task_name = device_property(
        dtype=str, default_value="Pyconlyse-Stop-TaRemoteEx"
    )
    remoteex_start_timeout_s = device_property(dtype=float, default_value=12.0)
    dg645_device = device_property(dtype=str, default_value="manip/sync/DG645")
    dg645_hpdta_recall_slot = device_property(dtype=int, default_value=9)
    dg645_recall_wait_s = device_property(dtype=float, default_value=1.0)

    def init_device(self):
        self.client = None
        self.controller = None
        self._sequence_reconnect_pending = False
        self._application_start_thread = None
        self._live_start_thread = None
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.busy_command_value = ""
        self._startup_configuration_error = ""
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
        # Poll read-only RemoteEx status so manual HPD-TA changes reach Tango
        # and the web UI. The controller skips detailed reads during acquisition.
        self.register_variables_for_archive()
        # This server can run before RemoteEx. It is the launcher for that
        # process, so a closed TCP port is a normal initial state, not a Tango
        # device fault.
        self.set_state(DevState.ON)
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

    _streak_camera_methods_power_dependency_ready_state = _bind_streak_camera_methods_power_dependency_ready_state(_refactor_modules[__name__])
    power_dependency_ready_state = _streak_camera_methods_power_dependency_ready_state["power_dependency_ready_state"]

    _handle_power_dependency_off = _streak_camera_methods_power_dependency_ready_state["_handle_power_dependency_off"]

    _handle_power_dependency_unavailable = _streak_camera_methods_power_dependency_ready_state["_handle_power_dependency_unavailable"]

    probe_powered_hardware = _streak_camera_methods_power_dependency_ready_state["probe_powered_hardware"]

    find_device = _streak_camera_methods_power_dependency_ready_state["find_device"]

    @command(polling_period=5000)
    def get_controller_status(self):
        """Refresh read-only status without DS_General's auto-turn-on loop.

        A streak acquisition is legitimately RUNNING. The generic implementation
        treats every non-ON state as a failed power-up and reconnects RemoteEx,
        which interrupts the web control state while Live is active.
        """
        power_state = self._observe_power_dependency()
        if power_state.configured and power_state.powered is not True:
            self.send_state_archive()
            return 0
        result = self.get_controller_status_local()
        self.send_state_archive()
        if result != 0:
            self.error(str(result))
        return result

    get_controller_status_local = _streak_camera_methods_power_dependency_ready_state["get_controller_status_local"]

    turn_on_local = _streak_camera_methods_power_dependency_ready_state["turn_on_local"]

    _connect_remoteex = _streak_camera_methods_power_dependency_ready_state["_connect_remoteex"]

    turn_off_local = _streak_camera_methods_power_dependency_ready_state["turn_off_local"]

    _create_client = _streak_camera_methods_power_dependency_ready_state["_create_client"]

    _windows_process_running = (staticmethod)(_streak_camera_methods_power_dependency_ready_state["_windows_process_running"])

    _require_controller = _streak_camera_methods_power_dependency_ready_state["_require_controller"]

    _reset_remoteex_connection = _streak_camera_methods_power_dependency_ready_state["_reset_remoteex_connection"]

    _prepare_dg645_for_hpdta = _streak_camera_methods_power_dependency_ready_state["_prepare_dg645_for_hpdta"]

    _sync_from_snapshot = _streak_camera_methods_power_dependency_ready_state["_sync_from_snapshot"]

    _float_or_zero = (staticmethod)(_streak_camera_methods_power_dependency_ready_state["_float_or_zero"])

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

    write_live_exposure_time = _streak_camera_methods_power_dependency_ready_state["write_live_exposure_time"]

    @attribute(label="acquire exposure time", dtype=str, access=AttrWriteType.READ_WRITE)
    def acquire_exposure_time(self):
        return str(self.acquire_exposure_time_value)

    write_acquire_exposure_time = _streak_camera_methods_power_dependency_ready_state["write_acquire_exposure_time"]

    @attribute(
        label="analog integration exposure time",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def analog_integration_exposure_time(self):
        return str(self.analog_integration_exposure_time_value)

    write_analog_integration_exposure_time = _streak_camera_methods_power_dependency_ready_state["write_analog_integration_exposure_time"]

    @attribute(label="live RT backsub", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rt_backsub(self):
        return str(self.live_rt_backsub_value)

    write_live_rt_backsub = _streak_camera_methods_power_dependency_ready_state["write_live_rt_backsub"]

    @attribute(label="live RT shading", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rt_shading(self):
        return str(self.live_rt_shading_value)

    write_live_rt_shading = _streak_camera_methods_power_dependency_ready_state["write_live_rt_shading"]

    @attribute(label="live rolling average", dtype=str, access=AttrWriteType.READ_WRITE)
    def live_rolling_average(self):
        return str(self.live_rolling_average_enabled_value)

    write_live_rolling_average = _streak_camera_methods_power_dependency_ready_state["write_live_rolling_average"]

    @attribute(
        label="live rolling average number",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def live_rolling_average_number(self):
        return str(self.live_rolling_average_number_value)

    write_live_rolling_average_number = _streak_camera_methods_power_dependency_ready_state["write_live_rolling_average_number"]

    @attribute(
        label="analog integration count",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def analog_integration_count(self):
        return str(self.analog_integration_count_value)

    write_analog_integration_count = _streak_camera_methods_power_dependency_ready_state["write_analog_integration_count"]

    @attribute(
        label="sequence acquisition mode",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def sequence_acquisition_mode(self):
        return str(self.sequence_acquisition_mode_value)

    write_sequence_acquisition_mode = _streak_camera_methods_power_dependency_ready_state["write_sequence_acquisition_mode"]

    @attribute(label="sequence loops", dtype=str, access=AttrWriteType.READ_WRITE)
    def sequence_loops(self):
        return str(self.sequence_loops_value)

    write_sequence_loops = _streak_camera_methods_power_dependency_ready_state["write_sequence_loops"]

    @attribute(
        label="sequence acquisition speed",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
    )
    def sequence_acquisition_speed(self):
        return str(self.sequence_acquisition_speed_value)

    write_sequence_acquisition_speed = _streak_camera_methods_power_dependency_ready_state["write_sequence_acquisition_speed"]

    @attribute(label="time range", dtype=str, access=AttrWriteType.READ_WRITE)
    def time_range(self):
        return str(self.current_time_range_value)

    write_time_range = _streak_camera_methods_power_dependency_ready_state["write_time_range"]

    @attribute(label="streak mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_mode(self):
        return str(self.current_streak_mode_value)

    write_streak_mode = _streak_camera_methods_power_dependency_ready_state["write_streak_mode"]

    @attribute(label="gate mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def gate_mode(self):
        return str(self.current_gate_mode_value)

    write_gate_mode = _streak_camera_methods_power_dependency_ready_state["write_gate_mode"]

    @attribute(label="MCP gain", dtype=str, access=AttrWriteType.READ)
    def mcp_gain_text(self):
        return str(self.current_mcp_gain_value)

    @attribute(label="streak shutter", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_shutter(self):
        return str(self.current_streak_shutter_value)

    write_streak_shutter = _streak_camera_methods_power_dependency_ready_state["write_streak_shutter"]

    @attribute(label="streak trig mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def streak_trig_mode(self):
        return str(self.current_streak_trig_mode_value)

    write_streak_trig_mode = _streak_camera_methods_power_dependency_ready_state["write_streak_trig_mode"]

    @attribute(label="streak trigger status", dtype=str, access=AttrWriteType.READ)
    def streak_trigger_status(self):
        return str(self.current_streak_trigger_status_value)

    @attribute(label="focus time over", dtype=str, access=AttrWriteType.READ_WRITE)
    def focus_time_over(self):
        return str(self.current_focus_time_over_value)

    write_focus_time_over = _streak_camera_methods_power_dependency_ready_state["write_focus_time_over"]

    @attribute(label="wavelength nm", dtype=float, access=AttrWriteType.READ_WRITE)
    def wavelength_nm(self):
        try:
            return float(self.current_wavelength_value)
        except Exception:
            return 0.0

    write_wavelength_nm = _streak_camera_methods_power_dependency_ready_state["write_wavelength_nm"]

    @attribute(label="grating", dtype=str, access=AttrWriteType.READ_WRITE)
    def grating(self):
        return str(self.current_grating_value)

    write_grating = _streak_camera_methods_power_dependency_ready_state["write_grating"]

    @attribute(label="slit width um", dtype=float, access=AttrWriteType.READ_WRITE)
    def slit_width_um(self):
        try:
            return float(self.current_slit_width_value)
        except Exception:
            return 0.0

    write_slit_width_um = _streak_camera_methods_power_dependency_ready_state["write_slit_width_um"]

    @attribute(label="spectrograph shutter", dtype=str, access=AttrWriteType.READ_WRITE)
    def spectrograph_shutter(self):
        return str(self.current_spectrograph_shutter_value)

    write_spectrograph_shutter = _streak_camera_methods_power_dependency_ready_state["write_spectrograph_shutter"]

    @attribute(label="blaze", dtype=str, access=AttrWriteType.READ)
    def blaze(self):
        return str(self.current_blaze_value)

    @attribute(label="ruling", dtype=str, access=AttrWriteType.READ)
    def ruling(self):
        return str(self.current_ruling_value)

    @attribute(label="exit mirror", dtype=str, access=AttrWriteType.READ_WRITE)
    def exit_mirror(self):
        return str(self.current_exit_mirror_value)

    write_exit_mirror = _streak_camera_methods_power_dependency_ready_state["write_exit_mirror"]

    @attribute(label="turret", dtype=str, access=AttrWriteType.READ_WRITE)
    def turret(self):
        return str(self.current_turret_value)

    write_turret = _streak_camera_methods_power_dependency_ready_state["write_turret"]

    @attribute(label="focus mirror", dtype=str, access=AttrWriteType.READ_WRITE)
    def focus_mirror(self):
        return str(self.current_focus_mirror_value)

    write_focus_mirror = _streak_camera_methods_power_dependency_ready_state["write_focus_mirror"]

    @attribute(label="side entry iris", dtype=str, access=AttrWriteType.READ_WRITE)
    def side_entry_iris(self):
        return str(self.current_side_entry_iris_value)

    write_side_entry_iris = _streak_camera_methods_power_dependency_ready_state["write_side_entry_iris"]

    @attribute(label="delay trig mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_trig_mode(self):
        return str(self.current_delay_trig_mode_value)

    write_delay_trig_mode = _streak_camera_methods_power_dependency_ready_state["write_delay_trig_mode"]

    @attribute(label="delay repetition rate", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_repetition_rate(self):
        return str(self.current_delay_repetition_rate_value)

    write_delay_repetition_rate = _streak_camera_methods_power_dependency_ready_state["write_delay_repetition_rate"]

    @attribute(label="delay setting", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_setting(self):
        return str(self.current_delay_setting_value)

    write_delay_setting = _streak_camera_methods_power_dependency_ready_state["write_delay_setting"]

    @attribute(label="delay A", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_a(self):
        return str(self.current_delay_a_value)

    write_delay_a = _streak_camera_methods_power_dependency_ready_state["write_delay_a"]

    @attribute(label="delay B", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_b(self):
        return str(self.current_delay_b_value)

    write_delay_b = _streak_camera_methods_power_dependency_ready_state["write_delay_b"]

    @attribute(label="delay C", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_c(self):
        return str(self.current_delay_c_value)

    write_delay_c = _streak_camera_methods_power_dependency_ready_state["write_delay_c"]

    @attribute(label="delay D", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_d(self):
        return str(self.current_delay_d_value)

    write_delay_d = _streak_camera_methods_power_dependency_ready_state["write_delay_d"]
    del _streak_camera_methods_power_dependency_ready_state

    @attribute(label="delay E", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_e(self):
        return str(self.current_delay_e_value)

    _streak_camera_methods_write_delay_e = _bind_streak_camera_methods_write_delay_e(_refactor_modules[__name__])
    write_delay_e = _streak_camera_methods_write_delay_e["write_delay_e"]

    @attribute(label="delay F", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_f(self):
        return str(self.current_delay_f_value)

    write_delay_f = _streak_camera_methods_write_delay_e["write_delay_f"]

    @attribute(label="delay G", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_g(self):
        return str(self.current_delay_g_value)

    write_delay_g = _streak_camera_methods_write_delay_e["write_delay_g"]

    @attribute(label="delay H", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_h(self):
        return str(self.current_delay_h_value)

    write_delay_h = _streak_camera_methods_write_delay_e["write_delay_h"]

    @attribute(label="delay ss trigger", dtype=str, access=AttrWriteType.READ)
    def delay_ss_trigger(self):
        return str(self.current_delay_ss_trigger_value)

    @attribute(label="delay burst mode", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_burst_mode(self):
        return str(self.current_delay_burst_mode_value)

    write_delay_burst_mode = _streak_camera_methods_write_delay_e["write_delay_burst_mode"]

    @attribute(label="delay manual control", dtype=str, access=AttrWriteType.READ_WRITE)
    def delay_manual_control(self):
        return str(self.current_delay_manual_control_value)

    write_delay_manual_control = _streak_camera_methods_write_delay_e["write_delay_manual_control"]

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

    StartRemoteEx = (command)(_streak_camera_methods_write_delay_e["StartRemoteEx"])

    StopRemoteEx = (command)(_streak_camera_methods_write_delay_e["StopRemoteEx"])

    @command(dtype_out=str)
    def PrepareDG645ForHPDTA(self):
        """Apply VD2 Recall 9 for a legacy full-profile session."""
        if getattr(self, "remote_camera_only", False) or getattr(getattr(self, "controller", None), "camera_only", False):
            raise RuntimeError("DG645 timing is owned by the DG645 Tango server")
        self._prepare_dg645_for_hpdta()
        self.last_response_value = (
            f"DG645 Recall {int(self.dg645_hpdta_recall_slot or 9)} applied; BURM=0"
        )
        return self.last_response_value

    @command
    def RefreshStatus(self):
        if any(
            thread is not None and thread.is_alive()
            for thread in (self._live_start_thread, self._application_start_thread)
        ):
            return json.dumps(
                {
                    "connected": self.connected_value,
                    "application_running": self.application_running_value,
                    "remoteex_status": self.remoteex_status_value,
                    "busy_command": self.busy_command_value,
                }
            )
        controller = self._require_controller()
        try:
            snapshot = controller.refresh_cached_state()
            self._sync_from_snapshot(snapshot)
        except RemoteExTransportError as exc:
            self._reset_remoteex_connection(exc)
        return json.dumps(
            {
                "connected": self.connected_value,
                "application_running": self.application_running_value,
                "remoteex_status": self.remoteex_status_value,
                "busy_command": self.busy_command_value,
            }
        )

    StartApplication = (command)(_streak_camera_methods_write_delay_e["StartApplication"])

    StartCameraOnlyApplication = (command)(_streak_camera_methods_write_delay_e["StartCameraOnlyApplication"])

    _launch_application = _streak_camera_methods_write_delay_e["_launch_application"]

    @attribute(dtype=bool, access=AttrWriteType.READ)
    def camera_only_application(self):
        return self._camera_only_profile_verified()

    def _camera_only_profile_verified(self):
        controller = self.controller
        return bool(controller and controller.camera_only_identity and self.application_running_value
                    and controller.camera_only_identity == remoteex_process_identity())

    _start_application_background = _streak_camera_methods_write_delay_e["_start_application_background"]

    @command
    def PrepareVD2Startup(self):
        """Apply the VD2 optical profile to an already running HPD-TA."""
        if not self._power_dependency_allows_hardware_operation(force=True):
            raise RuntimeError(self._power_dependency_status)
        if (
            self._application_start_thread is not None
            and self._application_start_thread.is_alive()
        ):
            return

        controller = self._require_controller()
        self._startup_configuration_error = ""
        self.remoteex_status_value = "preparing"
        self.busy_command_value = "VD2 startup configuration"
        self.set_state(DevState.RUNNING)
        self._application_start_thread = threading.Thread(
            target=self._configure_vd2_startup_background,
            args=(controller,),
            daemon=True,
            name="hamamatsu-prepare-vd2",
        )
        self._application_start_thread.start()

    _configure_vd2_startup_background = _streak_camera_methods_write_delay_e["_configure_vd2_startup_background"]

    @command
    def StopApplication(self):
        controller = self._require_controller()
        try:
            controller.stop_application()
        except Exception as exc:
            # HPD-TA may have accepted AppEnd() and closed RemoteEx before the
            # reply reaches us. Confirm the local process rather than leaving
            # a stale application_running flag that blocks shutdown.
            if self._windows_process_running("HPDTA95.exe"):
                raise
            if getattr(controller, "camera_only", False) and remoteex_process_identity() is not None:
                try:
                    controller.execute_raw("AcqStatus()")
                except Exception as probe:
                    if "3,acqstatus,application not running" not in str(probe).lower():
                        raise RuntimeError("HPD-TA application exit is unverified") from probe
                else:
                    raise RuntimeError("HPD-TA remains active in TaRemoteEx") from exc
            self.last_response_value = f"AppEnd closed RemoteEx socket: {exc}"
        controller.camera_only_identity = None
        self.application_running_value = False
        self._startup_configuration_error = ""
        self.remoteex_status_value = "idle"
        self.busy_command_value = ""
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text
        self.set_state(DevState.ON)

    @command
    def ShutdownRemoteEx(self):
        controller = self._require_controller()
        controller.shutdown_remoteex()
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.busy_command_value = ""
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text
        self.set_state(DevState.ON)

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
        if self._live_start_thread is not None and self._live_start_thread.is_alive():
            return

        controller = self._require_controller()
        self.remoteex_status_value = "starting"
        self.busy_command_value = "AcqStart(Live)"
        self.set_state(DevState.RUNNING)
        if self.remote_camera_only:
            self._start_live_background(controller, propagate=True)
            return
        self._live_start_thread = threading.Thread(
            target=self._start_live_background,
            args=(controller,),
            daemon=True,
            name="hamamatsu-start-live",
        )
        self._live_start_thread.start()

    _start_live_background = _streak_camera_methods_write_delay_e["_start_live_background"]

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
        self._sequence_reconnect_pending = False
        self.remoteex_status_value = "busy"
        self.set_state(DevState.RUNNING)

    @command
    def StopAcquisition(self):
        controller = self._require_controller()
        controller.stop_acquisition()
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text
        self.remoteex_status_value = "idle"
        self.busy_command_value = ""
        self.set_state(DevState.ON)

    @command
    def StopSequence(self):
        controller = self._require_controller()
        controller.stop_sequence()
        self.last_command_value = controller.last_command
        self.last_response_value = controller.last_response_text
        self.remoteex_status_value = "idle"
        self.busy_command_value = ""
        self.set_state(DevState.ON)

    @command
    def StartPairedLive(self):
        if not self._camera_only_profile_verified():
            raise RuntimeError("Paired capture requires the camera-only HPD-TA profile")
        controller = self._require_controller()
        controller.client.start_paired_monitor()
        self.set_state(DevState.RUNNING)
        self._start_live_background(controller, propagate=True)

    @command(dtype_in=int, dtype_out=str)
    def ReadPairedLiveFrame(self, sequence: int):
        frame = self._require_controller().client.read_paired_image(sequence)
        if frame is None:
            return ""
        return json.dumps({
            "width": frame.width, "height": frame.height, "bytes_per_pixel": frame.bytes_per_pixel,
            "sequence": frame.sequence_number, "timestamp_ms": frame.timestamp_ms,
            "pixels_b64": base64.b64encode(frame.pixels).decode("ascii"),
        })

    @command
    def StopPairedLive(self):
        controller = self._require_controller()
        try:
            # AcqStart may have failed before triggering, so check native state.
            if controller.execute_raw("AcqStatus()").raw_line.strip().lower() != "0,acqstatus,idle":
                self.StopAcquisition()
            if controller.execute_raw("AcqStatus()").raw_line.strip().lower() != "0,acqstatus,idle":
                raise RuntimeError("Paired HPD-TA acquisition is not confirmed idle")
        finally:
            controller.client.stop_paired_monitor()
        self.remoteex_status_value = "idle"
        self.busy_command_value = ""
        self.set_state(DevState.ON)

    @command(dtype_out=str)
    def GetCurrentDisplayFrame(self):
        """Return one rendered HPD-TA frame through the sole RemoteEx client."""
        controller = self._require_controller()
        frame = controller.get_current_display_image()
        return json.dumps(
            {
                "width": frame.width,
                "height": frame.height,
                "bytes_per_pixel": frame.bytes_per_pixel,
                "data_type": frame.data_type,
                "pixels_b64": base64.b64encode(frame.pixels).decode("ascii"),
            }
        )

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
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        saved = controller.save_current_sequence_his(path)
        deadline = time.monotonic() + 5.0
        while not target.is_file() and time.monotonic() < deadline:
            time.sleep(0.2)
        if not target.is_file():
            raise RuntimeError(f"RemoteEx reported HIS save complete, but file is missing: {path}")
        self.last_saved_sequence_path_value = saved
        self.get_controller_status()
        return saved

    @command(dtype_in=str, dtype_out=str)
    def DumpCurrentImageData(self, path: str):
        controller = self._require_controller()
        return controller.dump_current_image_data(path)

    ExecuteRaw = (command(dtype_in=str, dtype_out=str))(_streak_camera_methods_write_delay_e["ExecuteRaw"])
    del _streak_camera_methods_write_delay_e

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
