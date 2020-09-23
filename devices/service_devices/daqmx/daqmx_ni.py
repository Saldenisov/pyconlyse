"""
14/09/2020 DENISOV Sergey
"""
import nidaqmx
from typing import Dict, Tuple, Union
from devices.devices_dataclass import (HardwareDeviceDict, FuncPowerInput, FuncActivateInput, FuncActivateDeviceInput)
from devices.service_devices.daqmx.daqmx_controller import DAQmxController, DAQmxError
from devices.service_devices.daqmx.daqmx_dataclass import NIDAQmxCard
from utilities.myfunc import error_logger


class DAQmxCtrl_NI(DAQmxController):
    def __init__(self, **kwargs):
        kwargs['daqmx_dataclass'] = NIDAQmxCard
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxCtrl_NI] = HardwareDeviceDict()
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('сhannel_settings', 'сhannel_settings', dict)],
                                                          extra_func=[])
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        if not res:
            raise DAQmxError(self, comments)
        else:
            self.activation()

    def _get_number_hardware_devices(self):
        return len(self.daqmxes)

    def _change_device_status(device_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
        return False, 'not realized'

    def _form_devices_list(self) -> Tuple[bool, str]:
        system = nidaqmx.system.System.local()
        for device in system.devices:
            if device.name not in self.daqmxes:
                del self.daqmxes[device.name]

        if self.daqmxes:
            return True, ''
        else:
            return False, f'None of NI-DAQmx cards listed in DB are detected on the system.'

    def _release_hardware(self) -> Tuple[bool, str]:
        res, comments = True, ''
        try:
            for daqmx in self.daqmxes.values():
                for task in daqmx.tasks:
                    if task:
                        task.close()
        except nidaqmx.DaqError as e:
            error_logger(self, self._release_hardware, e)
            comments = f'{e}'
        finally:
            return True, comments
