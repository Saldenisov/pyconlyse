"""Implementation for read_position_axis_local and related operations."""


def _bind_owis_ps90_methods_read_position_axis_local(api):
    """Bind implementation to the owning module and its runtime state."""

    def read_position_axis_local(self, axis: int) -> api.Union[int, str]:
        res, com = self._get_pos_ex_ps90(self.control_unit_id, axis)
        if not com:
            self._delay_lines_parameters[axis]["position"] = res
            self.info(f"Reading position localy for axis {axis}: {res}", False)
            result = 0
        else:
            result = f"Device {self.device_name} reading position of axis {axis} was not successful."
            self.error(result)
        return result

    def set_param_axis_local(self, axis: int) -> api.Union[int, str]:
        param = self._delay_lines_parameters[axis]
        pitch = param["pitch"]
        revolution = param["revolution"]
        gear_ratio = param["gear_ratio"]
        speed = param["speed"]
        limit_min = param["limit_min"]
        limit_max = param["limit_max"]

        res1, com1 = self._set_stage_attributes_ps90(
            self.control_unit_id, axis, pitch, revolution, gear_ratio
        )
        res2, com2 = self._set_pos_velocity_ps90(self.control_unit_id, axis, speed)
        res_acc, com_acc = self._set_axis_acceleration_local(axis)
        res3, com3 = self._set_limit_min_ps90(self.control_unit_id, axis, limit_min)
        res4, com4 = self._set_limit_max_ps90(self.control_unit_id, axis, limit_max)
        currents_res = self._apply_axis_currents_local(axis)

        if all([res1, res2, res_acc, res3, res4]) and currents_res == 0:
            result = 0
        else:
            result = f"ERROR: {com1}:{com2}:{com_acc}:{com3}:{com4}:{currents_res}"
            self.error(result)
        return result

    def _set_axis_acceleration_local(self, axis: int) -> api.Tuple[bool, str]:
        param = self._delay_lines_parameters[axis]
        acceleration = param.get("acceleration")
        if acceleration is None:
            return True, "No acceleration override"

        controller = getattr(self.lib, "_controller", None)
        if controller is None:
            # DLL backend path currently has no dedicated acceleration hook here.
            return True, "Acceleration override skipped for DLL backend"

        try:
            acc_value = max(1, int(round(float(acceleration))))
            controller.set_acceleration(axis, acc_value)
            return True, f"Axis {axis} acceleration set to {acc_value}"
        except Exception as e:
            return False, f"Axis {axis} acceleration set failed: {e}"

    def _amps_to_percent(self, axis: int, amps: float) -> int:
        """Convert current in Amps to DLL percent value.

        Values > 10 are assumed to already be percent (legacy format).
        Low current level (0): max 2.4 A = 100%.
        High current level (1): max 5.45 A, capped at 66% = 3.6 A.

        If the requested current exceeds the low-level range and
        *allow_high_current_level* is set, the level is switched to high
        automatically (matching the TCP adapter behaviour).
        """
        v = abs(float(amps))
        if v > 10.0:
            # Legacy / already-percent value
            return max(0, min(100, int(round(v))))

        # Determine current level from controller
        level_res, _ = self._get_current_level_ps90(self.control_unit_id, axis)
        level = level_res if level_res in (0, 1) else 0

        allow_high = bool(getattr(self, "allow_high_current_level", False))
        if allow_high and v > 2.4 and level == 0:
            res_set, _ = self._set_current_level_ps90(
                self.control_unit_id, axis, 1
            )
            if res_set:
                level = 1
                self.info(
                    f"Axis {axis}: switched to high current level for {v:.2f} A",
                    True,
                )

        if level == 0:
            pct = int(round((v / 2.4) * 100.0))
            return max(0, min(100, pct))

        pct = int(round((v / 5.45) * 100.0))
        return max(0, min(66, pct))

    def _apply_axis_currents_local(self, axis: int) -> api.Union[int, str]:
        if (
            self._is_tcp_backend_active()
            and bool(getattr(self, "ovis_tcp_strict_init_profile", True))
            and hasattr(self.lib, "apply_ovis_current_profile")
        ):
            ok, comment = self.lib.apply_ovis_current_profile(axis)
            if ok:
                return 0
            return (
                f"ERROR: Device {self.device_name} could not apply OVIS TCP current "
                f"profile for axis {axis}: {comment}"
            )

        param = self._delay_lines_parameters[axis]
        drive_current = float(param["drive_current"])
        hold_current = float(param["hold_current"])

        drive_pct = self._amps_to_percent(axis, drive_current)
        hold_pct = self._amps_to_percent(axis, hold_current)
        self.info(
            f"Axis {axis} currents: drive={drive_current}A -> {drive_pct}%, "
            f"hold={hold_current}A -> {hold_pct}%",
            True,
        )

        res_drive, com_drive = self._set_drive_current_ex_ps90(
            self.control_unit_id, axis, drive_pct
        )
        res_hold, com_hold = self._set_hold_current_ex_ps90(
            self.control_unit_id, axis, hold_pct
        )
        if res_drive and res_hold:
            return 0

        return (
            f"ERROR: Device {self.device_name} could not apply currents for axis {axis}: "
            f"drive={drive_current}A={drive_pct}% ({com_drive}), "
            f"hold={hold_current}A={hold_pct}% ({com_hold})"
        )

    def _axis_state_name(self, state) -> str:
        names = {
            api.DevState.ON: "ON",
            api.DevState.OFF: "OFF",
            api.DevState.INIT: "INIT",
            api.DevState.STANDBY: "STANDBY",
            api.DevState.FAULT: "FAULT",
            api.DevState.MOVING: "MOVING",
            api.DevState.RUNNING: "RUNNING",
        }
        return names.get(state, str(state))

    def _refresh_axis_state(self, axis: int):
        res = self.get_status_axis_local(axis)
        if res != 0:
            return None
        return self._delay_lines_parameters[axis]["state"]

    def _ensure_axis_ready_for_motion(self, axis: int, force_reinit: bool = False) -> api.Union[int, str]:
        state = self._refresh_axis_state(axis)
        if state is None:
            return f"ERROR: Device {self.device_name} could not read state for axis {axis}."

        if state == api.DevState.ON and not force_reinit:
            return 0

        if not force_reinit:
            turn_on_res = self.turn_on_axis_local(axis)
            if turn_on_res == 0:
                api.sleep(0.05)
                state = self._refresh_axis_state(axis)
                if state == api.DevState.ON:
                    return 0

        self.info(
            f"{self.device_name} axis {axis} is not ready for motion "
            f"(state={self._axis_state_name(state)}), reinitializing axis.",
            True,
        )
        init_res = self.init_axis_local(axis)
        if init_res != 0:
            return (
                f"ERROR: Device {self.device_name} axis {axis} reinit failed: "
                f"{init_res}"
            )

        turn_on_res = self.turn_on_axis_local(axis)
        if turn_on_res != 0:
            return (
                f"ERROR: Device {self.device_name} axis {axis} could not be turned on "
                f"after reinit: {turn_on_res}"
            )

        api.sleep(0.05)
        state = self._refresh_axis_state(axis)
        if state != api.DevState.ON:
            return (
                f"ERROR: Device {self.device_name} axis {axis} is still "
                f"{self._axis_state_name(state)} after reinit."
            )
        return 0

    def turn_on_axis_local(self, axis: int) -> api.Union[int, str]:
        res, comments = self._motor_on_ps90(self.control_unit_id, axis)
        if not res:
            result = f"ERROR: Device {self.device_name} turn_on_axis for axis {axis} func did NOT work {comments}."
            self.error(result)
        else:
            api.sleep(0.05)
            axis_state = self._refresh_axis_state(axis)
            if axis_state == api.DevState.ON:
                result = 0
            else:
                result = (
                    f"ERROR: Device {self.device_name} axis {axis} turn_on did not "
                    f"reach ON state (state={self._axis_state_name(axis_state)})."
                )
                self.error(result)
        return result

    def turn_off_axis_local(self, axis: int) -> api.Union[int, str]:
        res, comments = self._motor_off_ps90(self.control_unit_id, axis)
        if not res:
            # OWIS may report "axis is in wrong state" when it's already effectively off.
            if isinstance(comments, str) and "wrong state" in comments.lower():
                self._delay_lines_parameters[axis]["state"] = api.DevState.OFF
                result = 0
            else:
                result = f"ERROR: Device {self.device_name} turn_off_axis for axis {axis} func did NOT work {comments}."
                self.error(result)
        else:
            self._delay_lines_parameters[axis]["state"] = api.DevState.OFF
            result = 0
        return result

    def move_axis_local(self, args) -> api.Union[int, str]:
        axis = int(args[0])
        pos: float = args[1]

        ready_res = self._ensure_axis_ready_for_motion(axis)
        if ready_res != 0:
            return ready_res

        set_res, set_comments = self._set_target_ex_ps90(self.control_unit_id, axis, pos)
        if not set_res:
            result = (
                f"ERROR: Device {self.device_name} set_target_ex to {pos} for axis {axis} "
                f"did NOT work {set_comments}."
            )
            self.error(result)
            return result

        res, comments = self._go_target_ps90(self.control_unit_id, axis)
        if (not res) and isinstance(comments, str) and ("wrong state" in comments.lower()):
            self.info(
                f"{self.device_name} axis {axis} reported wrong state on go_target; "
                "retrying once after reinit.",
                True,
            )
            ready_res = self._ensure_axis_ready_for_motion(axis, force_reinit=True)
            if ready_res == 0:
                set_res, set_comments = self._set_target_ex_ps90(self.control_unit_id, axis, pos)
                if not set_res:
                    result = (
                        f"ERROR: Device {self.device_name} set_target_ex retry to {pos} "
                        f"for axis {axis} did NOT work {set_comments}."
                    )
                    self.error(result)
                    return result
                res, comments = self._go_target_ps90(self.control_unit_id, axis)
            else:
                return ready_res

        if res:
            self.info(
                f"Device {self.device_name} axis {axis} started moving to {pos}.",
                True,
            )
            if axis not in self.follow:
                self.follow[axis] = api.Thread(
                    target=self.follow_after_moving, args=(axis,), daemon=True
                )
                self.follow[axis].start()
            result = 0
        else:
            if not self._keep_motor_powered(axis):
                self.turn_off_axis(axis)
            result = f"ERROR: Device {self.device_name} axis {axis} did NOT start moving: {comments}."
            self.error(result)
        return result

    def follow_after_moving(self, axis, wait=1.0, stable_needed=5, eps=1e-4, max_wait_s=180.0):
        stable = 0
        checks = 0
        max_checks = max(1, int(max_wait_s / wait))
        try:
            while checks < max_checks:
                if axis not in self._delay_lines_parameters:
                    break
                pos_prev = float(self._delay_lines_parameters[axis]["position"])
                api.sleep(wait)
                pos_now = float(self._delay_lines_parameters[axis]["position"])
                if abs(pos_now - pos_prev) <= eps:
                    stable += 1
                    if stable >= stable_needed:
                        if not self._keep_motor_powered(axis):
                            self.turn_off_axis(axis)
                        break
                else:
                    stable = 0
                checks += 1
            if checks >= max_checks:
                self.info(
                    f"follow_after_moving timeout for axis {axis}, leaving motor state unchanged.",
                    True,
                )
        finally:
            self.follow.pop(axis, None)

    def stop_axis_local(self, axis: int) -> api.Union[int, str]:
        res, comments = self._stop_axis_ps90(self.control_unit_id, axis)
        if not res:
            result = (
                f"ERROR: Device {self.device_name} stop_axis axis {axis} "
                f"did NOT work {comments}."
            )
            self.error(result)
        else:
            result = 0
        return result

    def define_position_axis_local(self, args) -> api.Union[int, str]:
        axis = int(args[0])
        pos = float(args[1])
        res, comments = self._set_position_ex_ps90(self.control_unit_id, axis, pos)
        if not res:
            result = (
                f"ERROR: Device {self.device_name} define_pos axis {axis} "
                f"did NOT work {comments}."
            )
            self.error(result)
        else:
            result = 0
        return result

    def _connect_ps90(
        self,
        control_unit: int,
        interface: int,
        port: int,
        baudrate: int,
        par3=0,
        par4=0,
        par5=0,
        par6=0,
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_Connect (long Index, long Interface, long p1, long p2, long p3, long p4, long p5, long p6)
        Description
        open interface and connect to PS 90. Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).

        Example:
        Open COM3 and connect to PS 90 (Index=1):
        long error = PS90_Connect(1, 0, 3, 9600, 0, 0, 0, 0);
        :param control_unit: Index control unit index 1–10 (default=1, range=1...20)  11...20 – debug mode 1...10 – standard mode
        :param interface: Interface define interface (default=0) USB or serial com_port (=0)
        :param com_port or p1: p1 define COM com_port (default=1 – COM1, range=0...255)
        :param baudrate or p2: p2 define request mode for communication (default=9600) 115200 – fast read (all bytes, fast check) 19200 – fast read (all bytes, slow check)  9600* – standard read (byte-by-byte)
        :param par3: p3 define delay value (=20+x) for serial communication (default=20 ms)
        :param par4: p4 system value (default=0) 10 – without check 0* – with check (firmware, terminal mode, clear error)
        :param par5: p5 system value (default=0) 10 – with com_port flush  0* – without com_port flush
        :param par6: p6 system value (default=0) 5 – reconnect for every message  0* – without reconnect

        :return: 0 – function was successful 1...9 – error
        1 function error (invalid parameters)
        3 invalid serial com_port (com_port is not found)
        4 access react_denied (com_port is busy)
        5 no response from control unit (check cable, connection or reset control unit)
        8 no connection to modbus/tcp
        9 no connection to tcp/ip socket

        """
        control_unit = api.ctypes.c_long(control_unit)
        interface = api.ctypes.c_long(int(interface))
        port = api.ctypes.c_long(int(port))
        baudrate = api.ctypes.c_long(int(baudrate))
        par3 = api.ctypes.c_long(par3)
        par4 = api.ctypes.c_long(par4)
        par5 = api.ctypes.c_long(par5)
        par6 = api.ctypes.c_long(par6)
        # res x -1 is according official documentation
        api.sleep(api.time_ps_delay)
        res = (
            self.lib.PS90_Connect(
                control_unit, interface, port, baudrate, par3, par4, par5, par6
            )
            * -1
        )
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    def _connect_simple_ps90(
        self, control_unit=1, ser_num=""
    ) -> api.Tuple[api.Union[bool, str]]:
        r"""Long PS90_SimpleConnect (long Index, const char* pszSerNum)
        Description
        find control unit with the specified serial number and connect to it.
        Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).
        The software handshake character is CR.
        Ethernet interface (communication via Com-Server)
        As Com-Server the OWIS software tool “OWISerialServer.exe” may be used (..\OWISoft\Application\system). Alternatively, you can use other commercial products (hardware/software). The application software can access this interface via Windows TCP socket: special communication for OWIS software (command + delay). The software handshake character is CR.

        Example:
        Find control unit and connect to it (empty string, COMx):
        long error = PS90_SimpleConnect(1, “”);
        :param control_unit: Index control unit index 1-10 (default=1, range=1...20)
                             11...20 – debug mode
                             1...10 – standard mode
        :param ser_num: pszSerNum control unit serial number (default=empty string)
                       USB or serial com_port
                       empty string – the first found control unit is connected;
                       “12345678” – control unit with the specified serial number is connected;
                       Ethernet interface
                       “net” – control unit is connected to the Com-Server (local application) by the first found local IP address and com_port number 1200.
        :return: 0 – function was successful
                 1...9 – error
                 1 function error (invalid parameters)
                 5 no response from control unit (check cable, connection or reset control unit)
                 7 control unit with the specified serial number is not found
                 9 no connection to tcp/ip socket

        """
        control_unit = api.ctypes.c_long(control_unit)
        ser_num = api.ctypes.c_char_p(ser_num)
        api.sleep(api.time_ps_delay)
        res = (
            self.lib.PS90_SimpleConnect(control_unit, ser_num) * -1
        )  # *-1 is according official documentation
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    def _convert_axis_state_format_ps90(self, axis_state_OWIS: int) -> int:
        """Converts OWIS controller axis state to the used for stpmtr_controller
        :param axis_state_OWIS: 0     axis is not active
                                1     axis is not initialized
                                2     axis is switched off
                                3     axis is active and initialized and switched on
        :return: 0 - axis is not initialized, 1 - is active
        """
        if axis_state_OWIS in [0, 1, 2]:
            return 0
        if axis_state_OWIS == 3:
            return 1
        return 0

    def _disconnect_ps90(self, control_unit: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_Disconnect (long Index)
        Description
        disconnect PS 90
        Example
        Disconnect a control unit (Index=1):
        long error = PS90_Disconnect(1);
        :param control_unit: Index control unit index (1-10)
        :return:  0 – function was successful -1 – function error

        """
        control_unit = api.ctypes.c_long(control_unit)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_Disconnect(control_unit)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _free_switch_ps90(
        self, control_unit: int, axis: int
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_FreeSwitch (long Index, long AxisId)
        Description
        release active limit switches of an axis.
        After an axis has driven into a limit switch, it can release a limit switch with this function. This is valid only for released axes. Besides, the direction of the movement is selected automatically, depending on whether a positive or negative limit switch is activated.

        Example:
        Release active limit switches of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetLimitSwitch(1,1,15);
        error = PS90_SetLimitSwitchMode(1,1,15);
        long state = PS90_GetSwitchState(1,1);
        if( state & 15 ) error = PS90_FreeSwitch(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_FreeSwitch(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _get_connection_info(self, control_unit: int) -> api.Tuple[api.Union[bool, str]]:
        """Synopsis
        long PS90_GetConnectInfo (long Index, char* pszBuffer, long Length, long Mode)
        Description
        read connecting configuration
        Parameters
        Index control unit index (1-10)
        pszBuffer address of buffer for reading
        Length length of the buffer
        Mode mode (default=0, range=0...3)
        0 – connecting configuration
        1 – connecting configuration (short format)
        2 – last transferred data
        3 – connecting state (online or offline)

        Returns
        -------
        length of the string
        Example
        Read a connecting configuration for the control unit (Index=1):
        char szString[50];
        long len = PS90_GetConnectInfo(1, szString, 50, 0);
        long error = PS90_GetReadError(1);

        """

    def _go_target_ps90(self, control_unit: int, axis: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_GoTarget (long Index, long AxisId)
        Description
        start positioning of an axis.
        The axis goes to a new target position or a distance either in the trapezoidal or S-curve profile. This is valid only for released axes.

        Example:
        Drive an axis of the control unit (Index=1, Axis=1) to a target in trapezoidal profile:
        long error = PS90_SetPosMode(1,1,0);
        error = PS90_SetTargetMode(1,1,1);
        error = PS90_SetTarget(1,1,0);
        error = PS90_GoTarget(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_GoTarget(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _motor_init_ps90(self, control_unit: int, axis: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_MotorInit (long Index, long AxisId)
        Description
        initialize an axis and switch on.
        With this function the axis is completely initialized and afterwards is with a current and with active positioning regulator.
        It must be executed after the turning on of the control unit, so that the axis can be moved afterwards with the commands REF, PGO, VGO etc.
        Before the following parameters must have been set: limit switch mask and polarity, start regulator parameters.

        Example:
        Initialize an axis of the control unit (Index=1, Axis=1) and switch on:
        long error = PS90_MotorInit(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_MotorInit(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is initialized"
        )

    return {
        "read_position_axis_local": read_position_axis_local,
        "set_param_axis_local": set_param_axis_local,
        "_set_axis_acceleration_local": _set_axis_acceleration_local,
        "_amps_to_percent": _amps_to_percent,
        "_apply_axis_currents_local": _apply_axis_currents_local,
        "_axis_state_name": _axis_state_name,
        "_refresh_axis_state": _refresh_axis_state,
        "_ensure_axis_ready_for_motion": _ensure_axis_ready_for_motion,
        "turn_on_axis_local": turn_on_axis_local,
        "turn_off_axis_local": turn_off_axis_local,
        "move_axis_local": move_axis_local,
        "follow_after_moving": follow_after_moving,
        "stop_axis_local": stop_axis_local,
        "define_position_axis_local": define_position_axis_local,
        "_connect_ps90": _connect_ps90,
        "_connect_simple_ps90": _connect_simple_ps90,
        "_convert_axis_state_format_ps90": _convert_axis_state_format_ps90,
        "_disconnect_ps90": _disconnect_ps90,
        "_free_switch_ps90": _free_switch_ps90,
        "_get_connection_info": _get_connection_info,
        "_go_target_ps90": _go_target_ps90,
        "_motor_init_ps90": _motor_init_ps90,
    }
