#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import cv2
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union, List
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import LED
import numpy as np
from DeviceServers.General.DS_GPIO import DS_GPIO
from DeviceServers.General.DS_general import standard_str_output
from collections import OrderedDict
# -----------------------------

from tango.server import device_property, command, attribute
from tango import DevState, AttrWriteType
from pypylon import pylon, genicam
from threading import Thread


import platform    # For getting the operating system name
import subprocess  # For executing a shell command

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of
    param = '-n' if platform.system().lower()=='windows' else '-c'

    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]

    return subprocess.call(command) == 0



class DS_RPI_GPIO(DS_GPIO):
    _version_ = '0.1'
    _model_ = 'RPI GPIO controller'

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            if ping(self.ip_address):
                self.set_state(DevState.INIT)
                self._device_id_internal, self._uri = self.device_id, self.friendly_name.encode('utf-8')
                self.factory = PiGPIOFactory(host=self.ip_address)
                for pins_param in self.parameters:
                    pin_type = eval(pins_param[1]())
                    control_pin = pin_type(pins_param[0], pin_factory=self.factory)
                    self.pins[f'{pins_param[2]}_{pins_param[0]}'] = control_pin
            else:
                self._device_id_internal, self._uri = argreturn

    def get_pins_states(self) -> Union[int, str]:
        states = []
        for pin in self.pins.keys():
            control_pin = self.pins[pin][0]
            states.append(control_pin.value)
        self._states = states

    def set_pin_state_local(self, pins_values: List[int]) -> Union[int, str]:
        pin_id = pins_values[0]
        pin_value = int(pins_values[1])
        if pin_id in self.pins:
            if pin_value >= 1:
                self.pins[pin_id].on()
            elif pin_value <= 0:
                self.pins[pin_id].off()
            return 0
        else:
            return f'Wrong pin id {pin_id} was given.'

    def get_controller_status_local(self) -> Union[int, str]:
        if ping(self.ip_address):
            self.set_state(DevState.ON)
            self.get_pins_states_local()
            return 0
        else:
            self.set_state(DevState.FAULT)
            return f'Could not turn on, RPI {self.ip_address} is away...'

    def turn_on_local(self) -> Union[int, str]:
        if ping(self.ip_address):
            self.set_state(DevState.ON)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return f'Could not turn on, RPI {self.ip_address} is away...'

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)