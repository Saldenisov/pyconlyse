from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, List

from DeviceServers.General.DS_general import DS_General


class DS_GPIO(DS_General):
    """
    bla-bla
    """
    RULES = {'set_pin_state': [DevState.ON, DevState.STANDBY], 'get_pin_state': [DevState.ON, DevState.STANDBY],
             **DS_General.RULES}

    ip_address = device_property(dtype=str)
    number_outputs = device_property(dtype=int)
    parameters = device_property(dtype=str)
    authentication_name = device_property(dtype=str, default_value='admin')
    authentication_password = device_property(dtype=str, default_value='admin')

    def init_device(self):
        self._names = []
        self._pin_ids = []
        self._states = []
        self.pins = {}
        super().init_device()
        for pin_param in self.parameters['Pins']:
            self._pin_ids.append(pin_param[0])
            self._names.append(pin_param[2])

    @attribute(label="Pin names", dtype=[str,], max_dim_x=30, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives list of pins' names.")
    def names(self):
        return self._names

    @attribute(label="Pins' ids", dtype=[int,], max_dim_x=30, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives list of pins' ids.")
    def pin_ids(self):
        return self._pin_ids

    @attribute(label="Pin states", dtype=[int,], max_dim_x=30, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives list of pins' states.", polling_period=500, abs_change='1')
    def states(self):
        return self._states

    @command(dtype_in=[int], doc_in='In [Pin_id, value] function that changes state of outputs of the controller.',
             display_level=DispLevel.OPERATOR)
    def set_pin_state(self, pins_values: List[int]):
        state_ok = self.check_func_allowance(self.set_pin_state)
        if state_ok == 1:
            res = self.set_pins_state_local(pins_values)
            if res != 0:
                self.error(f'Setting pin {pins_values[0]} value {pins_values[1]} of device {self.device_name} was NOT '
                           f'accomplished with success: {res}')

    @command(dtype_in=int, doc_in='In Pin_id function that changes state of outputs of the controller.',
             display_level=DispLevel.OPERATOR, dtype_out=int)
    def get_pin_state(self, pin_id: int):
        state_ok = self.check_func_allowance(self.get_pin_state)
        res = -1
        if state_ok == 1:
            res = self.get_pin_state_local(pin_id)
            if isinstance(res, str):
                self.error(f'Getting pin {pin_id} value of device {self.device_name} was NOT '
                           f'accomplished with success: {res}')
                res = -1
        return res

    @abstractmethod
    def set_pins_state_local(self, pins_values: List[int]) -> Union[int, str]:
        pass

    @abstractmethod
    def set_pin_state_local(self, gpio_pin: int, value: int) -> Union[int, str]:
        pass

    @abstractmethod
    def get_pin_state_local(self, pin_id: int) -> Union[int, str]:
        pass

