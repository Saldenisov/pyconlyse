"""
14/09/2020 DENISOV Sergey
"""
import nidaqmx
from devices.service_devices.daqmx.daqmx_controller import DAQmxController, DAQmxError
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.myfunc import error_logger, info_msg, join_smart_comments



class DAQmxCtrl_NI(DAQmxController):
    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxCtrl_NI] = HardwareDeviceDict()

    def _get_number_hardware_devices(self):
        return len(self.daqmxes)

    def _change_device_status(device_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
        return False, 'not realized'

    def _form_devices_list(self) -> Tuple[bool, str]:
        system = nidaqmx.system.System.local()












