#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import ctypes

from typing import Tuple, Union
import random
from time import sleep
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property

from DeviceServers.General.DS_general import DS_General, standard_str_output



class DS_Test(DS_General):
    """"
    Device Server (Tango) which controls the Standa motorized equipment using libximc.dll
    """
    _version_ = '0.1'
    _model_ = 'test'
    polling_local = 600
    unit = device_property(dtype=str)

    test_attr = attribute(label="test", dtype=float, display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ_WRITE,
                          polling_period=polling_local, abs_change=0.001)

    def test_archiving(self):
        while True:
            val = random.randint(0, 100)
            arch_data = self.form_acrhive_data(val, 'test')
            self.write_to_archive(arch_data)
            sleep(1)

    def read_test_attr(self):
        return self.test_value

    def write_test_attr(self, value):
        self.test_value = value

    def init_device(self):
        self.test_value = 0
        super(DS_Test, self).init_device()
        attr_prop = self.test_attr.get_properties()
        attr_prop.unit = self.unit
        self.test_attr.set_properties(attr_prop)
        self.set_state(DevState.INIT)
        from threading import Thread
        self.archiving = Thread(target=self.test_archiving)
        self.archiving.start()

    def find_device(self) -> Tuple[int, str]:
        self._device_id_internal = 123456789
        self._uri = b'test_device_id'

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
    DS_Test.run_server()
