from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, List

from DeviceServers.General.DS_general import DS_General, GeneralOrderInfo
from utilities.myfunc import ping
from dataclasses import dataclass
from typing import Dict

@dataclass
class OrderPulsesInfo(GeneralOrderInfo):
    pin: int
    number_of_pulses: int
    dt: int  # in us
    time_delay: int  # in us
    order_done: bool
    ready_to_delete: bool
    pulses_done: int


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
        self._blocking_pins = {}
        self._names = []
        self._pin_ids = []
        self._states = []
        self.pins = {}
        self.pulses_orders: Dict[str, OrderPulsesInfo] = {}
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
            res = self.set_pin_state_local(pins_values)
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

    @command(dtype_in=str, doc_in='Pass the name of order', doc_out='Give the order pulses finished', dtype_out=int)
    def give_pulses_done(self, name):
        res = -1
        if name in self.orders:
            res = self.orders[name].pulses_done
        return res

    def register_order_local(self, name, value):
        from time import time
        from threading import Thread
        pin = value[0]
        number_of_pulses = value[1]
        dt = value[2]
        time_delay = value[3]
        if pin not in self._blocking_pins:
            order_info = OrderPulsesInfo(order_done=False, order_timestamp=time(), ready_to_delete=False, pin=pin,
                                         number_of_pulses=number_of_pulses, dt=dt, time_delay=time_delay, pulses_done=0)
            self.info(f'Order {order_info} was registered.', True)
            self.orders[name] = order_info
            order_thread = Thread(target=self.generate_pulses, args=[order_info])
            order_thread.start()
            self._blocking_pins[pin] = name
            return 0
        else:
            return -1

    @abstractmethod
    def generate_TTL(self, pin: int, dt: int, time_delay: int):
        pass

    def generate_pulses(self, order: OrderPulsesInfo):
        number_of_pulses = order.number_of_pulses
        for i in range(number_of_pulses):
            self.generate_TTL(order.pin, order.dt, order.time_delay)
            order.pulses_done += 1
            if order.order_done:
                break
        order.order_done = True

    def give_order_local(self, name):
        res = 0
        if name in self.orders:
            order: OrderPulsesInfo = self.orders[name]
            order.ready_to_delete = True
            res = order.pulses_done
        del self._blocking_pins[order.pin]
        del self.orders[name]
        return res

    @abstractmethod
    def set_pin_state_local(self, pin_id_value: List[int]) -> Union[int, str]:
        """
        It takes List of pin_id, pin_value. So it change the state of one pin, not all
        """
        pass

    @abstractmethod
    def value_from_pin(self, pin_id: int):
        pass

    @abstractmethod
    def get_pin_state_local(self, pin_id: int) -> Union[int, str]:
        pass

    @staticmethod
    def check_ip(ip_address):
        return ping(ip_address)