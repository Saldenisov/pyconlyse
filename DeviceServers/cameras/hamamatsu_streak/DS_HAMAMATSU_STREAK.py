#!/usr/bin/python3 -u
from __future__ import annotations

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

from tango import AttrWriteType, DevState, DeviceProxy
from tango.server import attribute, command, device_property

from DeviceServers.base.general import DS_General
from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import (
    HamamatsuStreakController,
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
        self._application_start_thread = None
        self._live_start_thread = None
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
        try:
            # DS_General declares this command at 300 ms. HPD-TA RemoteEx cannot
            # service that rate while acquiring; the web API requests refreshes.
            self.stop_poll_command("get_controller_status")
        except Exception:
            pass
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

    def power_dependency_ready_state(self):
        """RemoteEx is a Tango companion service, not the camera power state."""
        return DevState.ON

    def _handle_power_dependency_off(self, detail: str) -> None:
        self._power_probe_pending = False
        self._power_probe_due_at = 0.0
        self._power_dependency_status = (
            f"Streak hardware power is OFF ({detail}); RemoteEx service remains available."
        )
        # Keep Tango ON: it represents the controller process, while the
        # dependency attribute represents the separately switched hardware.
        self._mark_hardware_power_off(
            self._power_dependency_status, tango_state=DevState.ON
        )

    def _handle_power_dependency_unavailable(self, detail: str) -> None:
        self._power_dependency_status = f"Streak hardware power is unknown: {detail}"
        self.set_hardware_lifecycle(
            "POWER_STATUS_UNAVAILABLE", "UNKNOWN", self._power_dependency_status
        )
        self.set_state(DevState.ON)
        self.warn(self._power_dependency_status, True)

    def probe_powered_hardware(self) -> Union[int, str]:
        """A PDU transition must not launch HPD-TA or issue camera commands."""
        return 0

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

    @command(polling_period=0)
    def get_controller_status(self):
        """Refresh only on demand without DS_General's auto-turn-on loop.

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

    def get_controller_status_local(self) -> Union[int, str]:
        if self.controller is None or not self.controller.is_connected:
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(DevState.ON)
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
            self._reset_remoteex_connection(exc)
            return f"RemoteEx status refresh failed: {exc}"

    def turn_on_local(self) -> Union[int, str]:
        try:
            self._connect_remoteex()

            if bool(int(self.start_application_on_turn_on or 0)):
                self.controller.start_application()
            else:
                # RemoteEx can accept TCP connections while HPD-TA is stopped.
                # Probe once after an explicit connection so the web UI is not
                # left with the default "stopped" cache when HPD-TA is already
                # running. A failed probe still leaves the RemoteEx layer ON.
                try:
                    snapshot = self.controller.refresh_cached_state()
                    self._sync_from_snapshot(snapshot)
                    self.set_state(
                        DevState.RUNNING
                        if self.remoteex_status_value.lower() == "busy"
                        else DevState.ON
                    )
                except Exception:
                    self.application_running_value = False
                    self.remoteex_status_value = "idle"
                    self.busy_command_value = ""
                    self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.client = None
            self.controller = None
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(DevState.ON)
            return f"Could not start Hamamatsu streak RemoteEx layer: {exc}"

    def _connect_remoteex(self) -> None:
        """Attach this Tango device to an already-running local RemoteEx."""
        client = self._create_client()
        controller = HamamatsuStreakController(
            client,
            ini_path=str(self.ini_path or ""),
            default_save_dir=str(self.default_save_dir or ""),
            async_timeout=float(self.async_timeout_s or 120.0),
        )
        try:
            controller.connect(connect_data_port=bool(int(self.connect_data_port or 0)))
        except Exception:
            client.close()
            raise
        self.client = client
        self.controller = controller
        self.connected_value = True

    def turn_off_local(self) -> Union[int, str]:
        """Detach RemoteEx without stopping the Tango device server."""
        try:
            if self.controller is not None:
                self.controller.disconnect()
        finally:
            self.controller = None
            self.client = None
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(DevState.ON)
        return 0

    def _create_client(self) -> RemoteExClient:
        return RemoteExClient(
            host=str(self.host or "localhost"),
            command_port=int(self.command_port or 1001),
            data_port=int(self.data_port or 1002),
            timeout=float(self.command_timeout_s or 5.0),
            encoding=str(self.command_encoding or "ascii"),
        )

    @staticmethod
    def _windows_process_running(image_name: str) -> bool:
        completed = subprocess.run(
            ["tasklist.exe", "/fi", f"imagename eq {image_name}", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return image_name.lower() in completed.stdout.lower()

    def _require_controller(self) -> HamamatsuStreakController:
        if self.controller is None or not self.controller.is_connected:
            raise RuntimeError("Hamamatsu streak controller is not connected")
        return self.controller

    def _reset_remoteex_connection(self, reason: Exception | str) -> None:
        """Discard a stale RemoteEx socket without faulting the Tango launcher."""
        if self.controller is not None:
            try:
                self.controller.disconnect()
            except Exception:
                pass
        self.controller = None
        self.client = None
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.busy_command_value = ""
        self.last_response_value = f"RemoteEx unavailable: {reason}"
        self.set_state(DevState.ON)

    def _prepare_dg645_for_hpdta(self) -> None:
        """Apply the VD2 timing preset before HPD-TA starts.

        Recall 9 is the VD2 timing preset. Burst mode is explicitly disabled
        after recall: the streak acquisition must receive one normal trigger
        per shot rather than a V0 burst train. This does not overwrite Recall 9.
        """
        device = str(self.dg645_device or "manip/sync/DG645")
        recall_slot = int(self.dg645_hpdta_recall_slot or 9)
        dg645 = DeviceProxy(device)
        dg645.set_timeout_millis(8000)
        dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
        time.sleep(float(self.dg645_recall_wait_s or 1.0))
        dg645.command_inout("scpi_write", "BURM 0")
        dg645.command_inout("scpi_query", "*OPC?")
        burst_mode = str(dg645.command_inout("scpi_query", "BURM?")).strip()
        if burst_mode not in {"0", "0.0", "+0", "+0.0"}:
            raise RuntimeError(
                f"DG645 recall {recall_slot} left burst mode enabled (BURM?={burst_mode})"
            )

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
    def StartRemoteEx(self):
        """Launch RemoteEx locally, then connect this Tango device to it.

        The web application never starts Windows processes directly. Astor starts
        this device server; this command starts only RemoteEx through its Windows
        scheduled task. HPD-TA itself is started later by StartApplication.
        """
        if self.controller is not None and self.controller.is_connected:
            return

        # A Tango restart must not create a second RemoteEx process. Attach to
        # the existing command socket first, then start the scheduled task only
        # when no RemoteEx instance accepts connections.
        try:
            self._connect_remoteex()
            self.application_running_value = False
            self.remoteex_status_value = "idle"
            self.busy_command_value = ""
            self.set_state(DevState.ON)
            return
        except Exception:
            self.client = None
            self.controller = None
            self.connected_value = False

        task_name = str(self.remoteex_task_name or "Pyconlyse-TaRemoteEx")
        completed = subprocess.run(
            ["schtasks.exe", "/run", "/tn", f"\\{task_name}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "scheduled task failed").strip()
            raise RuntimeError(f"Could not start RemoteEx task {task_name}: {detail}")

        deadline = time.monotonic() + float(self.remoteex_start_timeout_s or 12.0)
        last_error = None
        while time.monotonic() < deadline:
            try:
                self._connect_remoteex()
                self.application_running_value = False
                self.remoteex_status_value = "idle"
                self.busy_command_value = ""
                self.set_state(DevState.ON)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.4)
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.set_state(DevState.FAULT)
        raise RuntimeError(f"RemoteEx did not accept TCP connections: {last_error}")

    @command
    def StopRemoteEx(self):
        """Stop RemoteEx after HPD-TA has been closed."""
        if self.application_running_value and self._windows_process_running("HPDTA95.exe"):
            raise RuntimeError("Close HPD-TA before stopping RemoteEx")
        self.application_running_value = False
        controller = self.controller
        shutdown_error = None
        if controller is not None and controller.is_connected:
            try:
                controller.shutdown_remoteex()
            except Exception as exc:
                shutdown_error = exc

        if self._windows_process_running("TaRemoteEx.exe"):
            # RemoteEx runs elevated through its interactive scheduled task.
            # A non-elevated Tango device server cannot taskkill that process.
            # The dedicated stop task runs taskkill in the same elevated
            # interactive context as the RemoteEx launcher.
            task_name = str(
                self.remoteex_stop_task_name or "Pyconlyse-Stop-TaRemoteEx"
            )
            completed = subprocess.run(
                ["schtasks.exe", "/run", "/tn", f"\\{task_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            deadline = time.monotonic() + 10.0
            while (
                self._windows_process_running("TaRemoteEx.exe")
                and time.monotonic() < deadline
            ):
                time.sleep(0.25)
            if self._windows_process_running("TaRemoteEx.exe"):
                detail = (completed.stderr or completed.stdout or str(shutdown_error)).strip()
                raise RuntimeError(
                    f"Could not stop TaRemoteEx through elevated task {task_name}: {detail}"
                ) from shutdown_error
        self.controller = None
        self.client = None
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.busy_command_value = ""
        self.last_command_value = (
            controller.last_command
            if controller is not None
            else "schtasks /run stop TaRemoteEx"
        )
        self.last_response_value = controller.last_response_text if controller is not None else "TaRemoteEx stopped"
        # RemoteEx is an optional companion process. Its absence must not make
        # this still-running Tango device appear offline in the web control.
        self.set_state(DevState.ON)

    @command(dtype_out=str)
    def PrepareDG645ForHPDTA(self):
        """Apply VD2 Recall 9 and verify that burst mode is disabled."""
        self._prepare_dg645_for_hpdta()
        self.last_response_value = (
            f"DG645 Recall {int(self.dg645_hpdta_recall_slot or 9)} applied; BURM=0"
        )
        return self.last_response_value

    @command
    def RefreshStatus(self):
        if self._live_start_thread is not None and self._live_start_thread.is_alive():
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

    @command
    def StartApplication(self):
        if not self._power_dependency_allows_hardware_operation(force=True):
            raise RuntimeError(self._power_dependency_status)

        if (
            self._application_start_thread is not None
            and self._application_start_thread.is_alive()
        ):
            return self.application_version_value

        controller = self._require_controller()
        self.busy_command_value = f"DG645 Recall {int(self.dg645_hpdta_recall_slot or 9)}"
        try:
            self._prepare_dg645_for_hpdta()
        except Exception as exc:
            self.busy_command_value = ""
            self.last_response_value = f"DG645 preflight failed: {exc}"
            self.remoteex_status_value = "idle"
            self.set_state(DevState.ON)
            raise RuntimeError(self.last_response_value) from exc
        self.remoteex_status_value = "starting"
        self.busy_command_value = "AppStart()"
        self.set_state(DevState.RUNNING)
        self._application_start_thread = threading.Thread(
            target=self._start_application_background,
            args=(controller,),
            daemon=True,
            name="hamamatsu-start-application",
        )
        self._application_start_thread.start()
        return self.application_version_value

    def _start_application_background(
        self, controller: HamamatsuStreakController
    ) -> None:
        try:
            controller.start_application()
            snapshot = controller.refresh_cached_state()
            self._sync_from_snapshot(snapshot)
            self.last_command_value = controller.last_command
            self.last_response_value = controller.last_response_text
            self.application_running_value = True
            self.remoteex_status_value = "idle"
            self.busy_command_value = ""
            self.set_state(DevState.ON)
        except Exception as exc:
            self._reset_remoteex_connection(f"StartApplication failed: {exc}")

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
            self.last_response_value = f"AppEnd closed RemoteEx socket: {exc}"
        self.application_running_value = False
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
        self._live_start_thread = threading.Thread(
            target=self._start_live_background,
            args=(controller,),
            daemon=True,
            name="hamamatsu-start-live",
        )
        self._live_start_thread.start()

    def _start_live_background(self, controller: HamamatsuStreakController) -> None:
        try:
            controller.start_live()
            self.last_command_value = controller.last_command
            self.last_response_value = controller.last_response_text
            self.remoteex_status_value = "busy"
        except Exception as exc:
            self.last_response_value = f"StartLive failed: {exc}"
            self.remoteex_status_value = "fault"
            self.set_state(DevState.FAULT)

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
