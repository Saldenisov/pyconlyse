import sys
import requests

from typing import Tuple, Union,  List
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute
from collections import OrderedDict

try:
    from DeviceServers.General.DS_Control import DS_ControlPosition
except ModuleNotFoundError:
    from General.DS_Control import DS_ControlPostion


class DS_LaserPointing(DS_ControlPosition):
    RULES = {'set_param_after_init': [DevState.ON], 'start_grabbing': [DevState.ON],
             'stop_grabbing': [DevState.ON],
             **DS_ControlPosition.RULES}
    """
    Device Server (Tango) which controls laser pointing.
    """
    _version_ = '0.1'
    _model_ = 'LaserPoiting Controller'
    polling = 500

    def calc_correction(self, args):
        pass

    def init_device(self):
        super().init_device()
        self.turn_on()

    def find_device(self):
        argreturn = self.server_id, self.device_id
        self._device_id_internal, self._uri = argreturn

    def get_controller_status_local(self) -> Union[int, str]:
        return super().get_controller_status_local()

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
    DS_LaserPointing.run_server()
