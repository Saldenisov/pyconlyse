"""Implementation for _motor_on_ps90 and related operations."""


def _bind_owis_ps90_methods_motor_on_ps90(api):
    """Bind implementation to the owning module and its runtime state."""

    def _motor_on_ps90(self, control_unit: int, axis: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_MotorOn (long Index, long AxisId)
        Description
        switch an axis on.
        With this function the axis, after the motor was switched off, is switched on again and afterwards is with a current and with active positioning regulator.

        Example:
        Switch an axis of the control unit (Index=1, Axis=1) on:
        long error = PS90_MotorOff(1,1);
        error = PS90_MotorOn(1,1);
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
        res = self.lib.PS90_MotorOn(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is on."
        )

    def _motor_off_ps90(self, control_unit: int, axis: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_MotorOff (long Index, long AxisId)
        Description
        switch an axis off.
        With this function the position regulator is deactivated and the power amplifier is switched off.

        Example:
        Switch an axis of the control unit (Index=1, Axis=1) off:
        long error = PS90_MotorOff(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_int(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_int(axis)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_MotorOff(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is off."
        )

    def _stop_axis_ps90(self, control_unit: int, axis: int) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_Stop (long Index, long AxisId)
        Description
        stop movement of an axis.
        Any active movement of an axis is terminated. The axis is stopped with the programmed brake ramp and stands still.

        Example:
        Stop movement of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_Stop(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return:  0 – function was successful -1 – function error -2 – communication error -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        res = self.lib.PS90_Stop(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Axis {axis} movement is stopped."
        )

    def _set_limit_min_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example:
        Set negative limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMinEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_double(value)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetLimitMinEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_limit_max_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example:
        Set positive limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMaxEx(1,1,50.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_double(value)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetLimitMaxEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_position_ex_ps90(
        self, control_unit: int, axis: int, pos: float
    ) -> api.Tuple[api.Union[bool, str]]:
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        pos = api.ctypes.c_double(pos)
        res = self.lib.PS90_SetPositionEx(control_unit, axis, pos)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_pos_mode_ps90(
        self, control_unit: int, axis: int, mode: int
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetPosMode (long Index, long AxisId, long Mode)
        Description
        set positioning mode of an axis
        Example
        Set positioning mode of an axis of the control unit (Index=1, Axis=1, trapezoidal profile):
        long error = PS90_SetPosMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode positioning mode Mode=0 trapezoidal profile Mode=1 S-curve profile
        :return: 0 – function was successful -1 – function error -2 – communication error -3 – syntax error
        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        mode = api.ctypes.c_long(mode)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetPosMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_pos_velocity_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetPosFEx (long Index, long AxisId, double dValue)
        Description
        set positioning velocity of an axis (values in selected unit).
        It is used for a trapezoidal and a S-curve profile.
        velocity = unit/s
        Example
        Set positioning velocity of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetPosFEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param speed: dValue positioning velocity (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_double(value)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetPosFEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_stage_attributes_ps90(
        self,
        control_unit: int,
        axis: int,
        pitch: float,
        inc_rev: int,
        gear_ratio: float,
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetStageAttributes (long Index, long AxisId, double dPitch, long IncRev, double dRatio)
        Description
        set stage attributes for an axis.
        The control unit uses for positioning of the axes internal values (increments). To allow the positioning in other units (e.g., for linear measuring stages - mm, µm, for rotary measuring stages - degrees, mrad etc.), these parameters should be defined. Then one is able to use the extended functions (...Ex) with a desired unit. The specified values are converted internally into increments. The movement of the slide per spindle revolution (pitch) is specified in a desired unit (e.g., 1 mm), as the first parameter for linear measuring stages. With rotary measuring stages a revolution of the rotary table is specified in a desired unit (e.g., 360 degrees). The number of the increments per motor revolution is defined as the second parameter. With the step motors it is the number of the full steps per revolution (e.g., 200). If a motor with the encoder is controlled, it is the number of the increments per revolution (e.g., encoder with 4-fold evaluation: encoder lines number x 4 = 500x4). The whole gear reduction ratio specified as the third parameter.

        Example:
        Define stage attributes of the control unit (Index=1, Axis=1)
        (linear measuring stage + servo motor with encoder: pitch = 1.0 mm, pulses/rev = 2000, ratio =1.0):
        long error = PS90_SetStageAttributes(1,1,1.0,2000,1.0);
        double dValue = PS90_GetPositionEx(1,1);
        Define stage attributes of the control unit (Index=1, Axis=2)
        (rotary measuring stage + step motor without encoder: revolution = 360.0 degrees, full steps/rev = 200, ratio =180.0):
        error = PS90_SetStageAttributes(1,2,360.0,200,180.0);
        dValue = PS90_GetPositionEx(1,2);
        :param control_unit:Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param pitch: dPitch pitch
        :param inc_rev: IncRev pulses/steps per motor revolution
        :param gear_ratio: dRatio gear reduction ratio
        :return: 0 – function was successful
                -1 – function error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        pitch = api.ctypes.c_double(pitch)
        inc_rev = api.ctypes.c_long(int(inc_rev))
        gear_ratio = api.ctypes.c_double(gear_ratio)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetStageAttributes(
            control_unit, axis, pitch, inc_rev, gear_ratio
        )
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_target_mode_ps90(
        self, control_unit: int, axis: int, mode: int
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetTargetMode (long Index, long AxisId, long Mode)
        Description
        set target mode of an axis
        Example
        Set target mode of the control unit (Index=1, Axis=1) for relative positioning:
        long error = PS90_SetTargetMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode target mode Mode=0 relative positioning (target value is distance) Mode=1 absolute positioning (target value is target position)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        mode = api.ctypes.c_long(mode)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetTargetMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_target_ps90(
        self, control_unit: int, axis: int, value: int
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetTarget (long Index, long AxisId, long Value)
        Description
        set target position or distance of an axis (values in increments).
        The definition depends on the target mode. The sign determines the positioning direction.

        Example:
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTarget(1,1,100);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1…9)
        :param value: Value target position or distance (values in increments)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_long(value)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetTarget(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_target_ex_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> api.Tuple[api.Union[bool, str]]:
        """Long PS90_SetTargetEx (long Index, long AxisId, double dValue)
        Description
        set target position or distance of an axis (values in selected unit).
        The definition depends on the target mode. The sign determines the positioning direction.

        Example:
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTargetEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue target position or distance (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_double(value)
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetTargetEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_drive_current_ex_ps90(self, control_unit: int, axis: int, value: float):
        """Synopsis
        long PS90_SetDriveCurrent (long Index, long AxisId, long Value)

        Description
        set drive current for an axis (values in percent).
        For step motor axes (Open Loop) it is an adjustable current. For dc servo motor axes (DC-Brush) it is an adjustable current limiting. For BLDC and step motor axes (Closed Loop) it is an adjustable current limiting. For step motor axes the maximum current will be defined with the function “PS90_SetCurrentLevel” (low – 2.4 A, high – 5.45 A). A maximum allowed current is 3.6 A. Therefore the maximum value for high current level is 66 percent.
        For dc servo motor axes the maximum current limiting is defined (12 A). The function “PS90_SetCurrentLevel” has no effect.
        For BLDC and step motor axes (Closed Loop) the maximum current limiting is defined (6 A). The function “PS90_SetCurrentLevel” has no effect.

        Parameters
        ----------
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Value drive current (values in percent)

        Returns
        -------
         0 – function was successful
        -1 – function error
        -2 – communication error
        -3 – syntax error


        Example
        Set drive current of the control unit (Index=1, Axis=1):
        long error = PS90_SetDriveCurrent(1,1,50);

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_long(int(round(value)))
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetDriveCurrent(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_hold_current_ex_ps90(self, control_unit: int, axis: int, value: float):
        """Synopsis
        long PS90_SetHoldCurrent (long Index, long AxisId, long Value)

        Description
        set hold current for an axis (values in percent).
        This setting is valid only for step motor axes (Open Loop). The maximum current will be defined with the
        function \u201cPS90_SetCurrentLevel\u201d (low \u2013 2.4 A, high \u2013 5.45 A). A maximum allowed current is 3.6 A.
        Therefore the maximum value for high current level is 66 percent.

        Parameters
        ----------
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Value hold current (values in percent)

        Returns
        -------
         0 \u2013 function was successful
        -1 \u2013 function error
        -2 \u2013 communication error
        -3 \u2013 syntax error


        Example
        Set hold current of the control unit (Index=1, Axis=1):
        long error = PS90_SetHoldCurrent(1,1,30);

        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = int(axis)
        axis = api.ctypes.c_long(axis)
        value = api.ctypes.c_long(int(round(value)))
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetHoldCurrent(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _set_current_level_ps90(self, control_unit: int, axis: int, level: int):
        """long PS90_SetCurrentLevel (long Index, long AxisId, long Value)

        Set current level for a step motor axis.
        Value 0 = low level (max 2.4 A), 1 = high level (max 5.45 A, capped at 66% = 3.6 A).
        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = api.ctypes.c_long(int(axis))
        level = api.ctypes.c_long(int(level))
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_SetCurrentLevel(control_unit, axis, level)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _get_current_level_ps90(self, control_unit: int, axis: int):
        """long PS90_GetCurrentLevel (long Index, long AxisId)

        Get current level for a step motor axis.
        Returns 0 = low level, 1 = high level.
        """
        control_unit = api.ctypes.c_long(control_unit)
        axis = api.ctypes.c_long(int(axis))
        api.sleep(api.time_ps_delay)
        res = self.lib.PS90_GetCurrentLevel(control_unit, axis)
        return res, self._error_OWIS_ps90(min(res, 0), 1)

    def _error_OWIS_ps90(self, code: int, type: int, user_def="") -> str:
        """:param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors_connections = {
            0: "no error",
            -1: "function error",
            -3: "invalid serial com_port (com_port is not found)",
            -4: "access react_denied  (com_port is busy)",
            -5: "no response from control unit",
            -7: "control unit with the specified serial number is not found",
            -8: "no connection to modbus/tcp",
            -9: "no connection to tcp/ip socket",
        }
        errors_functions = {
            0: "no error",
            -1: "function error",
            -2: "communication error",
            -3: "syntax error",
            -4: "axis is in wrong state",
            -9: "OWISid chip is not found",
            -10: "OWISid parameter is empty (not defined)",
        }
        if code > 0:
            return "Wrong code number"
        if type not in [0, 1]:
            return "Wrong type of error"
        if type == 0 and code not in errors_connections:
            return "Wrong code number"
        if type == 1 and code not in errors_functions:
            return "Wrong code number"
        if code != 0:
            return errors_connections[code] if type == 0 else errors_functions[code]
        return user_def

    return {
        "_motor_on_ps90": _motor_on_ps90,
        "_motor_off_ps90": _motor_off_ps90,
        "_stop_axis_ps90": _stop_axis_ps90,
        "_set_limit_min_ps90": _set_limit_min_ps90,
        "_set_limit_max_ps90": _set_limit_max_ps90,
        "_set_position_ex_ps90": _set_position_ex_ps90,
        "_set_pos_mode_ps90": _set_pos_mode_ps90,
        "_set_pos_velocity_ps90": _set_pos_velocity_ps90,
        "_set_stage_attributes_ps90": _set_stage_attributes_ps90,
        "_set_target_mode_ps90": _set_target_mode_ps90,
        "_set_target_ps90": _set_target_ps90,
        "_set_target_ex_ps90": _set_target_ex_ps90,
        "_set_drive_current_ex_ps90": _set_drive_current_ex_ps90,
        "_set_hold_current_ex_ps90": _set_hold_current_ex_ps90,
        "_set_current_level_ps90": _set_current_level_ps90,
        "_get_current_level_ps90": _get_current_level_ps90,
        "_error_OWIS_ps90": _error_OWIS_ps90,
    }
