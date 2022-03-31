from abc import abstractmethod

from tango import DispLevel, DevState
from tango.server import attribute, command, device_property, AttrWriteType
from typing import Union, List
from threading import Thread
from DeviceServers.General.DS_general import DS_General
from time import sleep

class DS_PID(DS_General):
    """
    bla-bla
    """
    RULES = {'set_temperature': [DevState.ON, DevState.STANDBY],
             'turn_on_PID': [DevState.ON, DevState.STANDBY], 'turn_off_PID': [DevState.ON, DevState.STANDBY],
             **DS_General.RULES
             }
    ip_address = device_property(dtype=str)
    temp_polling = device_property(dtype=int)
    pid_polling = device_property(dtype=int)

    @attribute(label="temperature", dtype=float, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ, polling_period=500, abs_change='1')
    def temperature(self):
        return self._temperature

    def init_device(self):
        self._temperature = 0
        self._set_temperature = 0
        self.pid_active = False
        self.temperature_thread = Thread(target=self.read_temperature)
        self.pid_thread = Thread(target=self.pid_action)
        super().init_device()
        self.temperature_thread.start()
        self.pid_thread.start()

    @command(dtype_in=float)
    def set_temperature(self, value):
        self._set_temperature = value

    @command
    def turn_on_PID(self):
        self.pid_active = True

    @command
    def turn_off_PID(self):
        self.pid_active = False

    @abstractmethod
    def read_temperature_local(self):
        pass

    def read_temperature(self):
        while True:
            self.read_temperature_local()
            sleep(self.temp_polling / 1000)

    @abstractmethod
    def pid_action_local(self):
        pass

    def pid_action(self):
        while True:
            if self.pid_active:
                self.pid_action_local()
            sleep(self.pid_polling / 1000)