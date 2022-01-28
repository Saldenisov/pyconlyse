#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys

from pathlib import Path
from typing import Union, Tuple

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))
from tango import AttrWriteType, DispLevel, DevState
from threading import Thread
from time import sleep
try:
    from DeviceServers.General.DS_Sync import DS_SYNC_GENERAL
except ModuleNotFoundError:
    from General.General.DS_Sync import DS_SYNC_GENERAL


class DS_Synchronizer(DS_SYNC_GENERAL):

    _version_ = '0.1'
    _model_ = 'Syncronizer'
    polling_local = 25

    def init_device(self):
        super().init_device()
        self.turn_on()
        self.t = Thread(target=self.increament)
        self.t.start()

    def increament(self):
        while True:
            sleep(0.250)
            self.sync_impulse += 1

    def find_device(self) -> Tuple[int, str]:
        arg_return = 1, 'qwerty'
        self.info(f"Searching for SYNC device {self.device_name}", True)
        return arg_return

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
    DS_Synchronizer.run_server()
