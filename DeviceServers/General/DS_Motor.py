from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any

from DeviceServers.General.DS_general import DS_General, standard_str_output


class DS_MOTORIZED_MONO_AXIS(DS_General):
    RULES = {'read_position': [DevState.ON, DevState.MOVING], 'write_position': [DevState.ON],
             'define_position': [DevState.ON], 'move_axis': [DevState.ON, DevState.STANDBY],
             'stop_axis': [DevState.MOVING, DevState.ON, DevState.STANDBY], **DS_General.RULES}

    POWER_STATES = {0: 'PWR_UNKNOWN', 1: 'PWR_OFF', 3: 'PWR_NORM', 4: 'PWR_REDUCED', 5: 'PWR_MAX'}

    wait_time = device_property(dtype=int, default_value=5000)
    limit_min = device_property(dtype=float)
    limit_max = device_property(dtype=float)
    real_pos = device_property(dtype=float)
    preset_positions = device_property(dtype='DevVarFloatArray')

    @attribute(label="Important parameters of motorized DS", dtype=[float], display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ, max_dim_x=3,
               doc="Min and Max limits, real_pos and then goes preset_position")
    def important_parameters(self):
        res = [self.limit_min, self.limit_max, self.real_pos]
        for preset_pos in self.preset_positions:
            res.append(preset_pos)
        return res

    @attribute(label="internal ID of axis", dtype=int, display_level=DispLevel.EXPERT, access=AttrWriteType.READ,
               doc="Internal enumeration of device by hardware controller.")
    def device_id_internal(self):
        return self._device_id_internal

    @attribute(label="Power Status", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="the human readable power status.")
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
            if res != 0:
                self.error(f'Could not read position of {self.device_name}: {res}')
        return self._position

    @abstractmethod
    def read_position_local(self) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    def write_position(self, pos):
        self.debug_stream(f'Setting position {pos} of {self.device_name}.')
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok == 1:
            pos = float(pos)
            if pos <= self.limit_max and pos >= self.limit_min:
                self._prev_pos = self._position
                res = self.write_position_local(pos)
                self._prev_pos = self._position
                if res != 0:
                    self.error(f'Could not write position of {self.device_name}: {res}')
            else:
                self.error(f'Could not write position of {self.device_name}: position out of limit:'
                                  f'({self.limit_min}:{self.limit_max})')

    @abstractmethod
    def write_position_local(self, pos) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=float, doc_in="Redefines position of axis.")
    def define_position(self, position):
        self.debug_stream(f'Setting position {position} of {self.device_name}.')
        state_ok = self.check_func_allowance(self.define_position)
        if state_ok == 1:
            res = self.define_position_local(position)
            if res != 0:
                self.error(f'{res}')
            else:
                self.debug_stream(f'Position for {self.device_name} is redefined to {position}.')
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
        state_ok = self.check_func_allowance(self.move_axis)
        asked_pos = pos
        if state_ok == 1:
            res = self.move_axis_local(pos)
            if res != 0:
                self.error(f'Moving to {pos} was NOT accomplished with success: {res}')
            self.read_position()
            if asked_pos == self._position:
                self.info_stream(f'Moving to {pos} was accomplished with success.')
            else:
                self.error(f'Moving to {pos} was NOT accomplished with success. Actual pos is {self._position}')

    @abstractmethod
    def move_axis_local(self, pos) -> Union[int, str]:
        pass

    @command
    def stop_movement(self):
        self.info(f"Stopping axis movement of device {self.device_name}.")
        state_ok = self.check_func_allowance(self.move_axis_abs)
        if state_ok == 1:
            self.stop_movement_local()
            self.get_controller_status()

    @abstractmethod
    def stop_movement_local(self) -> Union[int, str]:
        pass


class DS_MOTORIZED_MULTI_AXES(DS_General):
    """"
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """
    polling = 500
    RULES = {'read_position_axis': [DevState.ON],
             'define_position_axis': [DevState.ON],
             'stop_axis': [DevState.ON, DevState.STANDBY, DevState.MOVING, DevState.OFF],
             'set_param_axis': [DevState.ON],
             'move_axis': [DevState.ON],
             'init_axis': [DevState.ON],
             'turn_on_axis': [DevState.ON],
             'turn_off_axis': [DevState.ON],
             'get_status_axis': [DevState.ON], **DS_General.RULES}

    delay_lines_parameters = device_property(dtype=str)  # Specific for Controller: see, e.g., DS_OWIS_PS90
    dll_path = device_property(dtype=str, default_value='')

    @attribute(label="Axes states", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives list of axes states as str of python dict{id: state}", polling_period=polling, abs_change='')
    def states(self):
        states = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            states[axis_id] = axis_param['state']
        return str(states)

    @attribute(label="Axes positions", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives list of axes positions as str of python dict{id: state}", polling_period=polling,
               abs_change='')
    def positions(self):
        position = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            position[axis_id] = axis_param['position']
        return str(position)

    @attribute(label="Axes device_names", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ, doc="Gives list of axes device names as str of python dict{id: name}.")
    def device_names(self):
        names = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            names[axis_id] = axis_param['device_name']
        return str(names)

    @attribute(label="Axes friendly_names", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ, doc="Gives list of axes friendly names as str of python dict{id: name}.")
    def friendly_names(self):
        names = {}
        for axis_id, axis_param in self._delay_lines_parameters.items():
            names[axis_id] = axis_param['friendly_name']
        return str(names)

    def init_device(self):
        super().init_device()

        try:
            must_have = {'wait_time': int, 'limit_min': float, 'limit_max': float, 'real_pos': float,
                         'preset_positions': list}
            self._delay_lines_parameters: Dict[str, Dict[Any]] = eval(self.delay_lines_parameters)
            for ds_id, ds_param in self._delay_lines_parameters.items():
                for param_name, param_type in must_have.items():
                    if param_name not in ds_param.keys():
                        raise KeyError(f'{param_name} is not {ds_param} of axis {ds_id}.')
                    else:
                        if not isinstance(ds_param[param_name], param_type):
                            raise TypeError(f'{ds_param[param_name]} is a wrong type {type(ds_param[param_name])}, '
                                            f'must be {param_type}.')

                ds_param['position'] = 0.0
                ds_param['state'] = DevState.OFF

        except SyntaxError:
            self.set_state(DevState.FAULT)
            self.error(f"{self.device_name} could not eval delay_lines_parameters from DB: "
                       f"{self.delay_lines_parameters}")
        except KeyError as e:
            self.set_state(DevState.FAULT)
            self.error(e)
        except TypeError as e:
            self.set_state(DevState.FAULT)
            self.error(e)

    @command(dtype_in=int, doc_in='Input is axis id: int', dtype_out=str, doc_out=standard_str_output)
    def init_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.init_axis)
        if state_ok == 1:
            res = self.init_axis_local(axis)
            if res != 0:
                self.error(f'Could not initialize axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.init_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def init_axis_local(self, axis: int) -> Union[DevState, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis id: int', dtype_out=int, doc_out='Provides state of the axis.')
    def get_status_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.get_status_axis)
        if state_ok == 1:
            res = self.get_status_axis_local(axis)
            if res != 0:
                self.error(f'Could not get status for axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.get_status_axis} did not work. Check {self.RULES}.'
        return self._delay_lines_parameters[axis]['state']

    @abstractmethod
    def get_status_axis_local(self, axis: int) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=[float], doc_in='Input args[axis:int, pos:float]', dtype_out=str,
             doc_out=standard_str_output)
    def define_position_axis(self, args):
        state_ok = self.check_func_allowance(self.define_position_axis)
        if state_ok == 1:
            res = self.define_position_axis_local(args)
            if res != 0:
                try:
                    axis = args[0]
                except IndexError:
                    axis = None
                self.error(f'Could not define position for axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.define_position_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def define_position_axis_local(self, args) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis_id: int', dtype_out=float, doc_out='Return axis position.')
    def read_position_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.read_position_axis)
        if state_ok == 1:
            res = self.read_position_axis_local(axis)
            if res != 0:
                self.error(f'Could not read position for axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.read_position_axis} did not work. Check {self.RULES}.'
        return self._delay_lines_parameters[axis]['position']

    @abstractmethod
    def read_position_axis_local(self, axis: int) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis_id: int, other parameters are loaded from DB: '
                                  'pitch (1), revolution (2), gear_ratio (3), speed (4), limit_min (5), limit_max (6)',
             dtype_out=str, doc_out=standard_str_output)
    def set_param_axis(self, axis):
        state_ok = self.check_func_allowance(self.set_param_axis)
        if state_ok == 1:
            axis
            res = self.set_param_axis_local(axis)
            if res != 0:
                self.error(f'Could not set parameters for axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.set_param_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def set_param_axis_local(self, args) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis_id: int', dtype_out=str, doc_out=standard_str_output)
    def turn_on_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.turn_on_axis)
        if state_ok == 1:
            res = self.turn_on_axis_local(axis)
            if res != 0:
                self.error(f'Could not turn on axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.turn_on_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def turn_on_axis_local(self, axis: int) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis_id: int', dtype_out=str, doc_out=standard_str_output)
    def turn_off_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.turn_off_axis)
        if state_ok == 1:
            res = self.turn_off_axis_local(axis)
            if res != 0:
                self.error(f'Could not turn off axis {axis} of {self.device_name}: {res}')
        else:
            res = f'check_func_allowance of {self.turn_off_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def turn_off_axis_local(self, axis: int) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=[float], doc_in='Input is axis_id: int and then position value.', dtype_out=str, doc_out=standard_str_output)
    def move_axis(self, args):
        state_ok = self.check_func_allowance(self.move_axis)
        if state_ok == 1:
            res = self.move_axis_local(args)
            if res != 0:
                self.error(f'Could not move axis {args[0]} of {self.device_name}: {res}')
        return str(res)

    @command(dtype_in=float, doc_in='Input is axis_id: int and then position value.')
    def move_axis_abs(self, args):
        self.move_axis(args)

    @abstractmethod
    def move_axis_local(self, args) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=int, doc_in='Input is axis_id: int', dtype_out=str, doc_out=standard_str_output)
    def stop_axis(self, axis: int):
        state_ok = self.check_func_allowance(self.stop_axis)
        if state_ok == 1:
            res = self.stop_axis_local(axis)
            if res != 0:
                self.error(f'Could not stop axis {axis} of {self.device_name}: {res}')
            else:
                self.info(f'Axis {axis} was stopped by user.', True)
        else:
            res = f'check_func_allowance of {self.stop_axis} did not work. Check {self.RULES}.'
        return str(res)

    @abstractmethod
    def stop_axis_local(self, args) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass
