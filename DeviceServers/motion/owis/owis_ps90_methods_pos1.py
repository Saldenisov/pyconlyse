"""Implementation for pos1 and related operations."""


def _bind_owis_ps90_methods_pos1(api):
    """Bind implementation to the owning module and its runtime state."""

    def pos1(self):
        if 1 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[1]["position"]

    def write_pos1(self, pos):
        if 1 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 1 configured.")
            return
        self.move_axis([1, pos])

    def pos2(self):
        if 2 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[2]["position"]

    def write_pos2(self, pos):
        if 2 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 2 configured.")
            return
        self.move_axis([2, pos])

    def pos3(self):
        if 3 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[3]["position"]

    def write_pos3(self, pos):
        if 3 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 3 configured.")
            return
        self.move_axis([3, pos])

    def pos4(self):
        # Some installations use only 3 axes for this device instance.
        if 4 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[4]["position"]

    def write_pos4(self, pos):
        if 4 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 4 configured.")
            return
        self.move_axis([4, pos])

    def get_pos(self, axis):
        return self._delay_lines_parameters[axis]["position"]

    def _power_dependency_proxy(device_name: str):
        return api.DeviceProxy(device_name)

    def _handle_power_dependency_off(self, detail: str) -> None:
        self._set_off_for_unpowered_controller(detail)

    def probe_powered_hardware(self) -> api.Union[int, str]:
        """Restore PS90 transport only; never initialise axes from a PDU event."""
        self.find_device()
        if self._device_id_internal == -1:
            return "OWIS controller did not respond after power was restored"
        return 0

    def _set_off_for_unpowered_controller(self, detail: str) -> str:
        message = f"OWIS controller power is OFF ({detail}); connection is intentionally skipped."
        self._controller_connection_status = message
        return self._mark_hardware_power_off(message)

    def controller_connection_status(self):
        return getattr(self, "_controller_connection_status", "initialising")

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b""
        if state_ok:
            power_is_on, power_detail = self._read_power_dependency_state()
            if power_is_on is False:
                self._set_off_for_unpowered_controller(power_detail)
                return
            transport = str(getattr(self, "transport", "tcp")).strip().lower()
            ip = str(getattr(self, "controller_ip", "")).strip()
            port = int(getattr(self, "controller_port", 8777))
            tcp_aliases = {"tcp", "ip", "ethernet", "socket"}
            dll_aliases = {"dll", "windll"}

            if transport in tcp_aliases:
                use_tcp_backend = True
            elif transport in dll_aliases:
                use_tcp_backend = False
            else:
                use_tcp_backend = bool(ip)
                fallback = "TCP" if use_tcp_backend else "DLL"
                self.info(
                    f"Unknown transport '{transport}', fallback to {fallback}.", True
                )

            if not hasattr(api.ctypes, "WinDLL") and not use_tcp_backend:
                if ip:
                    self.info(
                        "ctypes.WinDLL is unavailable on this platform; forcing TCP backend.",
                        True,
                    )
                    use_tcp_backend = True
                else:
                    self.error(
                        "DLL transport requested on non-Windows platform without controller_ip."
                    )
                    self.set_state(api.DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return

            if use_tcp_backend:
                if not ip:
                    self.error(
                        "OWIS TCP backend requires 'controller_ip' device property."
                    )
                    self.set_state(api.DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return
                timeout = float(getattr(self, "tcp_timeout", 5.0))
                command_delay = float(getattr(self, "tcp_command_delay", 0.005))
                velocity_scale = float(getattr(self, "tcp_velocity_scale", 16.0))
                velocity_scale_map_raw = str(
                    getattr(self, "tcp_velocity_scale_map", "")
                ).strip()
                velocity_scale_map = {}
                if velocity_scale_map_raw:
                    try:
                        parsed = api.ast.literal_eval(velocity_scale_map_raw)
                        if isinstance(parsed, dict):
                            for axis, scale in parsed.items():
                                axis_i = int(axis)
                                scale_f = float(scale)
                                if axis_i > 0 and scale_f > 0:
                                    velocity_scale_map[axis_i] = scale_f
                        else:
                            self.error(
                                "tcp_velocity_scale_map must be a dict, "
                                f"got {type(parsed).__name__}"
                            )
                    except Exception as e:
                        self.error(
                            f"Invalid tcp_velocity_scale_map '{velocity_scale_map_raw}': {e}"
                        )
                self.info(
                    f"Using OWIS TCP backend: {ip}:{port} "
                    f"(timeout={timeout}s, command_delay={command_delay}s, "
                    f"velocity_scale={velocity_scale}, "
                    f"strict_ovis_init={bool(getattr(self, 'ovis_tcp_strict_init_profile', True))})",
                    True,
                )
                if velocity_scale_map:
                    self.info(
                        f"TCP velocity scale overrides by axis: {velocity_scale_map}",
                        True,
                    )
                self.lib = api._PS90TcpAdapter(
                    ip,
                    port=port,
                    timeout=timeout,
                    command_delay=command_delay,
                    velocity_scale=velocity_scale,
                    velocity_scale_map=velocity_scale_map,
                    allow_high_current_level=bool(
                        getattr(self, "allow_high_current_level", False)
                    ),
                    strict_ovis_init_profile=bool(
                        getattr(self, "ovis_tcp_strict_init_profile", True)
                    ),
                    ovis_init_current_level=int(
                        getattr(self, "ovis_tcp_current_level", 0)
                    ),
                    ovis_init_hold_current_percent=int(
                        getattr(self, "ovis_tcp_hold_current_percent", 38)
                    ),
                    ovis_init_drive_current_percent=int(
                        getattr(self, "ovis_tcp_drive_current_percent", 50)
                    ),
                    ovis_init_ready_timeout=float(
                        getattr(self, "ovis_tcp_init_ready_timeout", 6.0)
                    ),
                    ovis_init_poll_interval=float(
                        getattr(self, "ovis_tcp_init_poll_interval", 0.05)
                    ),
                )
                # TCP adapter: connect via PS90_Connect (supported by _PS90TcpAdapter)
                res, comments = self._connect_ps90(
                    self.control_unit_id,
                    interface=self.interface,
                    port=self.com_port,
                    baudrate=self.baudrate,
                )
            else:
                # Resolve DLL path robustly: prefer valid device property, else fall back to local drivers dir
                dll_candidate = None
                try:
                    cfg_path = str(self.dll_path).strip()
                except Exception:
                    cfg_path = ""
                if cfg_path:
                    p = api.Path(cfg_path)
                    if p.exists():
                        dll_candidate = p

                if dll_candidate is None:
                    drivers_dir = api.Path(api.__file__).resolve().parent / "drivers"
                    # Prefer arch-specific DLL name; fall back to generic
                    arch_name = "ps90_64.dll" if api.sys.maxsize > 2**32 else "ps90_32.dll"
                    for name in (arch_name, "ps90.dll"):
                        cand = drivers_dir / name
                        if cand.exists():
                            dll_candidate = cand
                            break

                if dll_candidate is None:
                    self.error(
                        f"OWIS DLL not found. Checked property path '{cfg_path}' and drivers dir '{drivers_dir}'."
                    )
                    self.set_state(api.DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return

                # Ensure Windows can locate any adjacent DLL dependencies (Python 3.8+)
                try:
                    if hasattr(api.os, "add_dll_directory"):
                        api.os.add_dll_directory(str(dll_candidate.parent))
                except Exception as e:
                    self.info(f"add_dll_directory failed: {e}", True)

                self.dll_path = dll_candidate
                self.info(f"Using OWIS DLL: {self.dll_path}", True)
                self.lib = api.ctypes.WinDLL(str(self.dll_path))

                # DLL: use Ethernet (PS90_SimpleConnect) if controller_ip is set, else COM/USB
                _eth_ip = str(getattr(self, "controller_ip", "")).strip()
                if _eth_ip:
                    _eth_port = int(getattr(self, "controller_port", 8777))
                    self.info(
                        f"Using OWIS DLL over Ethernet: {_eth_ip}:{_eth_port}", True
                    )
                    res, comments = self._connect_simple_ps90(
                        self.control_unit_id,
                        ser_num=f"net:{_eth_ip}:{_eth_port}".encode("ascii"),
                    )
                else:
                    res, comments = self._connect_ps90(
                        self.control_unit_id,
                        interface=self.interface,
                        port=self.com_port,
                        baudrate=self.baudrate,
                    )
            if res:
                self.set_state(api.DevState.STANDBY)
                argreturn = self.control_unit_id, f"{self.serial_number}".encode()
                self._controller_connection_status = "OWIS controller transport connected"
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.CONNECTED,
                    api.InitializationState.NOT_REQUESTED,
                    "OWIS controller transport connected; axis initialisation has not been requested",
                )
            else:
                self.set_state(api.DevState.FAULT)
                self._controller_connection_status = (
                    f"OWIS controller connection failed ({comments}); {power_detail}"
                )
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.DISCONNECTED,
                    api.InitializationState.NOT_REQUESTED,
                    self._controller_connection_status,
                )
                self.comment = self._controller_connection_status
        self._device_id_internal, self._uri = argreturn

    def turn_on_local(self) -> api.Union[int, str]:
        power_is_on, power_detail = self._read_power_dependency_state()
        if power_is_on is False:
            return self._set_off_for_unpowered_controller(power_detail)
        if self._device_id_internal == -1:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()

        if self._device_id_internal == -1:
            self.set_state(api.DevState.FAULT)
            return f"Could NOT turn on {self.device_name}: Device could not be found."

        self.set_state(api.DevState.ON)
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.CONNECTED,
            api.InitializationState.IN_PROGRESS,
            "OWIS transport connected; axis initialisation is in progress",
        )
        init_errors = []
        for axis in sorted(self._delay_lines_parameters.keys()):
            try:
                res = self.init_axis_local(int(axis))
            except Exception as e:
                res = f"exception during init: {e}"
            if res != 0:
                err = f"axis {axis} init failed: {res}"
                init_errors.append(err)
                self.error(f"{self.device_name} {err}")
        if init_errors:
            self.set_state(api.DevState.FAULT)
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.CONNECTED,
                api.InitializationState.FAILED,
                "; ".join(init_errors),
            )
            return (
                f"Could NOT turn on {self.device_name}: "
                + "; ".join(init_errors)
            )
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.READY,
            api.InitializationState.SUCCEEDED,
            "OWIS controller connected and configured axes are initialised",
        )
        return 0

    def turn_off_local(self) -> api.Union[int, str]:
        self._device_id_internal = -1
        res, comments = self._disconnect_ps90(self.control_unit_id)
        if res:
            self.set_state(api.DevState.OFF)
            return 0
        self.set_state(api.DevState.FAULT)
        return comments

    def _attempt_recover_connection(self) -> bool:
        power_is_on, power_detail = self._read_power_dependency_state()
        if power_is_on is False:
            self._set_off_for_unpowered_controller(power_detail)
            return False
        attempts = max(1, int(getattr(self, "recovery_connect_attempts", 3)))
        retry_delay = max(
            0.1, float(getattr(self, "recovery_attempt_delay_seconds", 1.0))
        )
        self.info(
            f"Attempting OWIS transport recovery for {self.device_name} "
            f"(attempts={attempts}, delay={retry_delay}s; no axis initialisation).",
            True,
        )
        self.set_state(api.DevState.FAULT)
        self._device_id_internal = -1
        self._uri = b""

        for attempt in range(1, attempts + 1):
            try:
                # Best effort cleanup of stale session before reconnecting.
                self._disconnect_ps90(self.control_unit_id)
            except Exception:
                pass

            try:
                # find_device performs only the controller connection probe.
                # Calling turn_on_local here would initialise axes and can
                # alter motor state merely because a status poll failed.
                self.find_device()
                res = 0 if self._device_id_internal != -1 else "controller unavailable"
            except Exception as e:
                self.error(
                    f"Recovery attempt {attempt}/{attempts} failed for "
                    f"{self.device_name}: {e}"
                )
                res = None

            if res == 0:
                self._status_check_fault = 0
                self._next_recovery_attempt_ts = 0.0
                self._last_recovery_wait_log_ts = 0.0
                self.set_state(api.DevState.STANDBY)
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.CONNECTED,
                    api.InitializationState.NOT_REQUESTED,
                    "OWIS transport recovery succeeded; axis initialisation has not been requested",
                )
                self.info(
                    f"OWIS transport recovery succeeded for {self.device_name}; "
                    "awaiting explicit turn_on for axis initialisation.",
                    True,
                )
                return True

            self.error(
                f"Recovery attempt {attempt}/{attempts} did not recover "
                f"{self.device_name}: {res}"
            )
            if attempt < attempts:
                api.sleep(retry_delay)

        return False

    def is_ensure_on_allowed(self):
        return self.get_state() in self.RULES.get("ensure_on", [])

    def ensure_on(self):
        """Ensure the controller is ON (idempotent).

        If already ON, this is a no-op. Otherwise, delegates to turn_on().
        """
        state_ok = self.check_func_allowance(self.ensure_on)
        if state_ok == 1:
            if self.get_state() != api.DevState.ON:
                self.turn_on()
            else:
                self.info(f"{self.device_name} already ON; ensure_on is a no-op.", True)

    def get_controller_status_local(self) -> api.Union[int, str]:
        power_is_on, power_detail = self._read_power_dependency_state()
        if power_is_on is False:
            return self._set_off_for_unpowered_controller(power_detail)

        now = api.time.monotonic()
        next_recovery_attempt_ts = float(
            getattr(self, "_next_recovery_attempt_ts", 0.0)
        )
        last_recovery_wait_log_ts = float(
            getattr(self, "_last_recovery_wait_log_ts", 0.0)
        )
        ser_num = self._get_serial_number_ps90(self.control_unit_id)
        if ser_num < 0:
            self._status_check_fault += 1
            self.set_state(api.DevState.FAULT)
            if self._status_check_fault <= self.recovery_fault_threshold:
                return "Connection with PS90 is lost"

            if now < next_recovery_attempt_ts:
                remaining = max(0.0, next_recovery_attempt_ts - now)
                # Throttle repetitive logs while status is polled frequently.
                if now - last_recovery_wait_log_ts >= 1.0:
                    self.info(
                        f"Recovery cooldown for {self.device_name}: "
                        f"next attempt in {remaining:.1f}s.",
                        True,
                    )
                    self._last_recovery_wait_log_ts = now
                return (
                    "Connection with PS90 is lost; "
                    f"waiting {remaining:.1f}s before next reconnect attempt"
                )

            if self._attempt_recover_connection():
                # Keep the status command correct even when a backend supplies
                # a lightweight recovery implementation without resetting its
                # own counters.
                self._status_check_fault = 0
                self._next_recovery_attempt_ts = 0.0
                self._last_recovery_wait_log_ts = 0.0
                return 0

            pause = max(1.0, float(getattr(self, "recovery_pause_seconds", 8.0)))
            self._next_recovery_attempt_ts = api.time.monotonic() + pause
            self.info(
                f"Recovery paused for {pause:.1f}s for {self.device_name}. "
                "Will retry automatically.",
                True,
            )
            return (
                "Connection with PS90 is lost; "
                f"recovery will retry in {pause:.1f}s"
            )

        self._status_check_fault = 0
        self._next_recovery_attempt_ts = 0.0
        self._last_recovery_wait_log_ts = 0.0
        for axis in self._delay_lines_parameters.keys():
            self.get_status_axis_local(axis)
            self.read_position_axis_local(axis)
        return 0

    def _is_tcp_backend_active(self) -> bool:
        return isinstance(getattr(self, "lib", None), api._PS90TcpAdapter)

    def _keep_motor_powered(self, axis: int) -> bool:
        if self._is_tcp_backend_active() and bool(
            getattr(self, "ovis_tcp_keep_motor_on", True)
        ):
            return True
        param = self._delay_lines_parameters.get(axis, {})
        return bool(param.get("keep_on", False))

    def init_axis_local(self, axis: int) -> api.Union[int, str]:
        res, comments = self._motor_init_ps90(self.control_unit_id, axis)
        if not res:
            result = f"ERROR: Device {self.device_name} motor_init for axis {axis} func did NOT work: {comments}."
            self.error(result)
            self._delay_lines_parameters[axis]["state"] = api.DevState.FAULT
        else:
            res, comments = self._set_target_mode_ps90(self.control_unit_id, axis, 1)
            if not res:
                result = (
                    f"ERROR: Device {self.device_name} set_target_mode to ABS for axis {axis} "
                    f"did NOT work {comments}."
                )
                self.error(result)
            else:
                self._delay_lines_parameters[axis]["state"] = api.DevState.INIT
                res = self.set_param_axis(axis)
                if res == "0":
                    result = 0
                else:
                    result = res
            if not self._keep_motor_powered(axis):
                self._motor_off_ps90(self.control_unit_id, axis)
        return result

    def get_status_axis_local(self, axis: int) -> api.Union[int, str]:
        res, comments = self._get_axis_state_ps90(self.control_unit_id, axis)
        if res == 0:
            result = api.DevState.OFF
        elif res == 1:
            result = api.DevState.STANDBY
        elif res == 2:
            result = api.DevState.INIT
        elif res == 3:
            result = api.DevState.ON
        else:
            error = f"ERROR: {comments}"
            self.error(error)
            result = api.DevState.FAULT
        self._delay_lines_parameters[axis]["state"] = result
        return 0

    return {
        "pos1": pos1,
        "write_pos1": write_pos1,
        "pos2": pos2,
        "write_pos2": write_pos2,
        "pos3": pos3,
        "write_pos3": write_pos3,
        "pos4": pos4,
        "write_pos4": write_pos4,
        "get_pos": get_pos,
        "_power_dependency_proxy": _power_dependency_proxy,
        "_handle_power_dependency_off": _handle_power_dependency_off,
        "probe_powered_hardware": probe_powered_hardware,
        "_set_off_for_unpowered_controller": _set_off_for_unpowered_controller,
        "controller_connection_status": controller_connection_status,
        "find_device": find_device,
        "turn_on_local": turn_on_local,
        "turn_off_local": turn_off_local,
        "_attempt_recover_connection": _attempt_recover_connection,
        "is_ensure_on_allowed": is_ensure_on_allowed,
        "ensure_on": ensure_on,
        "get_controller_status_local": get_controller_status_local,
        "_is_tcp_backend_active": _is_tcp_backend_active,
        "_keep_motor_powered": _keep_motor_powered,
        "init_axis_local": init_axis_local,
        "get_status_axis_local": get_status_axis_local,
    }
