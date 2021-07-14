import time
import numpy

from abc import abstractmethod
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.test_context import DeviceTestContext, DeviceProxy
from tango.server import Device, attribute, command, pipe, device_property

from typing import Dict, Tuple
from pathlib import Path
from time import sleep


class DS_Motor(Device):
    """"
    Device Server (Tango) general class for motors
    """
    POWER_STATES = {0: 'PWR_UNKNOWN', 1: 'PWR_OFF', 3: 'PWR_NORM', 4: 'PWR_REDUCED',5: 'PWR_MAX'}


    @attribute(label="Position", unit="step", dtype=float)
    def position(self):
        pass

    @command(polling_period=100)
    def get_controller_status(self):
        pass
