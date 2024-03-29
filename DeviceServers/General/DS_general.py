import time
import zlib
from abc import abstractmethod
from threading import Thread
from time import sleep
from typing import Union, Dict, Any

import msgpack
import numpy as np
import taurus
from tango import AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, pipe, device_property

from utilities.datastructures.mes_independent.measurments_dataclass import ArchiveData, Scalar, Array

standard_str_output = 'str: 0 if success, else error.'
from dataclasses import dataclass

@dataclass
class GeneralOrderInfo:
    order_done: bool
    order_timestamp: int
    ready_to_delete: bool

class DS_General(Device):
    device_id = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    server_id = device_property(dtype=int)
    always_on = device_property(dtype=int, default_value=0)
    archive = 'manip/general/archive'
    polling_main = 300
    RULES = {'turn_on': [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
             'turn_off': [DevState.ON, DevState.STANDBY, DevState.INIT, DevState.RUNNING],
             'find_device': [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
             'get_controller_status': [DevState.ON, DevState.MOVING, DevState.RUNNING, DevState.INIT]}

    @property
    def _version_(self):
        raise NotImplementedError

    @property
    def _model_(self):
        raise NotImplementedError

    @pipe(label="DS_Info", doc="General info about DS")
    def read_info_ds(self):
        return ('info_ds', dict(manufacturer=f'{self.__class__.__name__}',
                            model=self._model_,
                            version_number=self._version_,
                            device_id=self.device_id))

    @attribute(label='Always on?', dtype=int, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ_WRITE)
    def always_on_value(self):
        return self.always_on

    def write_always_on_value(self, value: int):
        self.always_on = value

    @attribute(label="Friendly name", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ_WRITE)
    def device_friendly_name(self):
        return self.friendly_name

    def write_device_friendly_name(self, friendly_name):
        self.friendly_name = friendly_name

    @attribute(label="comments", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Last essential comment.", polling_period=polling_main)
    def last_comment(self):
        return self._comment

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        self._comment = value

    @attribute(label="error", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Last error.", polling_period=polling_main)
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
        self._comment = info_in
        if printing:
            print(info_in)

    @command(dtype_in=str)
    def register_client_lock(self, name):
        if name:
            self.locking_client_token = name
            self.locked_client = True

    @command
    def unregister_client_lock(self):
        self.locking_client_token = ''
        self.locked_client = False

    @abstractmethod
    def init_device(self):
        self.orders: Dict[str, GeneralOrderInfo] = {}
        self.previous_archive_state: Dict[str, Any] = {}
        self.archive_state: Dict[str, Any] = {}
        self.locking_client_token = ''
        self.locked_client = False
        self._comment = '...'
        self._error = '...'
        self._n = 0
        internal_time = Thread(target=self.int_time)
        internal_time.start()
        self._status_check_fault = 0
        self.prev_state = DevState.FAULT
        Device.init_device(self)
        if hasattr(self, 'parameters'):
            self.parameters = eval(str(self.parameters))
        self.archive = taurus.Device(self.archive)
        self.set_state(DevState.OFF)
        self._device_id_internal = -1
        self._uri = b''
        self.find_device()

        if self._device_id_internal != -1:
            self.info(f"{self.device_name} was found.", True)
        else:
            self.info(f"{self.device_name} was NOT found.", True)
            self.set_state(DevState.FAULT)

    @abstractmethod
    def register_variables_for_archive(self):
        self.archive_state['State'] = (self.get_state, 'int8')

    def send_state_archive(self):
        res = {}
        for key, prev_value in self.previous_archive_state.items():
            current_value = self.archive_state[key][0]()
            dt = self.archive_state[key][1]
            res[key] = current_value
            if prev_value != current_value:
                data = self.form_archive_data(current_value, key, dt)
                self.write_to_archive(data)
        self.previous_archive_state = res

    def fix_state(self):
        res = {}
        for key, value in self.archive_state.items():
            res[key] = value[0]()
        self.previous_archive_state = res
        self.info('Fixing archiving state', True)

    @abstractmethod
    def find_device(self):
        """
        sets device_id_internal and uri if applicable
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

    @property
    def device_name(self) -> str:
        return f'Device {self.device_id} {self.friendly_name}'

    @command(polling_period=polling_main)
    def get_controller_status(self):
        state_ok = self.check_func_allowance(self.get_controller_status)
        if True:
            res = self.get_controller_status_local()
            self.send_state_archive()
            if res != 0:
                self.error(f'{res}')
            if self.get_state() != DevState.ON and self.always_on == 1:
                self.turn_on()

    @abstractmethod
    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @command
    def turn_on(self):
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok == 1:
            self.info(f"Turning ON {self.device_name}.", True)
            res = self.turn_on_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name} WAS turned ON.", True)
                self.fix_state()
        else:
            self.error(f"Turning ON {self.device_name}, did not work, check state of the device {self.get_state()}.")

    @abstractmethod
    def turn_on_local(self) -> Union[int, str]:
        pass

    @command
    def turn_off(self):
        state_ok = self.check_func_allowance(self.turn_off)
        if state_ok == 1:
            self.info(f"Turning off device {self.device_name}.", True)
            res = self.turn_off_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name} is turned OFF.", True)
                data = self.form_archive_data(0, 'State')
                self.write_to_archive(data)
        else:
            self.error(f"Turning OFF {self.device_name}, did not work, check state of the device {self.get_state()}.")

    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass

    def write_to_archive(self, data: ArchiveData):
        if self.archive.state == 1:
            data_c = self.compress_data(data)
            self.archive.archive_it(data_c)

    def compress_data(self, data):
        msg_b = msgpack.packb(str(data))
        msg_b_c = zlib.compress(msg_b)
        msg_b_c_s = str(msg_b_c)
        return msg_b_c_s

    def form_archive_data(self, data, name: str, time_stamp=None, dt=None):
        if isinstance(data, float):
            if not dt:
                dt = 'float32'
            data_s = Scalar(value=data, dtype=dt)
        elif isinstance(data, int):
            if not dt:
                if data <= 127 and data >= 0:
                    dt = 'uint8'
                elif data >= 0:
                    dt = 'uintc'
                else:
                    dt = 'int'
            data_s = Scalar(value=data, dtype=dt)
        elif isinstance(data, np.ndarray):
            if not dt:
                dt = str(data.dtype)
                data.astype(dt)
            data_s = Array(value=data.tobytes(), shape=data.shape, dtype=dt)

        if not time_stamp:
            time_stamp = time.time()

        archive_data = ArchiveData(tango_device=self.get_name(), data_timestamp=time_stamp,
                                   dataset_name=name, data=data_s)
        return archive_data

    @command(dtype_in=[int,], dtype_out=str, doc_in='Takes an order', doc_out='return name of order')
    def register_order(self, value: int):
        import string
        import random
        s = 20  # number of characters in the string.
        name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=s))
        res = self.register_order_local(name, value)
        return name if res == 0 else '-1, could not register order'

    def register_order_local(self, name, value):
        pass

    @command(dtype_in=str, doc_in='Order name', dtype_out=bool)
    def is_order_ready(self, name):
        res = False
        if name in self.orders:
            order = self.orders[name]
            res = order.order_done
        return res

    @command(dtype_in=str, doc_in='Order name', dtype_out=str)
    def give_order(self, name):
        res = self.give_order_local(name)
        try:
            res = res.tobytes()
        except AttributeError:
            res = str(res).encode('utf-8')
        res = zlib.compress(res)
        return str(res)

    @command(dtype_in=str, doc_in='Order name', dtype_out=int, doc_out='0 if Ok -1 if order is not present in orders')
    def stop_order(self, name):
        order = self.orders[name]
        res = -1
        if name in self.orders:
            order.order_done = True
            res = 0
        return res

    def give_order_local(self, name) -> Any:
        pass
