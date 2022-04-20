from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState, DevFloat
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any
from collections import OrderedDict


from DeviceServers.General.DS_general import DS_General, standard_str_output


class DS_ControlPosition(DS_General):
    RULES = {**DS_General.RULES}
    ds_dict = device_property(dtype=str)
    controller_rules = device_property(dtype=str)
    groups = device_property(dtype=str)
    pid_groups = device_property(dtype=str)

    def init_device(self):
        self.control_position = [0, 0]
        super().init_device()
        self.ds_dict = eval(self.ds_dict)
        self.controller_rules = eval(self.controller_rules)
        self.groups = eval(self.groups)
        self.pid_groups = eval(self.pid_groups)
        self.devices = {}


    @attribute(label="Rules for controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_rules(self):
        return str(self.controller_rules)

    @attribute(label="DS used by controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_ds_dict(self):
        return str(self.ds_dict)

    @attribute(label="Groups of DS used by controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_groups(self):
        return str(self.groups)

    @attribute(label="Rules of DS used by controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_rules(self):
        return str(self.controller_rules)

    @attribute(label="Laser position", dtype=(DevFloat,), display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ_WRITE, max_dim_x=2)
    def control_position(self):
        self.control_position

    def write_control_position(self, value):
        self.control_position = value
