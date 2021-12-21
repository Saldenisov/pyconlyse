from abc import abstractmethod

from tango import AttrQuality, AttrWriteType, DispLevel, DevState, InfoIt, PipeWriteType, Pipe
from tango.server import Device, attribute, command, pipe, device_property
from typing import Tuple, Union, List
from threading import Thread
from time import sleep


standard_str_output = 'str: 0 if success, else error.'


class DS_General(Device):
    device_id = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    server_id = device_property(dtype=int)
    polling_main = 500
    RULES = {'turn_on': [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
             'turn_off': [DevState.ON, DevState.STANDBY, DevState.INIT],
             'find_device': [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
             'get_controller_status': [DevState.ON, DevState.MOVING, DevState.INIT]}

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
               doc="Last essential comment.", polling_period=polling_main)
    def last_comments(self):
        return self._comments

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
        Device.init_device(self)
        self.set_state(DevState.OFF)
        self._device_id_internal = -1
        device_id_internal, uri = self.find_device()
        self._uri = uri
        self._device_id_internal = device_id_internal

        if self._device_id_internal >= 0:
            self.info(f"{self.device_name} was found.", True)
        else:
            self.info(f"{self.device_name} was NOT found.", True)
            self.set_state(DevState.FAULT)

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

    @property
    def device_name(self) -> str:
        return f'Device {self.device_id} {self.friendly_name}'

    @command(polling_period=polling_main)
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
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok == 1:
            self.info(f"Turning ON {self.device_name}.", True)
            res = self.turn_on_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name} WAS turned ON.", True)
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
        else:
            self.error(f"Turning OFF {self.device_name}, did not work, check state of the device {self.get_state()}.")


    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass


