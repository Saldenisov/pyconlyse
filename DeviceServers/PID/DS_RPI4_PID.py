#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import cv2
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union


import numpy as np
from DeviceServers.General.DS_PID import DS_PID
from DeviceServers.General.DS_general import standard_str_output
from collections import OrderedDict
# -----------------------------

from tango.server import device_property, command, attribute
from tango import DevState, AttrWriteType
from pypylon import pylon, genicam
from threading import Thread


class DS_RPI4_PID(DS_PID):

    _version_ = '0.1'
    _model_ = 'RPI4 PID MAX31865'

    def find_device(self):
        pass

    def get_controller_status_local(self) -> Union[int, str]:
        pass

    def turn_on_local(self) -> Union[int, str]:
        pass

    def turn_off_local(self) -> Union[int, str]:
        pass

    def read_temperature_local(self):
        pass

    def pid_action_local(self):
        pass


if __name__ == "__main__":
    DS_RPI4_PID.run_server()