"""Implementation for power_dependency_ready_state and related operations."""

from __future__ import annotations


def _bind_streak_camera_methods_power_dependency_ready_state(api):
    """Bind implementation to the owning module and its runtime state."""

    def power_dependency_ready_state(self):
        """RemoteEx is a Tango companion service, not the camera power state."""
        return api.DevState.ON

    def _handle_power_dependency_off(self, detail: str) -> None:
        self._power_probe_pending = False
        self._power_probe_due_at = 0.0
        self._power_dependency_status = (
            f"Streak hardware power is OFF ({detail}); RemoteEx service remains available."
        )
        # Keep Tango ON: it represents the controller process, while the
        # dependency attribute represents the separately switched hardware.
        self._mark_hardware_power_off(
            self._power_dependency_status, tango_state=api.DevState.ON
        )

    def _handle_power_dependency_unavailable(self, detail: str) -> None:
        self._power_dependency_status = f"Streak hardware power is unknown: {detail}"
        self.set_hardware_lifecycle(
            "POWER_STATUS_UNAVAILABLE", "UNKNOWN", self._power_dependency_status
        )
        self.set_state(api.DevState.ON)
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

    def get_controller_status_local(self) -> Union[int, str]:
        # The start workers own the RemoteEx command socket until they finish.
        if any(
            thread is not None and thread.is_alive()
            for thread in (self._application_start_thread, self._live_start_thread)
        ):
            return 0
        if self.controller is None or not self.controller.is_connected:
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            if self._startup_configuration_error:
                self.set_state(api.DevState.FAULT)
                self.set_status(self._startup_configuration_error)
            else:
                self.set_state(api.DevState.ON)
            return 0

        try:
            snapshot = self.controller.refresh_cached_state()
            self._sync_from_snapshot(snapshot)
            if self._startup_configuration_error:
                self.set_state(api.DevState.FAULT)
                self.set_status(self._startup_configuration_error)
            elif self.remoteex_status_value.lower() == "busy":
                self.set_state(api.DevState.RUNNING)
            else:
                self.set_state(api.DevState.ON)
            return 0
        except Exception as exc:
            self._reset_remoteex_connection(exc)
            return f"RemoteEx status refresh failed: {exc}"

    def turn_on_local(self) -> Union[int, str]:
        try:
            self._connect_remoteex()

            if bool(int(self.start_application_on_turn_on or 0)) and not getattr(self.controller, "camera_only", False):
                self.controller.start_application()
                try:
                    snapshot = self.controller.configure_vd2_startup()
                except Exception as exc:
                    self._startup_configuration_error = (
                        f"VD2 startup configuration failed: {exc}"
                    )
                    self.application_running_value = True
                    self.set_state(api.DevState.FAULT)
                    self.set_status(self._startup_configuration_error)
                    return self._startup_configuration_error
                self._sync_from_snapshot(snapshot)
                self._startup_configuration_error = ""
                self.set_state(api.DevState.ON)
            else:
                # RemoteEx can accept TCP connections while HPD-TA is stopped.
                # Probe once after an explicit connection so the web UI is not
                # left with the default "stopped" cache when HPD-TA is already
                # running. A failed probe still leaves the RemoteEx layer ON.
                try:
                    snapshot = self.controller.refresh_cached_state()
                    self._sync_from_snapshot(snapshot)
                    self.set_state(
                        api.DevState.RUNNING
                        if self.remoteex_status_value.lower() == "busy"
                        else api.DevState.ON
                    )
                except Exception:
                    self.application_running_value = False
                    self.remoteex_status_value = "idle"
                    self.busy_command_value = ""
                    self.set_state(api.DevState.ON)
            return 0
        except Exception as exc:
            self.client = None
            self.controller = None
            self.connected_value = False
            self.application_running_value = False
            self.remoteex_status_value = "disconnected"
            self.set_state(api.DevState.ON)
            return f"Could not start Hamamatsu streak RemoteEx layer: {exc}"

    def _connect_remoteex(self) -> None:
        """Attach this Tango device to an already-running local RemoteEx."""
        client = self._create_client()
        controller = api.HamamatsuStreakController(
            client,
            ini_path=str(self.ini_path or ""),
            default_save_dir=str(self.default_save_dir or ""),
            async_timeout=float(self.async_timeout_s or 120.0),
        )
        controller.camera_only = bool(getattr(self, "remote_camera_only", False))
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
            self.set_state(api.DevState.ON)
        return 0

    def _create_client(self) -> RemoteExClient:
        return api.RemoteExClient(
            host=str(self.host or "localhost"),
            command_port=int(self.command_port or 1001),
            data_port=int(self.data_port or 1002),
            timeout=float(self.command_timeout_s or 5.0),
            encoding=str(self.command_encoding or "ascii"),
        )

    def _windows_process_running(image_name: str) -> bool:
        completed = api.subprocess.run(
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
        if self._startup_configuration_error:
            self.set_state(api.DevState.FAULT)
            self.set_status(self._startup_configuration_error)
        else:
            self.set_state(api.DevState.ON)

    def _prepare_dg645_for_hpdta(self) -> None:
        """Apply the VD2 timing preset before HPD-TA starts.

        Recall 9 is the VD2 timing preset. Burst mode is explicitly disabled
        after recall: the streak acquisition must receive one normal trigger
        per shot rather than a V0 burst train. This does not overwrite Recall 9.
        """
        device = str(self.dg645_device or "manip/sync/DG645")
        recall_slot = int(self.dg645_hpdta_recall_slot or 9)
        dg645 = api.DeviceProxy(device)
        dg645.set_timeout_millis(8000)
        dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
        api.time.sleep(float(self.dg645_recall_wait_s or 1.0))
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

    def _float_or_zero(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def write_live_exposure_time(self, value: str):
        controller = self._require_controller()
        self.live_exposure_time_value = controller.set_live_exposure_time(str(value))

    def write_acquire_exposure_time(self, value: str):
        controller = self._require_controller()
        self.acquire_exposure_time_value = controller.set_acquire_exposure_time(str(value))

    def write_analog_integration_exposure_time(self, value: str):
        controller = self._require_controller()
        self.analog_integration_exposure_time_value = (
            controller.set_analog_integration_exposure_time(str(value))
        )

    def write_live_rt_backsub(self, value: str):
        controller = self._require_controller()
        self.live_rt_backsub_value = controller.set_live_rt_backsub(str(value))

    def write_live_rt_shading(self, value: str):
        controller = self._require_controller()
        self.live_rt_shading_value = controller.set_live_rt_shading(str(value))

    def write_live_rolling_average(self, value: str):
        controller = self._require_controller()
        self.live_rolling_average_enabled_value = (
            controller.set_live_rolling_average_enabled(str(value))
        )

    def write_live_rolling_average_number(self, value: str):
        controller = self._require_controller()
        self.live_rolling_average_number_value = (
            controller.set_live_rolling_average_number(str(value))
        )

    def write_analog_integration_count(self, value: str):
        controller = self._require_controller()
        self.analog_integration_count_value = controller.set_analog_integration_count(
            str(value)
        )

    def write_sequence_acquisition_mode(self, value: str):
        controller = self._require_controller()
        self.sequence_acquisition_mode_value = controller.set_sequence_acquisition_mode(
            str(value)
        )

    def write_sequence_loops(self, value: str):
        controller = self._require_controller()
        self.sequence_loops_value = controller.set_sequence_loops(str(value))

    def write_sequence_acquisition_speed(self, value: str):
        controller = self._require_controller()
        self.sequence_acquisition_speed_value = controller.set_sequence_acquisition_speed(
            str(value)
        )

    def write_time_range(self, value: str):
        controller = self._require_controller()
        self.current_time_range_value = controller.set_time_range(str(value))

    def write_streak_mode(self, value: str):
        controller = self._require_controller()
        self.current_streak_mode_value = controller.set_streak_mode(str(value))

    def write_gate_mode(self, value: str):
        controller = self._require_controller()
        self.current_gate_mode_value = controller.set_gate_mode(str(value))

    def write_streak_shutter(self, value: str):
        controller = self._require_controller()
        self.current_streak_shutter_value = controller.set_streak_shutter(str(value))

    def write_streak_trig_mode(self, value: str):
        controller = self._require_controller()
        self.current_streak_trig_mode_value = controller.set_streak_trigger_mode(
            str(value)
        )

    def write_focus_time_over(self, value: str):
        controller = self._require_controller()
        self.current_focus_time_over_value = controller.set_focus_time_over(str(value))

    def write_wavelength_nm(self, value: float):
        controller = self._require_controller()
        self.current_wavelength_value = controller.set_wavelength_nm(float(value))

    def write_grating(self, value: str):
        controller = self._require_controller()
        self.current_grating_value = controller.set_grating(str(value))

    def write_slit_width_um(self, value: float):
        controller = self._require_controller()
        self.current_slit_width_value = controller.set_slit_width_um(float(value))

    def write_spectrograph_shutter(self, value: str):
        controller = self._require_controller()
        self.current_spectrograph_shutter_value = controller.set_spectrograph_shutter(
            str(value)
        )

    def write_exit_mirror(self, value: str):
        controller = self._require_controller()
        self.current_exit_mirror_value = controller.set_exit_mirror(str(value))

    def write_turret(self, value: str):
        controller = self._require_controller()
        self.current_turret_value = controller.set_turret(str(value))

    def write_focus_mirror(self, value: str):
        controller = self._require_controller()
        self.current_focus_mirror_value = controller.set_focus_mirror(str(value))

    def write_side_entry_iris(self, value: str):
        controller = self._require_controller()
        self.current_side_entry_iris_value = controller.set_side_entry_iris(str(value))

    def write_delay_trig_mode(self, value: str):
        controller = self._require_controller()
        self.current_delay_trig_mode_value = controller.set_delay_trigger_mode(str(value))

    def write_delay_repetition_rate(self, value: str):
        controller = self._require_controller()
        self.current_delay_repetition_rate_value = controller.set_delay_repetition_rate(
            str(value)
        )

    def write_delay_setting(self, value: str):
        controller = self._require_controller()
        self.current_delay_setting_value = controller.set_delay_setting(str(value))

    def write_delay_a(self, value: str):
        controller = self._require_controller()
        self.current_delay_a_value = controller.set_delay_channel("Delay A", str(value))

    def write_delay_b(self, value: str):
        controller = self._require_controller()
        self.current_delay_b_value = controller.set_delay_channel("Delay B", str(value))

    def write_delay_c(self, value: str):
        controller = self._require_controller()
        self.current_delay_c_value = controller.set_delay_channel("Delay C", str(value))

    def write_delay_d(self, value: str):
        controller = self._require_controller()
        self.current_delay_d_value = controller.set_delay_channel("Delay D", str(value))

    return {
        "power_dependency_ready_state": power_dependency_ready_state,
        "_handle_power_dependency_off": _handle_power_dependency_off,
        "_handle_power_dependency_unavailable": _handle_power_dependency_unavailable,
        "probe_powered_hardware": probe_powered_hardware,
        "find_device": find_device,
        "get_controller_status_local": get_controller_status_local,
        "turn_on_local": turn_on_local,
        "_connect_remoteex": _connect_remoteex,
        "turn_off_local": turn_off_local,
        "_create_client": _create_client,
        "_windows_process_running": _windows_process_running,
        "_require_controller": _require_controller,
        "_reset_remoteex_connection": _reset_remoteex_connection,
        "_prepare_dg645_for_hpdta": _prepare_dg645_for_hpdta,
        "_sync_from_snapshot": _sync_from_snapshot,
        "_float_or_zero": _float_or_zero,
        "write_live_exposure_time": write_live_exposure_time,
        "write_acquire_exposure_time": write_acquire_exposure_time,
        "write_analog_integration_exposure_time": write_analog_integration_exposure_time,
        "write_live_rt_backsub": write_live_rt_backsub,
        "write_live_rt_shading": write_live_rt_shading,
        "write_live_rolling_average": write_live_rolling_average,
        "write_live_rolling_average_number": write_live_rolling_average_number,
        "write_analog_integration_count": write_analog_integration_count,
        "write_sequence_acquisition_mode": write_sequence_acquisition_mode,
        "write_sequence_loops": write_sequence_loops,
        "write_sequence_acquisition_speed": write_sequence_acquisition_speed,
        "write_time_range": write_time_range,
        "write_streak_mode": write_streak_mode,
        "write_gate_mode": write_gate_mode,
        "write_streak_shutter": write_streak_shutter,
        "write_streak_trig_mode": write_streak_trig_mode,
        "write_focus_time_over": write_focus_time_over,
        "write_wavelength_nm": write_wavelength_nm,
        "write_grating": write_grating,
        "write_slit_width_um": write_slit_width_um,
        "write_spectrograph_shutter": write_spectrograph_shutter,
        "write_exit_mirror": write_exit_mirror,
        "write_turret": write_turret,
        "write_focus_mirror": write_focus_mirror,
        "write_side_entry_iris": write_side_entry_iris,
        "write_delay_trig_mode": write_delay_trig_mode,
        "write_delay_repetition_rate": write_delay_repetition_rate,
        "write_delay_setting": write_delay_setting,
        "write_delay_a": write_delay_a,
        "write_delay_b": write_delay_b,
        "write_delay_c": write_delay_c,
        "write_delay_d": write_delay_d,
    }
