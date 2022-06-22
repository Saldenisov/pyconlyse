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
from functools import partial

from DeviceServers.General.DS_GPIO import DS_GPIO

from utilities.myfunc import ping
from DeviceServers.NUMATO.DS_Numato_GPIO import DS_Numato_GPIO

class DS_Numato_Relay(DS_Numato_GPIO):
    _version_ = '0.1'
    _model_ = 'NUMATO_Relay'

    def set_pin_state_local(self, pin_id_value: List[int]) -> Union[int, str]:
        gpio_pin = pin_id_value[0]
        value = pin_id_value[1]
        gpio_pin = DS_Numato_GPIO._int_to_numato_numbering(gpio_pin)
        if value:
            self.telnet_obj.write(b"relay on " + str(gpio_pin).encode("ascii") + b"\r\n")
        else:
            self.telnet_obj.write(b"relay off " + str(gpio_pin).encode("ascii") + b"\r\n")

        self.info(f"Relay {gpio_pin} was set to {value}", True)
        time.sleep(self.telnet_wait)
        res = self.telnet_obj.read_eager()
        return 0

    def get_pin_state_local(self, gpio_pin: int) -> Union[int, str]:
        gpio_pin = DS_Numato_GPIO._int_to_numato_numbering(gpio_pin)
        self.telnet_obj.write(b"relay read " + str(gpio_pin).encode("ascii") + b"\r\n")
        time.sleep(self.telnet_wait)
        response = self.telnet_obj.read_eager()
        result = int(re.split(br'[&>]', response)[0].decode())
        self.info(f'Relay {gpio_pin} is set to {result}')
        return result


if __name__ == "__main__":
    DS_Numato_Relay.run_server()
