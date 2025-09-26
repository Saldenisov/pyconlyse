from collections import OrderedDict

from tango import AttrWriteType, DevFloat, DispLevel
from tango.server import attribute, device_property

try:
    from DeviceServers.base.general import DS_General
except ModuleNotFoundError:
    # Fallback for when not imported from root
    import sys
    from pathlib import Path

    app_folder = Path(__file__).resolve().parents[3]  # Go to pyconlyse root
    sys.path.append(str(app_folder))
    from DeviceServers.base.general import DS_General


class DS_ControlPosition(DS_General):
    RULES = {**DS_General.RULES}
    ds_dict = device_property(dtype=str)
    controller_rules = device_property(dtype=str)
    groups = device_property(dtype=str)
    pid_groups = device_property(dtype=str)

    def init_device(self):
        self.control_position = [0, 0]
        super().init_device()

        # Create safe globals for eval with necessary imports
        eval_globals = {
            "__builtins__": {},
            "OrderedDict": OrderedDict,
            "dict": dict,
            "list": list,
            "tuple": tuple,
        }

        self.ds_dict = eval(self.ds_dict, eval_globals)
        self.controller_rules = eval(self.controller_rules, eval_globals)
        self.groups = eval(self.groups, eval_globals)
        self.pid_groups = eval(self.pid_groups, eval_globals)
        self.devices = {}

    @attribute(
        label="Rules for controller",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def get_rules(self):
        return str(self.controller_rules)

    @attribute(
        label="DS used by controller",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def get_ds_dict(self):
        return str(self.ds_dict)

    @attribute(
        label="Groups of DS used by controller",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def get_groups(self):
        return str(self.groups)

    @attribute(
        label="Rules of DS used by controller",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def get_controller_rules(self):
        return str(self.controller_rules)

    @attribute(
        label="Laser position",
        dtype=(DevFloat,),
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        max_dim_x=2,
    )
    def control_position(self):
        return self.control_position

    def write_control_position(self, value):
        self.control_position = value

