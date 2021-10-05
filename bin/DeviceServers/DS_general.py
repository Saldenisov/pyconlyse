from abc import abstractmethod

import numpy
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, InfoIt, PipeWriteType, Pipe
from tango.server import Device, attribute, command, pipe, device_property
from typing import Tuple, Union, List
from threading import Thread
from time import sleep


class DS_General(Device):
    device_id = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    server_id = device_property(dtype=int)

    RULES = {'turn_on': [DevState.OFF, DevState.FAULT, DevState.STANDBY], 'turn_off': [DevState.ON, DevState.STANDBY],
             'find_device': [DevState.OFF, DevState.FAULT, DevState.STANDBY],
             'get_controller_status': [DevState.ON, DevState.MOVING]}

    @property
    def _version_(self):
        raise NotImplementedError

    @property
    def _model_(self):
        raise NotImplementedError

    @pipe(label="DS_Info", doc="General info about DS.")
    def read_info_ds(self):
        return ('info_ds', dict(manufacturer=f'{self.__class__.__name__}',
                            model=self._model_,
                            version_number=self._version_,
                            device_id=self.device_id))

    @attribute(label="comments", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Last essential comment.", polling_period=250)
    def last_comments(self):
        return self._comments

    @attribute(label="error", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Last error.", polling_period=250)
    def last_error(self):
        return self._error

    @attribute(label="URI", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="The URI of device.")
    def uri(self):
        return self._uri

    def error(self, error_in):
        self.error_stream(error_in)
        self._error = error_in
        self._n = 0
        print(error_in)

    def info(self, info_in, printing=False):
        self.info_stream(info_in)
        self._comments = info_in
        if printing:
            print(info_in)

    @abstractmethod
    def init_device(self):
        self._comments = '...'
        self._error = '...'
        self._n = 0
        internal_time = Thread(target=self.int_time)
        internal_time.start()
        self._status_check_fault = 0
        self.set_state(DevState.FAULT)
        Device.init_device(self)

    @abstractmethod
    def find_device(self) -> Tuple[int, str]:
        """
        returns device_id_internal and uri if applicable
        """
        pass

    def check_func_allowance(self, func) -> int:
        state_ok = -1
        if func.__name__ in self.RULES:
            rules_for_func = self.RULES[func.__name__]
            state = self.get_state()
            if state in rules_for_func:
                state_ok = 1
        else:
            self.error(f'Function {func} is not in RULES: {self.RULES}.')
        return state_ok

    def int_time(self):
        while 1:
            sleep(0.5)
            self._n += 1
            if self._n > 10:
                self._error = ''
                self._n = 0

    def device_name(self) -> str:
        return f'Device {self.device_id} {self.friendly_name}'

    @command(polling_period=250)
    def get_controller_status(self):
        state_ok = self.check_func_allowance(self.get_controller_status)
        if state_ok == 1:
            res = self.get_controller_status_local()
            if res != 0:
                self.error(f'{res}')

    @abstractmethod
    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @command
    def turn_on(self):
        self.info(f"Turning ON {self.device_name()}.", True)
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok == 1:
            res = self.turn_on_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name()} WAS turned ON.", True)

    @abstractmethod
    def turn_on_local(self) -> Union[int, str]:
        pass

    @command
    def turn_off(self):
        self.debug_stream(f"Turning off {self.device_name()}.")
        print(f"Turning off device {self.device_name()}.")
        state_ok = self.check_func_allowance(self.turn_off)
        if state_ok == 1:
            res = self.turn_off_local()
            if res != 0:
                self.error_stream(f"{res}")
            else:
                print(f"Device {self.device_name()} is turned OFF.")

    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass


class DS_PDU(DS_General):
    """
    bla-bla
    """
    RULES = {'set_channels_states': [DevState.ON, DevState.STANDBY],
             'get_channels_states': [DevState.ON, DevState.STANDBY], **DS_General.RULES
             }
    ip_address = device_property(dtype=str)
    authentication_name = device_property(dtype=str)
    authentication_password = device_property(dtype=str)
    number_outputs = device_property(dtype=str)

    def init_device(self):
        super().init_device()
        self._device_id_internal = -1
        self._outputs = {}
        self._device_id_internal, self._uri = self.find_device()
        if self._device_id_internal >= 0:
            self.info(f"Device {self.device_name()} was found.", True)
            self.set_state(DevState.OFF)
        else:
            self.info(f"Device {self.device_name()} was NOT found.", True)
            self.set_state(DevState.FAULT)

    # @command(doc_in="Reads PDU channels state.", polling_period=500, dtype_out=)
    # def get_channels_states(self):
    #     self.debug_stream(f'Getting PDU channels states of {self.device_name()}.')
    #     state_ok = self.check_func_allowance(self.get_channels_state())
    #     if state_ok == 1:
    #         res = self.get_channels_state_local()
    #         if res != 0:
    #             self.error(f'{res}')
    #     return self._outputs

    @abstractmethod
    def get_channels_state_local(self) -> Union[int, str]:
        pass

    @command(dtype_in=[int], doc_in='Function that changes state of outputs of the PDU.',
             display_level=DispLevel.OPERATOR)
    def set_channels_states(self, outputs: List[int]):
        self.info(f"Setting output channels of device {self.device_name()} to {outputs}.")
        state_ok = self.check_func_allowance(self.set_channels_states)
        if state_ok == 1:
            res = self.set_channels_states_local(outputs)
            if res != 0:
                self.error(f'Setting output channels of device {self.device_name()} was NOT '
                           f'accomplished with success: {res}')

    @abstractmethod
    def set_channels_states_local(self, outputs: List[int]) -> Union[int, str]:
        pass


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

    def init_device(self):
        super().init_device()
        self._prev_pos = 0.0
        self._position = 0.0
        self._device_id_internal = -1
        self._temperature = None
        self._power_current = 0
        self._power_voltage = 0
        self._power_status = self.POWER_STATES[0]
        device_id_internal, uri = self.find_device()
        self._uri = uri
        self._device_id_internal = device_id_internal


        if self._device_id_internal >= 0:
            self.info(f"Device {self.device_name()} was found.", True)
            self.set_state(DevState.OFF)
        else:
            self.info(f"Device {self.device_name()} was NOT found.", True)
            self.set_state(DevState.FAULT)

    def read_position(self):
        state_ok = self.check_func_allowance(self.read_position)
        if state_ok == 1:
            res = self.read_position_local()
            if res != 0:
                self.error(f'Could not read position of {self.device_name()}: {res}')
        return self._position

    @abstractmethod
    def read_position_local(self) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    def write_position(self, pos):
        self.debug_stream(f'Setting position {pos} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok == 1:
            pos = float(pos)
            if pos <= self.limit_max and pos >= self.limit_min:
                self._prev_pos = self._position
                res = self.write_position_local(pos)
                self._prev_pos = self._position
                if res != 0:
                    self.error(f'Could not write position of {self.device_name()}: {res}')
            else:
                self.error(f'Could not write position of {self.device_name()}: position out of limit:'
                                  f'({self.limit_min}:{self.limit_max})')

    @abstractmethod
    def write_position_local(self, pos) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=float, doc_in="Redefines position of axis.")
    def define_position(self, position):
        self.debug_stream(f'Setting position {position} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.define_position)
        if state_ok == 1:
            res = self.define_position_local(position)
            if res != 0:
                self.error(f'{res}')
            else:
                self.debug_stream(f'Position for {self.device_name()} is redefined to {position}.')
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
        self.info(f"Moving axis of device {self.device_name()} to {pos}.")
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
        self.info(f"Stopping axis movement of device {self.device_name()}.")
        state_ok = self.check_func_allowance(self.move_axis_abs)
        if state_ok == 1:
            self.stop_movement_local()
            self.get_controller_status()

    @abstractmethod
    def stop_movement_local(self) -> Union[int, str]:
        pass


class DS_MOTORIZED_MULTI_AXES(DS_MOTORIZED_MONO_AXIS):
    n_axes = device_property(dtype=int, default_value=4)
    wait_time = device_property(dtype=int, default_value=5000)
    limit_min = device_property(dtype='DevVarFloatArray')
    limit_max = device_property(dtype='DevVarFloatArray')
    real_pos = device_property(dtype='DevVarFloatArray')
    preset_positions = device_property(dtype=str)  # '[[1, 2, 3], [10, 20, 30], [...], ...]'

    @attribute(label="Important parameters of motorized DS", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="[Min and Max limits, real_pos and then goes preset_positions] for all axes as a string"
                   "'[[-100, 100, 100, [10, 20, 40, 0]], [...[...]], [...[..]],...'")
    def important_parameters(self):
        res = []
        preset_pos = list(self.preset_positions)
        for pp in preset_pos:
            local = []
            for mn, mx, rp in zip(self.limit_min, self.limit_max, self.real_pos):
                local.append(mn, mx, rp)
            local.append(pp)
            res.append(local)
        return str(res)

    @attribute(label="internal ID of axis", dtype=int, display_level=DispLevel.EXPERT, access=AttrWriteType.READ,
               doc="Internal enumeration of device by hardware controller.")
    def device_id_internal(self):
        return self._device_id_internal

    @attribute(label="Power Status", dtype=[str], display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="The human readable power status of motors.", max_dim_x=10)
    def power_status(self):
        return self._power_status

    def init_device(self):
        super().init_device()
        self._prev_pos = [0.0] * self.n_axes
        self._position = [0.0] * self.n_axes
        self._power_status = [self.POWER_STATES[0]] * self.n_axes
        self._temperature = [None] * self.n_axes
        self._power_current = [0.0] * self.n_axes
        self._power_voltage = [0.0] * self.n_axes

    def read_position(self):
        state_ok = self.check_func_allowance(self.read_position)
        if state_ok == 1:
            res = self.read_position_local()
            if res != 0:
                self.error(f'Could not read position of {self.device_name()}: {res}')
        return self._position

    @abstractmethod
    def read_position_local(self) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    def write_position(self, pos):
        self.debug_stream(f'Setting position {pos} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok == 1:
            pos = float(pos)
            if pos <= self.limit_max and pos >= self.limit_min:
                self._prev_pos = self._position
                res = self.write_position_local(pos)
                self._prev_pos = self._position
                if res != 0:
                    self.error(f'Could not write position of {self.device_name()}: {res}')
            else:
                self.error(f'Could not write position of {self.device_name()}: position out of limit:'
                                  f'({self.limit_min}:{self.limit_max})')

    @abstractmethod
    def write_position_local(self, pos) -> Union[int, str]:
        """
        Returns 0 if success, if not error as a str
        """
        pass

    @command(dtype_in=float, doc_in="Redefines position of axis.")
    def define_position(self, position):
        self.debug_stream(f'Setting position {position} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.define_position)
        if state_ok == 1:
            res = self.define_position_local(position)
            if res != 0:
                self.error(f'{res}')
            else:
                self.debug_stream(f'Position for {self.device_name()} is redefined to {position}.')
            self.read_position()

    @abstractmethod
    def define_position_local(self, position) -> Union[int, str]:
        pass

    @command(dtype_in=float, doc_in="Takes pos of axis in float.")
    def move_axis_abs(self, pos, axis: int):
        self.move_axis(pos)

    @command(dtype_in=float, doc_in="Takes rel pos of axis in float.")
    def move_axis_rel(self, rel_pos, axis: int):
        self.move_axis(self._position + rel_pos)

    def move_axis(self, pos, axis: int):
        pos = float(pos)
        self.info(f"Moving axis of device {self.device_name()} to {pos}.")
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
    def move_axis_local(self, pos, axis: int) -> Union[int, str]:
        pass

    @command
    def stop_movement(self, axis: int):
        self.info(f"Stopping axis movement of device {self.device_name()}.")
        state_ok = self.check_func_allowance(self.move_axis_abs)
        if state_ok == 1:
            self.stop_movement_local()
            self.get_controller_status()

    @abstractmethod
    def stop_movement_local(self, axis: int) -> Union[int, str]:
        pass

