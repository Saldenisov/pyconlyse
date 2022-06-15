#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import requests
import telnetlib

from typing import Tuple, Union,  List
from pathlib import Path
import time
import  re
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute


from DeviceServers.General.DS_GPIO import DS_GPIO

import platform    # For getting the operating system name
import subprocess  # For executing a shell command

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of
    param = '-n' if platform.system().lower() == 'windows' else '-c'

    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]

    return subprocess.call(command, stdout=subprocess.DEVNULL) == 0


class DS_Numato_GPIO(DS_GPIO):
    """
    Device Server (Tango) which controls the NUMATO pdu using JSON API.
    """
    _version_ = '0.1'
    _model_ = 'NUMATO_GPIO'
    polling = 500

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        self._device_id_internal, self._uri = -1, b''
        if state_ok:
            if ping(self.ip_address):
                if self.turn_on_local() == 1:
                    self.set_state(DevState.INIT)
                    self._device_id_internal, self._uri = int(self.device_id), self.friendly_name.encode('utf-8')
                    states = []
                    for pins_param in self.parameters['Pins']:
                        self.gpio_set(pins_param[0], pins_param[3])

    def turn_on_local(self) -> Union[int, str]:
        # Wait for login prompt from device and enter user name when prompted
        self.telnet_obj = telnetlib.Telnet(self.ip_address)
        self.telnet_obj.read_until(b"login")
        self.telnet_obj.write(self.authentication_name.encode('ascii') + b"\r\n")

        # Wait for password prompt and enter password when prompted by device
        self.telnet_obj.read_until(b"Password: ")
        self.telnet_obj.write(self.authentication_password.encode('ascii') + b"\r\n")

        # Wait for device response
        log_result = self.telnet_obj.read_until(b"successfully\r\n")
        self.telnet_obj.read_until(b">")

        # Check if login attempt was successful
        if b"successfully" in log_result:
            return 1
        elif "denied" in log_result:
            return log_result

    @staticmethod
    def _int_to_hex(gpio_pin:int):
        return str(hex(gpio_pin)[2:]).upper()

    def set_pin_state_local(self, gpio_pin: int, value: int) -> Union[int, str]:
        gpio_pin = DS_Numato_GPIO._int_to_hex(gpio_pin)
        if value:
            self.telnet_obj.write(("gpio set " + str(gpio_pin) + "\r\n").encode())
        else:
            self.telnet_obj.write(("gpio clear " + str(gpio_pin) + "\r\n").encode())

        self.info(f"GPIO {gpio_pin} was set to {value}", True)
        time.sleep(0.5)
        self.telnet_obj.read_eager()
        # TODO: return


    def get_pin_state_local(self, gpio_pin: int) -> Union[int, str]:
        gpio_pin = DS_Numato_GPIO._int_to_hex(gpio_pin)
        self.telnet_obj.write(b"gpio read " + str(gpio_pin).encode("ascii") + b"\r\n")
        time.sleep(0.5)
        response = self.telnet_obj.read_eager()
        result = int(re.split(br'[&>]', response)[0].decode())
        self.info(f'GPIO pin {gpio_pin} is set to {result}')
        return result

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def check_ip(self):
        return ping(self.ip_address)

    def get_controller_status_local(self) -> Union[int, str]:
        res = self.check_ip()
        if res and self.telnet_obj:
            self.set_state(DevState.ON)
            return 0
        else:
            self.turn_on_local()
            res = self.check_ip()
            if res:
                self.set_state(DevState.ON)
                return 0
            else:
                self.set_state(DevState.FAULT)
                return f'Could not turn on, Numato {self.ip_address} is away...'


if __name__ == "__main__":
    DS_Numato_GPIO.run_server()