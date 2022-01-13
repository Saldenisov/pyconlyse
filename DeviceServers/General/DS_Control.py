from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState, DevFloat
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any
from collections import OrderedDict


from DeviceServers.General.DS_general import DS_General, standard_str_output


class DS_ControlPosition(DS_General):

    ds_dict = device_property(dtype=str)
    rules = device_property(dtype=str)
    groups = device_property(dtype=str)

    def init_device(self):
        super().init_device()
        self.control_position = [0, 0]
        self.ds_dict = eval(self.ds_dict)
        self.rules = eval(self.rules)
        self.groups = eval(self.groups)
        self._device_id_internal = -1
        self._device_id_internal, self._uri = self.find_device()
        if self._device_id_internal >= 0:
            self.info(f"Device {self.device_name} was found.", True)
            self.set_state(DevState.OFF)
        else:
            self.info(f"Device {self.device_name} was NOT found.", True)
            self.set_state(DevState.FAULT)

    @abstractmethod
    def calc_correction(self, args):
        pass

    @attribute(label="Rules for controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_rules(self):
        return str(self.rules)

    @attribute(label="DS used by controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_ds_dict(self):
        return str(self.ds_dict)

    @attribute(label="Groups of DS used by controller", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def get_groups(self):
        return str(self.groups)

    @attribute(label="Laser position", dtype=(DevFloat,), display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ_WRITE, max_dim_x=2)
    def control_position(self):
        self.control_position

    def write_control_position(self, value):
        self.control_position = value


