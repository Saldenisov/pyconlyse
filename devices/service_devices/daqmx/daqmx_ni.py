"""
14/09/2020 DENISOV Sergey
"""
import nidaqmx
from copy import deepcopy
from typing import Dict, Tuple, Union

from devices.devices_dataclass import (HardwareDeviceDict, FuncPowerInput, FuncActivateInput, FuncActivateDeviceInput,
                                       HardwareDevice)
from devices.service_devices.daqmx.daqmx_controller import DAQmxController, DAQmxError
from devices.service_devices.daqmx.daqmx_dataclass import DAQmxCard_NI, DAQmxCard, DAQmxTask, DAQmxTask_NI
from utilities.myfunc import error_logger


class DAQmxCtrl_NI(DAQmxController):
    def __init__(self, **kwargs):
        kwargs['daqmx_dataclass'] = DAQmxCard_NI
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxCard_NI] = HardwareDeviceDict()
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('channel_settings', 'channel_settings', dict)],
                                                          extra_func=[])
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        if not res:
            raise DAQmxError(self, comments)

    def _get_number_hardware_devices(self):
        return len(self.daqmxes)

    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = False, 'Did not work.'
        change = False
        if device.status == 2 and force:
            change = True
        elif device.status == 2 and device.status != flag:
            res, comments = False, f'Cannot set device status to {flag}. Use force option.'
        else:
            change = True

        if change:
            device.status = flag
            res, comments = True, f'DAQmxCard id={device.device_id_seq}, name={device.friendly_name} status is changed ' \
                                  f'to {flag}.'
        return res, comments

    @property
    def daqmxes(self) -> Dict[int, DAQmxCard_NI]:
        return self.daqmxes_without_tasks

    @property
    def daqmxes_without_tasks(self) -> Dict[int, DAQmxCard_NI]:
        return {device_id: device.no_tasks() for device_id, device in self._hardware_devices.items()}

    def _form_devices_list(self) -> Tuple[bool, str]:
        system = nidaqmx.system.System.local()
        for device in system.devices:
            if device.name not in self._hardware_devices:
                del self._hardware_devices[device.name]

        if self.daqmxes:
            res, comments = self._create_tasks()
            self.register_observation('daqmx_channels_observation', self._read_channels)
            return res, comments
        else:
            return False, f'None of NI-DAQmx cards listed in DB are detected on the system.'

    def _create_tasks(self) -> Tuple[bool, str]:
        res, comments = True, ''

        for device in self._hardware_devices.values():
            device: DAQmxCard_NI = device
            if device.channel_settings:
                task_id = 1
                task_dict = {}
                channel_settings = deepcopy(device.channel_settings)
                for physical_address, param in channel_settings.items():
                    task = nidaqmx.task.Task(new_task_name=param[0])
                    if param[1] == 'DigitalOut':
                        task.do_channels.add_do_chan(lines=f'{device.device_id}/{physical_address}',
                                                     line_grouping=nidaqmx.constants.LineGrouping.CHAN_PER_LINE,
                                                     name_to_assign_to_lines=param[0])
                    elif param[1] == 'DigitalIn':
                        task.di_channels.add_di_chan(lines=f'{device.device_id}/{physical_address}',
                                                     line_grouping=nidaqmx.constants.LineGrouping.CHAN_PER_LINE,
                                                     name_to_assign_to_lines=param[0])
                    elif param[1] == 'AICurrent':
                        task.ai_channels.add_ai_current_chan(physical_channel=f'{device.device_id}/{physical_address}',
                                                             name_to_assign_to_channel=param[0])
                    elif param[1] == 'AIVoltage':
                        task.ai_channels.add_ai_voltage_chan(physical_channel=f'{device.device_id}/{physical_address}',
                                                             name_to_assign_to_channel=param[0])
                    elif param[1] == 'CounterInput':
                        task.ci_channels.add_ci_count_edges_chan(counter=f'{device.device_id}/{param[2]}',
                                                                 name_to_assign_to_channel=param[0])
                        task.ci_channels[0].ci_count_edges_term = f'/{device.device_id}/{physical_address}'
                        task.start()
                    else:
                        task = None
                        del device.channel_settings[physical_address]
                    if task:
                        task = DAQmxTask_NI(channel=f'/{device.device_id}/{physical_address}', name=param[0],
                                            task_type=param[1], task_ni=task, value=task.read())
                        task_dict[task_id] = task
                        task_id += 1
                device.tasks = task_dict
        return res, comments

    def _read_channels(self):
        for device in self._hardware_devices.values():
            device: DAQmxCard_NI = device
            for task in device.tasks.values():
                task_ni: DAQmxTask_NI = task.task_ni
                task.value = task_ni.read()

    def _release_hardware(self) -> Tuple[bool, str]:
        res, comments = True, ''
        for daqmx in self._hardware_devices.values():
            try:
                for task in daqmx.tasks.values():
                    if task:
                        task.task_ni.close()
                        task = None
            except nidaqmx.DaqError as e:
                error_logger(self, self._release_hardware, e)
                comments = f'{e}'
            finally:
                self.unregister_observation('daqmx_channels_observation')
                daqmx.tasks = {}
            return True, comments

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        results, comments = [], ''
        
        return all(results), comments
