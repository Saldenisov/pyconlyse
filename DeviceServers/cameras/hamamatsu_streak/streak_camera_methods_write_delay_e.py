"""Implementation for write_delay_e and related operations."""

from __future__ import annotations


def _bind_streak_camera_methods_write_delay_e(api):
    """Bind implementation to the owning module and its runtime state."""

    def write_delay_e(self, value: str):
        controller = self._require_controller()
        self.current_delay_e_value = controller.set_delay_channel("Delay E", str(value))

    def write_delay_f(self, value: str):
        controller = self._require_controller()
        self.current_delay_f_value = controller.set_delay_channel("Delay F", str(value))

    def write_delay_g(self, value: str):
        controller = self._require_controller()
        self.current_delay_g_value = controller.set_delay_channel("Delay G", str(value))

    def write_delay_h(self, value: str):
        controller = self._require_controller()
        self.current_delay_h_value = controller.set_delay_channel("Delay H", str(value))

    def write_delay_burst_mode(self, value: str):
        controller = self._require_controller()
        self.current_delay_burst_mode_value = controller.set_delay_burst_mode(str(value))

    def write_delay_manual_control(self, value: str):
        controller = self._require_controller()
        self.current_delay_manual_control_value = controller.set_delay_manual_control(
            str(value)
        )

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
            self.set_state(api.DevState.ON)
            return
        except Exception:
            self.client = None
            self.controller = None
            self.connected_value = False

        if not self._windows_process_running("TaRemoteEx.exe"):
            task_name = str(self.remoteex_task_name or "Pyconlyse-TaRemoteEx")
            completed = api.subprocess.run(
                ["schtasks.exe", "/run", "/tn", f"\\{task_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "scheduled task failed").strip()
                raise RuntimeError(f"Could not start RemoteEx task {task_name}: {detail}")

        deadline = api.time.monotonic() + max(30.0, float(self.remoteex_start_timeout_s or 0))
        last_error = None
        while api.time.monotonic() < deadline:
            try:
                self._connect_remoteex()
                self.application_running_value = False
                self.remoteex_status_value = "idle"
                self.busy_command_value = ""
                self.set_state(api.DevState.ON)
                return
            except Exception as exc:
                last_error = exc
                api.time.sleep(0.4)
        self.connected_value = False
        self.application_running_value = False
        self.remoteex_status_value = "disconnected"
        self.set_state(api.DevState.FAULT)
        raise RuntimeError(f"RemoteEx did not accept TCP connections: {last_error}")

    def StopRemoteEx(self):
        """Stop RemoteEx after HPD-TA has been closed."""
        # A disconnected/stale application_running flag is not proof of exit.
        if self._windows_process_running("HPDTA95.exe"):
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
            completed = api.subprocess.run(
                ["schtasks.exe", "/run", "/tn", f"\\{task_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            deadline = api.time.monotonic() + 10.0
            while (
                self._windows_process_running("TaRemoteEx.exe")
                and api.time.monotonic() < deadline
            ):
                api.time.sleep(0.25)
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
        self.set_state(api.DevState.ON)

    def StartApplication(self):
        if getattr(self, "remote_camera_only", False):
            return self.StartCameraOnlyApplication()
        return self._launch_application()

    def StartCameraOnlyApplication(self):
        ini = api.checked_camera_only_ini(self.camera_only_ini_path)
        if self._windows_process_running("HPDTA95.exe"):
            raise RuntimeError("Close the existing HPD-TA session before starting the camera-only profile")
        controller = self._require_controller()
        try:
            controller.execute_raw("AcqStatus()")
        except Exception as exc:
            if "3,acqstatus,application not running" not in str(exc).lower():
                raise RuntimeError("Cannot confirm the RemoteEx host has no HPD-TA session") from exc
        else:
            raise RuntimeError("Close the existing RemoteEx HPD-TA session before starting the camera-only profile")
        return self._launch_application(ini)

    def _launch_application(self, camera_only_ini=None):
        if not self._power_dependency_allows_hardware_operation(force=True):
            raise RuntimeError(self._power_dependency_status)
        if self._application_start_thread is not None and self._application_start_thread.is_alive():
            if camera_only_ini is not None:
                raise RuntimeError("An HPD-TA startup is already in progress")
            return self.application_version_value

        controller = self._require_controller()
        self._startup_configuration_error = ""
        controller.camera_only = camera_only_ini is not None
        controller.camera_only_identity = None
        if camera_only_ini is None:
            self.busy_command_value = f"DG645 Recall {int(self.dg645_hpdta_recall_slot or 9)}"
            try:
                self._prepare_dg645_for_hpdta()
            except Exception as exc:
                self.busy_command_value = ""
                self.last_response_value = f"DG645 preflight failed: {exc}"
                self.remoteex_status_value = "idle"
                self.set_state(api.DevState.ON)
                raise RuntimeError(self.last_response_value) from exc
        self.remoteex_status_value = "starting"
        self.busy_command_value = "AppStart()"
        self.set_state(api.DevState.RUNNING)
        self._application_start_thread = api.threading.Thread(
            target=self._start_application_background,
            args=(controller, camera_only_ini),
            daemon=True,
            name="hamamatsu-start-application",
        )
        self._application_start_thread.start()
        return self.application_version_value

    def _start_application_background(self, controller, camera_only_ini=None) -> None:
        try:
            if camera_only_ini is None:
                controller.start_application()
            else:
                controller.start_application(ini_path=camera_only_ini)
        except Exception as exc:
            self._reset_remoteex_connection(f"StartApplication failed: {exc}")
            self._startup_configuration_error = f"HPD-TA startup failed: {exc}"
            self.set_state(api.DevState.FAULT)
            self.set_status(self._startup_configuration_error)
            return
        self._configure_vd2_startup_background(controller)

    def _configure_vd2_startup_background(
        self, controller: HamamatsuStreakController
    ) -> None:
        try:
            snapshot = controller.configure_vd2_startup()
            if getattr(controller, "camera_only", False):
                identity = api.remoteex_process_identity()
                if identity is None:
                    raise RuntimeError("Cannot identify the camera-only TaRemoteEx host")
                controller.camera_only_identity = identity
            self._sync_from_snapshot(snapshot)
            self.last_command_value = controller.last_command
            self.last_response_value = controller.last_response_text
            self.application_running_value = True
            self.remoteex_status_value = "idle"
            self.busy_command_value = ""
            self._startup_configuration_error = ""
            self.set_state(api.DevState.ON)
        except Exception as exc:
            self._startup_configuration_error = f"VD2 startup configuration failed: {exc}"
            self.last_response_value = self._startup_configuration_error
            self.application_running_value = bool(controller.snapshot.application_running)
            self.remoteex_status_value = "idle"
            self.busy_command_value = ""
            self.set_state(api.DevState.FAULT)
            self.set_status(self._startup_configuration_error)

    def _start_live_background(self, controller: HamamatsuStreakController, *, propagate=False) -> None:
        try:
            controller.start_live()
            self.last_command_value = controller.last_command
            self.last_response_value = controller.last_response_text
            self.remoteex_status_value = "busy"
        except Exception as exc:
            self.last_response_value = f"StartLive failed: {exc}"
            self.remoteex_status_value = "fault"
            self.set_state(api.DevState.FAULT)
            if propagate:
                raise

    def ExecuteRaw(self, command_text: str):
        if command_text == "AsyncCommandStatus()":
            controller = self.controller
            if controller is None or not controller.is_connected:
                if not self._windows_process_running("TaRemoteEx.exe"):
                    raise RuntimeError("RemoteEx sequence connection unavailable; sequence completion unconfirmed")
                self._sequence_reconnect_pending = True
                if controller is None:
                    try:
                        self._connect_remoteex()
                    except api.RemoteExTransportError as exc:
                        raise api.RemoteExTransportError(f"{command_text}: {exc}") from exc
                    controller = self._require_controller()
            response = controller.execute_raw(command_text, reconnect_timeout=2.0, timeout=3.0)
            if self._sequence_reconnect_pending and response.parameters[:3] == ["0", "0", "0"]:
                try:
                    version = controller.execute_raw("AppInfo(Version)", timeout=3.0)
                except api.RemoteExTransportError as exc:
                    raise api.RemoteExTransportError(f"{command_text}: cannot verify HPD-TA after reconnect: {exc}") from exc
                if not (version.parameter(0) or "").strip():
                    raise RuntimeError("HPD-TA application unverified after reconnect; sequence completion unconfirmed")
                self._sequence_reconnect_pending = False
        else:
            controller = self._require_controller()
            response = controller.execute_raw(command_text)
        self.last_command_value = command_text
        self.last_response_value = response.raw_line
        return response.raw_line

    return {
        "write_delay_e": write_delay_e,
        "write_delay_f": write_delay_f,
        "write_delay_g": write_delay_g,
        "write_delay_h": write_delay_h,
        "write_delay_burst_mode": write_delay_burst_mode,
        "write_delay_manual_control": write_delay_manual_control,
        "StartRemoteEx": StartRemoteEx,
        "StopRemoteEx": StopRemoteEx,
        "StartApplication": StartApplication,
        "StartCameraOnlyApplication": StartCameraOnlyApplication,
        "_launch_application": _launch_application,
        "_start_application_background": _start_application_background,
        "_configure_vd2_startup_background": _configure_vd2_startup_background,
        "_start_live_background": _start_live_background,
        "ExecuteRaw": ExecuteRaw,
    }
