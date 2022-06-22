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
from functools import partial
from tango.server import device_property, command, attribute
from tango import DevState, AttrWriteType
from pypylon import pylon, genicam
from threading import Thread
from time import sleep

from utilities.myfunc import ping


class DS_RPI_GPIO(DS_GPIO):
    _version_ = '0.1'
    _model_ = 'RPI GPIO controller'
    RULES = {**DS_GPIO.RULES}

    def init_device(self):
        super().init_device()
        self.turn_on()
        self.register_variables_for_archive()
        self.get_pins_states()

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            if ping(self.ip_address):
                self.set_state(DevState.INIT)
                self._device_id_internal, self._uri = int(self.device_id), self.friendly_name.encode('utf-8')
                self.factory = PiGPIOFactory(host=self.ip_address)
                states = []
                for pins_param in self.parameters['Pins']:
                    pin_type = eval(pins_param[1])  # Led or Button
                    control_pin = pin_type(pins_param[0], pin_factory=self.factory)  # Make object of pin using factory
                    self.pins[pins_param[0]] = control_pin
                    self.set_pin_state_local([pins_param[0], pins_param[3]])
                    states.append(control_pin.value)
                self._states = states
            else:
                self._device_id_internal, self._uri = argreturn

    def get_pins_states(self):
        states = []
        for pin in self._pin_ids:
            control_pin = self.pins[pin]
            value = control_pin.value
            states.append(value)
        self._states = states

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        extra = {}
        for pin in self._pin_ids:
            archive_key = f'pin_state_{pin}'
            extra[archive_key] = (partial(self.value_from_pin, pin), 'uint8')
        self.archive_state.update(extra)

    def value_from_pin(self, pin_id: int):
        control_pin = self.pins[pin_id]
        return control_pin.value

    def get_pin_state_local(self, pin_id: int) -> Union[int, str]:
        if pin_id in self.pins:
            value = self.pins[pin_id].value
            return value
        else:
            return f'Wrong pin id {pin_id} was given.'

    def set_pin_state_local(self, pin_id_value: List[int]) -> Union[int, str]:
        pin_id = pin_id_value[0]
        pin_value = int(pin_id_value[1])
        if pin_id in self.pins:
            if pin_value >= 1:
                self.pins[pin_id].on()
            elif pin_value <= 0:
                self.pins[pin_id].off()
            return 0
        else:
            return f'Wrong pin id {pin_id} was given.'

    def generate_TTL(self, pin: int, dt: int, time_delay: int):
        # self.pins[pin].on()
        # sleep(dt / 10**6)
        # self.pins[pin].off()
        # sleep(time_delay / 10**6)
        self.pins[pin].toggle()

    def get_controller_status_local(self) -> Union[int, str]:
        res = DS_GPIO.check_ip(self.ip_address)
        if res:
            self.set_state(DevState.ON)
            self.get_pins_states()
            return 0
        else:
            self.turn_on_local()
            res = DS_GPIO.check_ip(self.ip_address)
            if res:
                self.set_state(DevState.ON)
                self.get_pins_states()
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


if __name__ == "__main__":
    DS_RPI_GPIO.run_server()
