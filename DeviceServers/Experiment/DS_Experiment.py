from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, List

from DeviceServers.General.DS_general import DS_General, GeneralOrderInfo
from utilities.myfunc import ping
from dataclasses import dataclass
from typing import Dict

@dataclass
class OrderPulsesInfo(GeneralOrderInfo):
    pin: int
    number_of_pulses: int
    dt: int  # in us
    time_delay: int  # in us
    order_done: bool
    ready_to_delete: bool
    pulses_done: int


class DS_Experiment(DS_General):
    """
    Gives control to pulse and 3P epxeriment
    """
    RULES = {**DS_General.RULES}

    _version_ = '0.1'
    _model_ = 'Experiment ds'
    polling = 500

    authentication_name = device_property(dtype=str, default_value='admin')
    authentication_password = device_property(dtype=str, default_value='admin')

    def init_device(self):
        super().init_device()
        self.turn_on()

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        arg_return = -1, ''
        self.info(f"Searching for Experiment device {self.device_name}", True)
        self._device_id_internal, self._uri = self.device_id, self.friendly_name.encode('utf-8')

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

if __name__ == "__main__":
    DS_Experiment.run_server()
