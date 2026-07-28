from abc import abstractmethod
from threading import Event
from typing import Any, Dict, Union

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, command, device_property

from DeviceServers.base.general import (
    ConfigurationError,
    DS_General,
    operation_succeeded,
    parse_structured_config,
    standard_str_output,
)


class DS_MOTORIZED_MONO_AXIS(DS_General):
    RULES = {
        "read_position": [DevState.ON, DevState.MOVING],
        "write_position": [DevState.ON],
        "define_position": [DevState.ON],
        "move_axis": [DevState.ON, DevState.STANDBY],
        "stop_movement": [DevState.MOVING, DevState.ON, DevState.STANDBY],
        **DS_General.RULES,
    }

    POWER_STATES = {
        0: "PWR_UNKNOWN",
        1: "PWR_OFF",
        3: "PWR_NORM",
        4: "PWR_REDUCED",
        5: "PWR_MAX",
    }

    wait_time = device_property(dtype=int, default_value=5000)
    limit_min = device_property(dtype=float)
    limit_max = device_property(dtype=float)
    real_pos = device_property(dtype=float)
    preset_positions = device_property(dtype="DevVarFloatArray")

    @attribute(
        label="Important parameters of motorized DS",
        dtype=[float],
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        max_dim_x=3,
        doc="Min and Max limits, real_pos and then goes preset_position",
    )
    def important_parameters(self):
        res = [self.limit_min, self.limit_max, self.real_pos]
        for preset_pos in self.preset_positions:
            res.append(preset_pos)
        return res

    @attribute(
        label="internal ID of axis",
        dtype=int,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
        doc="Internal enumeration of device by hardware controller.",
    )
    def device_id_internal(self):
        return self._device_id_internal

    @attribute(
        label="Power Status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="the human readable power status.",
    )
    def power_status(self):
        return self._power_status

    def get_pos(self):
        return self._position

    def init_device(self):
        self._prev_pos = 0.0
        self._position = 0.0
        super().init_device()
        attr_prop = self.position.get_properties()
        attr_prop.min_value = self.limit_min
        attr_prop.max_value = self.limit_max
        self.position.set_properties(attr_prop)

    def read_position(self):
        state_ok = self.check_func_allowance(self.read_position)
        if state_ok == 1:
            res = self.read_position_local()
            if not operation_succeeded(res):
                self.error(f"Could not read position of {self.device_name}: {res}")
        return self._position

    @abstractmethod
    def read_position_local(self) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    def write_position(self, pos):
        self.debug_stream(f"Setting position {pos} of {self.device_name}.")
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok == 1:
            pos = float(pos)
            if pos <= self.limit_max and pos >= self.limit_min:
                self._prev_pos = self._position
                res = self.write_position_local(pos)
                self._prev_pos = self._position
                if not operation_succeeded(res):
                    self.error(f"Could not write position of {self.device_name}: {res}")
            else:
                self.error(
                    f"Could not write position of {self.device_name}: position out of limit:"
                    f"({self.limit_min}:{self.limit_max})"
                )

    def _position_within_limits(self, position: float) -> bool:
        return self.limit_min <= position <= self.limit_max

    @abstractmethod
    def write_position_local(self, pos) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(dtype_in=float, doc_in="Redefines position of axis.")
    def define_position(self, position):
        self.debug_stream(f"Setting position {position} of {self.device_name}.")
        state_ok = self.check_func_allowance(self.define_position)
        if state_ok == 1:
            res = self.define_position_local(position)
            if not operation_succeeded(res):
                self.error(f"{res}")
            else:
                self.debug_stream(
                    f"Position for {self.device_name} is redefined to {position}."
                )
            self.read_position()

    @abstractmethod
    def define_position_local(self, position) -> Union[int, str]:
        pass

    @command(dtype_in=float, doc_in="Takes pos of axis in float.")
    def move_axis_abs(self, pos):
        self.move_axis(pos)

    @command(dtype_in=float, doc_in="Takes rel pos of axis in float.")
    def move_axis_rel(self, rel_pos):
        self.move_axis(self._position + rel_pos)

    def move_axis(self, pos):
        pos = float(pos)
        self.info(f"Moving axis of device {self.device_name} to {pos}.")
        with self._get_lifecycle_lock():
            state_ok = self.check_func_allowance(self.move_axis)
            if state_ok != 1:
                return (
                    f"check_func_allowance of {self.move_axis} did not work. "
                    f"Check {self.RULES}."
                )
            if not self._position_within_limits(pos):
                result = (
                    f"Moving to {pos} was NOT started: position out of limit "
                    f"({self.limit_min}:{self.limit_max})"
                )
                self.error(result)
                return result
            if getattr(self, "_motion_stop_in_progress", False):
                result = (
                    f"Moving to {pos} was NOT started: stop is already in progress."
                )
                self.error(result)
                return result
            if getattr(self, "_active_motion_operation_id", None) is not None:
                result = (
                    f"Moving to {pos} was NOT started: another move is already in progress."
                )
                self.error(result)
                return result
            operation_id = getattr(self, "_motion_operation_id", 0) + 1
            self._motion_operation_id = operation_id
            self._active_motion_operation_id = operation_id

        try:
            res = self.move_axis_local(pos)
            if not operation_succeeded(res):
                self.error(f"Moving to {pos} was NOT accomplished with success: {res}")
                return str(res)

            with self._get_lifecycle_lock():
                stop_event = (
                    getattr(self, "_motion_stop_complete", None)
                    if getattr(self, "_motion_stop_in_progress", False)
                    and getattr(self, "_motion_stop_target_operation_id", None)
                    == operation_id
                    else None
                )
            if stop_event is not None:
                stop_event.wait()

            with self._get_lifecycle_lock():
                was_stopped = (
                    getattr(self, "_stopped_motion_operation_id", -1) >= operation_id
                )
            if was_stopped:
                return f"Moving to {pos} was stopped."

            self.read_position()
            with self._get_lifecycle_lock():
                stop_event = (
                    getattr(self, "_motion_stop_complete", None)
                    if getattr(self, "_motion_stop_in_progress", False)
                    and getattr(self, "_motion_stop_target_operation_id", None)
                    == operation_id
                    else None
                )
            if stop_event is not None:
                stop_event.wait()

            with self._get_lifecycle_lock():
                was_stopped = (
                    getattr(self, "_stopped_motion_operation_id", -1) >= operation_id
                )
                if was_stopped:
                    return f"Moving to {pos} was stopped."
                if pos == self._position:
                    self.info_stream(f"Moving to {pos} was accomplished with success.")
                    return 0
                else:
                    result = (
                        f"Moving to {pos} was NOT accomplished with success. Actual pos is {self._position}"
                    )
                    self.error(result)
                    return result
        finally:
            with self._get_lifecycle_lock():
                if getattr(self, "_active_motion_operation_id", None) == operation_id:
                    self._active_motion_operation_id = None

    @abstractmethod
    def move_axis_local(self, pos) -> Union[int, str]:
        pass

    @command
    def stop_movement(self):
        self.info(f"Stopping axis movement of device {self.device_name}.")
        with self._get_lifecycle_lock():
            state_ok = self.check_func_allowance(self.stop_movement)
            if state_ok != 1:
                return
            if getattr(self, "_motion_stop_in_progress", False):
                self.error(f"Stop for {self.device_name} is already in progress.")
                return
            operation_id = getattr(self, "_active_motion_operation_id", None)
            stop_token = getattr(self, "_motion_stop_token", 0) + 1
            stop_event = Event()
            self._motion_stop_token = stop_token
            self._motion_stop_in_progress = True
            self._motion_stop_target_operation_id = operation_id
            self._motion_stop_complete = stop_event

        succeeded = False
        try:
            result = self.stop_movement_local()
            succeeded = operation_succeeded(result)
            if not succeeded:
                self.error(f"Could not stop {self.device_name}: {result}")
                return
            with self._get_lifecycle_lock():
                if operation_id is not None:
                    self._stopped_motion_operation_id = max(
                        getattr(self, "_stopped_motion_operation_id", -1), operation_id
                    )
            self.get_controller_status()
        finally:
            with self._get_lifecycle_lock():
                if getattr(self, "_motion_stop_token", None) == stop_token:
                    self._motion_stop_in_progress = False
                    self._motion_stop_target_operation_id = None
                    stop_event.set()

    @abstractmethod
    def stop_movement_local(self) -> Union[int, str]:
        pass


class DS_MOTORIZED_MULTI_AXES(DS_General):
    """ "
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """

    polling = 500
    RULES = {
        "read_position_axis": [DevState.ON],
        "define_position_axis": [DevState.ON],
        "stop_axis": [DevState.ON, DevState.STANDBY, DevState.MOVING, DevState.OFF],
        "set_param_axis": [DevState.ON],
        "move_axis": [DevState.ON],
        "init_axis": [DevState.ON],
        "turn_on_axis": [DevState.ON],
        "turn_off_axis": [DevState.ON],
        "get_status_axis": [DevState.ON],
        **DS_General.RULES,
    }

    delay_lines_parameters = device_property(
        dtype=str
    )  # Specific for Controller: see, e.g., DS_OWIS_PS90
    dll_path = device_property(dtype=str, default_value="")

    @attribute(
        label="Axes states",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Gives list of axes states as str of python dict{id: state}",
        polling_period=polling,
        abs_change="",
    )
    def states(self):
        states = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            states[axis_id] = axis_param["state"]
        return str(states)

    @attribute(
        label="Axes positions",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Gives list of axes positions as str of python dict{id: state}",
        polling_period=polling,
        abs_change="",
    )
    def positions(self):
        position = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            position[axis_id] = axis_param["position"]
        return str(position)

    @attribute(
        label="Axes device_names",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Gives list of axes device names as str of python dict{id: name}.",
    )
    def device_names(self):
        names = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            names[axis_id] = axis_param["device_name"]
        return str(names)

    @attribute(
        label="Axes friendly_names",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Gives list of axes friendly names as str of python dict{id: name}.",
    )
    def friendly_names(self):
        names = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            names[axis_id] = axis_param["friendly_name"]
        return str(names)

    def init_device(self):
        super().init_device()

        try:
            self._delay_lines_parameters = self._parse_delay_lines_parameters(
                self.delay_lines_parameters
            )
        except (ConfigurationError, KeyError, TypeError, ValueError) as e:
            self.set_state(DevState.FAULT)
            self.error(
                f"{self.device_name} could not parse delay_lines_parameters from DB: "
                f"{self.delay_lines_parameters}. Error: {e}"
            )

    @staticmethod
    def _parse_delay_lines_parameters(raw_value) -> Dict[int, Dict[Any, Any]]:
        """Validate JSON and legacy literal multi-axis configuration."""
        parsed = parse_structured_config(raw_value, name="delay_lines_parameters")
        if not isinstance(parsed, dict):
            raise ConfigurationError(
                f"delay_lines_parameters must be a dict, got {type(parsed).__name__}"
            )

        required = (
            "wait_time",
            "limit_min",
            "limit_max",
            "real_pos",
            "preset_positions",
        )
        normalized: Dict[int, Dict[Any, Any]] = {}
        for raw_axis, axis_parameters in parsed.items():
            if isinstance(raw_axis, bool):
                raise ConfigurationError("axis ids must be integers, not booleans")
            try:
                axis = int(raw_axis)
            except (TypeError, ValueError) as error:
                raise ConfigurationError(f"invalid axis id {raw_axis!r}") from error
            if str(axis) != str(raw_axis) and raw_axis != axis:
                raise ConfigurationError(f"invalid axis id {raw_axis!r}")
            if axis in normalized:
                raise ConfigurationError(f"duplicate axis id {axis}")
            if not isinstance(axis_parameters, dict):
                raise ConfigurationError(f"axis {axis} parameters must be a dict")
            missing = [key for key in required if key not in axis_parameters]
            if missing:
                raise ConfigurationError(
                    f"axis {axis} missing required fields: {missing}"
                )
            if isinstance(axis_parameters["wait_time"], bool) or not isinstance(
                axis_parameters["wait_time"], int
            ):
                raise ConfigurationError(f"axis {axis} wait_time must be an int")
            for key in ("limit_min", "limit_max", "real_pos"):
                value = axis_parameters[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ConfigurationError(f"axis {axis} {key} must be numeric")
            presets = axis_parameters["preset_positions"]
            if not isinstance(presets, list) or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in presets
            ):
                raise ConfigurationError(
                    f"axis {axis} preset_positions must be a list of numbers"
                )
            limit_min = float(axis_parameters["limit_min"])
            limit_max = float(axis_parameters["limit_max"])
            if limit_min > limit_max:
                raise ConfigurationError(
                    f"axis {axis} limit_min cannot exceed limit_max"
                )
            if not limit_min <= float(axis_parameters["real_pos"]) <= limit_max:
                raise ConfigurationError(f"axis {axis} real_pos is outside limits")
            copied = dict(axis_parameters)
            copied["limit_min"] = limit_min
            copied["limit_max"] = limit_max
            copied["real_pos"] = float(axis_parameters["real_pos"])
            copied["preset_positions"] = [float(value) for value in presets]
            copied["position"] = 0.0
            copied["state"] = DevState.OFF
            normalized[axis] = copied
        return normalized

    def _axis_parameters(self, axis) -> Dict[Any, Any]:
        if isinstance(axis, bool):
            raise ValueError("axis id must be an integer")
        try:
            axis_id = int(axis)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid axis id {axis!r}") from error
        if axis_id not in self._delay_lines_parameters:
            raise ValueError(f"unknown axis {axis_id}")
        return self._delay_lines_parameters[axis_id]

    def _axis_error(self, axis) -> str:
        try:
            self._axis_parameters(axis)
        except ValueError as error:
            self.error(f"{self.device_name}: {error}")
            return str(error)
        return ""

    def _validated_axis_id(self, axis):
        self._axis_parameters(axis)
        return int(axis)

    def _validated_axis_move(self, args):
        if not isinstance(args, (list, tuple)) or len(args) != 2:
            raise ValueError("move_axis expects [axis, position]")
        axis = self._validated_axis_id(args[0])
        position = args[1]
        if isinstance(position, bool):
            raise ValueError("position must be numeric")
        try:
            position = float(position)
        except (TypeError, ValueError) as error:
            raise ValueError("position must be numeric") from error
        parameters = self._axis_parameters(axis)
        if not parameters["limit_min"] <= position <= parameters["limit_max"]:
            raise ValueError(
                f"position {position} is outside axis {axis} limits "
                f"({parameters['limit_min']}:{parameters['limit_max']})"
            )
        return [axis, position]

    @command(
        dtype_in=int,
        doc_in="Input is axis id: int",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def init_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return axis_error
        axis = int(axis)
        state_ok = self.check_func_allowance(self.init_axis)
        if state_ok == 1:
            res = self.init_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not initialize axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.init_axis} did not work. Check {self.RULES}."
        return str(res)

    @abstractmethod
    def init_axis_local(self, axis: int) -> Union[DevState, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis id: int",
        dtype_out=int,
        doc_out="Provides state of the axis.",
    )
    def get_status_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return DevState.FAULT
        axis = int(axis)
        state_ok = self.check_func_allowance(self.get_status_axis)
        if state_ok == 1:
            res = self.get_status_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not get status for axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.get_status_axis} did not work. Check {self.RULES}."
        return self._delay_lines_parameters[axis]["state"]

    @abstractmethod
    def get_status_axis_local(self, axis: int) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=[float],
        doc_in="Input args[axis:int, pos:float]",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def define_position_axis(self, args):
        if not isinstance(args, (list, tuple)) or len(args) != 2:
            res = "define_position_axis expects [axis, position]"
            self.error(f"{self.device_name}: {res}")
            return res
        axis_error = self._axis_error(args[0])
        if axis_error:
            return axis_error
        normalized_args = [int(args[0]), args[1]]
        state_ok = self.check_func_allowance(self.define_position_axis)
        if state_ok == 1:
            res = self.define_position_axis_local(normalized_args)
            if not operation_succeeded(res):
                self.error(
                    f"Could not define position for axis {normalized_args[0]} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.define_position_axis} did not work. Check {self.RULES}."
        return str(res)

    @abstractmethod
    def define_position_axis_local(self, args) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis_id: int",
        dtype_out=float,
        doc_out="Return axis position.",
    )
    def read_position_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return float("nan")
        axis = int(axis)
        state_ok = self.check_func_allowance(self.read_position_axis)
        if state_ok == 1:
            res = self.read_position_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not read position for axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.read_position_axis} did not work. Check {self.RULES}."
        return self._delay_lines_parameters[axis]["position"]

    @abstractmethod
    def read_position_axis_local(self, axis: int) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis_id: int, other parameters are loaded from DB: "
        "pitch (1), revolution (2), gear_ratio (3), speed (4), limit_min (5), limit_max (6)",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def set_param_axis(self, axis):
        axis_error = self._axis_error(axis)
        if axis_error:
            return axis_error
        axis = int(axis)
        state_ok = self.check_func_allowance(self.set_param_axis)
        if state_ok == 1:
            res = self.set_param_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not set parameters for axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.set_param_axis} did not work. Check {self.RULES}."
        return str(res)

    @abstractmethod
    def set_param_axis_local(self, args) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis_id: int",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def turn_on_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return axis_error
        axis = int(axis)
        state_ok = self.check_func_allowance(self.turn_on_axis)
        if state_ok == 1:
            res = self.turn_on_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not turn on axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.turn_on_axis} did not work. Check {self.RULES}."
        return str(res)

    @abstractmethod
    def turn_on_axis_local(self, axis: int) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis_id: int",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def turn_off_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return axis_error
        axis = int(axis)
        state_ok = self.check_func_allowance(self.turn_off_axis)
        if state_ok == 1:
            res = self.turn_off_axis_local(axis)
            if not operation_succeeded(res):
                self.error(
                    f"Could not turn off axis {axis} of {self.device_name}: {res}"
                )
        else:
            res = f"check_func_allowance of {self.turn_off_axis} did not work. Check {self.RULES}."
        return str(res)

    @abstractmethod
    def turn_off_axis_local(self, axis: int) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=[float],
        doc_in="Input is axis_id: int and then position value.",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def move_axis(self, args):
        try:
            args = self._validated_axis_move(args)
        except ValueError as error:
            self.error(f"{self.device_name}: {error}")
            return str(error)
        axis, position = args
        with self._get_lifecycle_lock():
            state_ok = self.check_func_allowance(self.move_axis)
            if state_ok != 1:
                return (
                    f"check_func_allowance of {self.move_axis} did not work. "
                    f"Check {self.RULES}."
                )
            stop_in_progress = getattr(self, "_axis_stop_in_progress", {})
            if axis in stop_in_progress:
                result = f"Axis {axis} move rejected: stop is already in progress."
                self.error(f"{self.device_name}: {result}")
                return result
            active_ids = getattr(self, "_active_axis_motion_operation_ids", {})
            if axis in active_ids:
                result = f"Axis {axis} move rejected: movement already in progress."
                self.error(f"{self.device_name}: {result}")
                return result
            operation_ids = getattr(self, "_axis_motion_operation_ids", {})
            operation_id = operation_ids.get(axis, 0) + 1
            operation_ids[axis] = operation_id
            self._axis_motion_operation_ids = operation_ids
            active_ids[axis] = operation_id
            self._active_axis_motion_operation_ids = active_ids

        try:
            res = self.move_axis_local(args)
            if not operation_succeeded(res):
                self.error(f"Could not move axis {axis} of {self.device_name}: {res}")
                return str(res)

            with self._get_lifecycle_lock():
                stop_in_progress = getattr(self, "_axis_stop_in_progress", {})
                stop_targets = getattr(self, "_axis_stop_target_operation_ids", {})
                stop_events = getattr(self, "_axis_stop_complete_events", {})
                stop_event = (
                    stop_events.get(axis)
                    if axis in stop_in_progress
                    and stop_targets.get(axis) == operation_id
                    else None
                )
            if stop_event is not None:
                stop_event.wait()

            with self._get_lifecycle_lock():
                stopped_ids = getattr(self, "_stopped_axis_motion_operation_ids", {})
            if stopped_ids.get(axis, -1) >= operation_id:
                return str(res)

            self.read_position_axis(axis)
            with self._get_lifecycle_lock():
                stop_in_progress = getattr(self, "_axis_stop_in_progress", {})
                stop_targets = getattr(self, "_axis_stop_target_operation_ids", {})
                stop_events = getattr(self, "_axis_stop_complete_events", {})
                stop_event = (
                    stop_events.get(axis)
                    if axis in stop_in_progress
                    and stop_targets.get(axis) == operation_id
                    else None
                )
            if stop_event is not None:
                stop_event.wait()

            with self._get_lifecycle_lock():
                stopped_ids = getattr(self, "_stopped_axis_motion_operation_ids", {})
                if stopped_ids.get(axis, -1) >= operation_id:
                    return str(res)
            return str(res)
        finally:
            with self._get_lifecycle_lock():
                active_ids = getattr(self, "_active_axis_motion_operation_ids", {})
                if active_ids.get(axis) == operation_id:
                    active_ids.pop(axis, None)
                    self._active_axis_motion_operation_ids = active_ids

    @command(dtype_in=float, doc_in="Input is axis_id: int and then position value.")
    def move_axis_abs(self, args):
        self.move_axis(args)

    @abstractmethod
    def move_axis_local(self, args) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""

    @command(
        dtype_in=int,
        doc_in="Input is axis_id: int",
        dtype_out=str,
        doc_out=standard_str_output,
    )
    def stop_axis(self, axis: int):
        axis_error = self._axis_error(axis)
        if axis_error:
            return axis_error
        axis = int(axis)
        with self._get_lifecycle_lock():
            state_ok = self.check_func_allowance(self.stop_axis)
            if state_ok != 1:
                return (
                    f"check_func_allowance of {self.stop_axis} did not work. "
                    f"Check {self.RULES}."
                )
            stop_in_progress = getattr(self, "_axis_stop_in_progress", {})
            if axis in stop_in_progress:
                result = f"Axis {axis} stop is already in progress."
                self.error(f"{self.device_name}: {result}")
                return result
            active_ids = getattr(self, "_active_axis_motion_operation_ids", {})
            operation_id = active_ids.get(axis)
            stop_tokens = getattr(self, "_axis_stop_tokens", {})
            stop_token = stop_tokens.get(axis, 0) + 1
            stop_tokens[axis] = stop_token
            stop_in_progress[axis] = stop_token
            stop_targets = getattr(self, "_axis_stop_target_operation_ids", {})
            stop_targets[axis] = operation_id
            stop_events = getattr(self, "_axis_stop_complete_events", {})
            stop_event = Event()
            stop_events[axis] = stop_event
            self._axis_stop_tokens = stop_tokens
            self._axis_stop_in_progress = stop_in_progress
            self._axis_stop_target_operation_ids = stop_targets
            self._axis_stop_complete_events = stop_events

        try:
            res = self.stop_axis_local(axis)
            if not operation_succeeded(res):
                self.error(f"Could not stop axis {axis} of {self.device_name}: {res}")
                return str(res)

            with self._get_lifecycle_lock():
                if operation_id is not None:
                    stopped_ids = getattr(self, "_stopped_axis_motion_operation_ids", {})
                    stopped_ids[axis] = max(stopped_ids.get(axis, -1), operation_id)
                    self._stopped_axis_motion_operation_ids = stopped_ids
            self.info(f"Axis {axis} was stopped by user.", True)
            return str(res)
        finally:
            with self._get_lifecycle_lock():
                stop_in_progress = getattr(self, "_axis_stop_in_progress", {})
                if stop_in_progress.get(axis) == stop_token:
                    stop_in_progress.pop(axis, None)
                    self._axis_stop_in_progress = stop_in_progress
                    stop_targets = getattr(self, "_axis_stop_target_operation_ids", {})
                    stop_targets.pop(axis, None)
                    self._axis_stop_target_operation_ids = stop_targets
                    stop_events = getattr(self, "_axis_stop_complete_events", {})
                    stop_events.pop(axis, None)
                    self._axis_stop_complete_events = stop_events
                    stop_event.set()

    @abstractmethod
    def stop_axis_local(self, args) -> Union[int, str]:
        """Returns 0 if success, if not error as a str"""
