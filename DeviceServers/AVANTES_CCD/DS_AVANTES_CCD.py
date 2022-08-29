#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union, List, Dict
from time import time_ns, time, sleep
import ctypes
import inspect
from threading import Thread
import numpy as np
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD, OrderInfo
from DeviceServers.General.DS_general import standard_str_output
from utilities.tools.decorators import dll_lock
# -----------------------------
from msl.equipment.exceptions import AvantesError
from tango.server import device_property, command, attribute, AttrWriteType
from tango import DevState, DevFloat

import requests



from msl.equipment import (
    EquipmentRecord,
    ConnectionRecord,
    Backend,
)

class DS_AVANTES_CCD(DS_CAMERA_CCD):
    RULES = {**DS_CAMERA_CCD.RULES}

    _version_ = '0.1'
    _model_ = 'AVANTES_CCD CCD'

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path = device_property(dtype=str)
    width = device_property(dtype=int)
    wavelengths = device_property(dtype=str)
    arduino_sync = device_property(dtype=str, default_value='10.20.30.47')

    def init_device(self):
        self.serial_number_real = -1
        self.head_name = ''
        self.status_real = 0
        self.exposure_time_local = -1
        self.accumulate_time_local = -1
        self.kinetic_time_local = -1
        self.n_gains_max = 1
        self.gain_value = -1
        self.height_value = 1
        self.grabbing_thread: Thread = None
        self.abort = False
        self.n_kinetics = 1
        self.camera = None
        self.BG_level_value = 0
        self.integration_delay_value = 0
        self.integration_time_value = 0.05
        self.trigger_type_value = 0
        self.trigger_source_value = 0
        self.trigger_mode_value = 0

        super().init_device()
        self.register_variables_for_archive()
        if self.camera:
            self.wavelengths = self.camera.get_lambda()
            self.width = self.camera.get_num_pixels()
        else:
            self.wavelengths = eval(self.wavelengths)

        self._arduino_addr_on = f'http://{self.arduino_sync}/?status=ON'
        self._arduino_addr_off = f'http://{self.arduino_sync}/?status=OFF'

    @attribute(label='number of kinetics', dtype=int, access=AttrWriteType.READ_WRITE)
    def number_kinetics(self):
        return self.n_kinetics

    def write_number_kinetics(self, value: int):
       self.n_kinetics = value

    def _connect(self):
        try:
            self.camera = self.record.connect(demo=False)
        except (Exception, AvantesError) as e:
            pass

    def find_device(self) -> Tuple[int, str]:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.record = EquipmentRecord(manufacturer='Avantes',
                                          model='AvaSpec-2048L',
                                          serial=self.device_id,
                                          connection=ConnectionRecord(
                                              address=f'SDK::{self.dll_path}',  # update the path to the DLL file
                                              backend=Backend.MSL))

            self._connect()

            if self.camera:
                self.camera.use_high_res_adc(True)
                self.set_state(DevState.ON)
                argreturn = 1, str(self.serial_number_real).encode('utf-8')
            else:
                self.error(f'Could not initialize camera.')
            self._device_id_internal, self._uri = argreturn

    def get_camera_friendly_name(self):
        return self.friendly_name

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)

    def get_camera_serial_number(self) -> Union[str, int]:
        return self.device_id

    def get_camera_model_name(self) -> str:
        self._GetHeadModel()
        return self.head_name

    def get_exposure_time(self) -> float:
        res = self._GetAcquisitionTimings()
        if res:
            self.info(f'Get exposure time worked', True)
        else:
            self.info(f'Get exposure time did not work: {res}', True)
        return self.exposure_time_local

    def set_exposure_time(self, value: float):
        restart = False
        self.info(f'Setting exposure time {value}', True)
        if self.grabbing:
            self.stop_grabbing()
            restart = True
        res = self._SetExposureTime(value)
        if res:
            self.info(f'Exposure time was set to {value}', True)
        else:
            self.info(f'Exposure time was not set to {value}: {res}', True)

        if restart:
            self.start_grabbing()

    def set_trigger_delay(self, value: str):
        self._SetIntegrationDelay(float(value))

    def get_trigger_delay(self) -> str:
        return str(self.trigger_delay_value)

    def get_exposure_min(self):
        return 0.00001

    def get_exposure_max(self):
        return

    def set_gain(self, value: int):
        pass

    def get_gain(self) -> int:
        return self.gain_value

    def get_gain_min(self) -> int:
        return 0

    def get_gain_max(self) -> int:
        self._GetNumberPreAmpGains()
        return self.n_gains_max

    def get_width(self) -> int:
        return self.width

    def set_width(self, value: int):
        pass

    def get_width_min(self):
        return self.width

    def get_width_max(self):
        return self.width

    def set_height(self, value: int):
        pass

    def get_height(self) -> int:
        return self.height_value

    def get_height_min(self):
        return 1

    def get_height_max(self):
        return self.height_value

    def get_offsetX(self) -> int:
        return -1

    def set_offsetX(self, value: int):
        pass

    def get_offsetY(self) -> int:
        return -1

    def set_offsetY(self, value: int):
        pass

    def set_format_pixel(self, value: str):
        pass

    def get_format_pixel(self) -> str:
        return 'None'

    def get_framerate(self):
        return -1

    def set_binning_horizontal(self, value: int):
        pass

    def get_binning_horizontal(self) -> int:
        return -1

    def set_binning_vertical(self, value: int):
        pass

    def get_binning_vertical(self) -> int:
        return -1

    def get_sensor_readout_mode(self) -> str:
        return 'None'

    def turn_on_local(self) -> Union[int, str]:
        if self.get_state != DevState.ON:
            self._connect()
            if self.camera:
                self.info(f"{self.device_name} was Opened.", True)
                self.set_state(DevState.ON)
                return 0
            else:
                self.info(f'Could not turn on camera, because it does not exist.', True)
                return f'Could not turn on camera, because it does not exist.'
        else:
            return f'Could not turn on camera it is opened already.'

    def turn_off_local(self) -> Union[int, str]:
        if self.grabbing:
            self.stop_grabbing_local()
        self.camera.disconnect()
        self.camera = None
        self.set_state(DevState.OFF)
        self.info(f"{self.device_name} was Closed.", True)
        return 0

    def set_param_after_init_local(self) -> Union[int, str]:
        functions = [self.set_acquisition_controls]
        results = []
        for func in functions:
            results.append(func())
        results_s = ''
        for res in results:
            if res != 0:
                results_s = results_s + res
        return results_s if results_s else 0

    def set_acquisition_controls(self):
        formed_parameters_dict = self.parameters['Acquisition_Controls']
        return self._set_parameters(formed_parameters_dict)

    def _set_parameters(self, formed_parameters_dict):
        if self.get_state() == DevState.ON:
            if self.grabbing:
                self.stop_grabbing()
            for param_name, param_value in formed_parameters_dict.items():
                func = getattr(self, f'_Set{param_name}')
                if isinstance(param_value, tuple) or isinstance(param_value, list):
                    res = func(*list(param_value))
                else:
                    res = func(param_value)
                if res != True:
                    return f'Error appeared: {res} when setting parameter "{param_name}" for camera {self.device_name}.'
            return 0
        else:
            return f'{self.device_name} state is {self.get_state()}.'

    def get_image(self):
        if self.abort:
            self.start_grabbing()

    def wait(self, timeout=0):
        try:
            self.status_real = 1
            while self.abort is not True and self.camera:
                a = time()
                cfg = self.camera.MeasConfigType()
                cfg.m_StopPixel = self.width - 1
                cfg.m_IntegrationTime = self.integration_time_value  # in milliseconds
                cfg.m_NrAverages = 1  # number of averages
                m_Trigger = self.camera.TriggerType()
                m_Trigger.m_Mode = self.trigger_mode_value
                m_Trigger.m_Source = self.trigger_source_value
                m_Trigger.m_SourceType = self.trigger_type_value
                cfg.m_Trigger = m_Trigger
                self.camera.prepare_measure(cfg)

                # start 1 measurement, wait until the measurement is finished, then get the data
                self.camera.measure(1)
                finished = True
                i = 0
                while not self.camera.poll_scan():
                    sleep(0.01)
                    i += 1
                    if i > 100:
                        finished = False
                        break
                if finished:
                    tick_count, data = self.camera.get_data()
                else:
                    data = None

                if isinstance(data, np.ndarray):
                    data2D = np.reshape(data, (-1, self.width))
                    data2D.astype('int16')
                    self.treat_orders(data2D)
                    self.info('Image is received...')
                else:
                    self.error('Did not measure, just sending you zeros.')
                    data2D = np.zeros(self.width * self.n_kinetics).reshape(-1, self.width)
                self.last_image = data2D
                b = time()
                self.info(f'Time passed: {b - a}')
        except Exception as e:
            self.error(e)
        finally:
            self.status_real = 0

    def get_controller_status_local(self) -> Union[int, str]:
        res = self._GetStatus()
        if res == True:
            r = 0
            if self.status_real == 20073:
                self.set_state(DevState.ON)
            elif self.status_real == 20072:
                self.set_state(DevState.RUNNING)
            else:
                self.set_state(DevState.UNKNOWN)
        else:
            self.set_state(DevState.FAULT)
            r = res
        return r

    def start_grabbing_local(self):
        sleep(0.5)
        if not self.grabbing:
            requests.get(url=self._arduino_addr_on)
            self.abort = False
            self.grabbing_thread = Thread(target=self.wait, args=[self.timeoutt])
            self.grabbing_thread.start()
        return 0

    def stop_grabbing_local(self):
        self.abort = True
        requests.get(url=self._arduino_addr_off)
        return 0

    def grabbing_local(self):
        res = False
        if self.camera:
            if self.status_real == 1:
                res = True
        return res

    def set_trigger_mode(self, state):
        self._SetTriggerMode(state)

    def get_trigger_mode(self) -> int:
        return self.trigger_mode_value

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def _SetTriggerMode(self, state):
        self.trigger_mode_value = state
        return True

    def _SetTriggerSource(self, state):
        self.trigger_source_value = state
        return True

    def _SetTriggerType(self, state):
        self.trigger_type_value = state
        return True

    def _SetIntegrationTime(self, value):
        self.integration_time_value = value
        return True

    def _SetIntegrationDelay(self, value):
        self.integration_delay_value = value
        return True

    def _SetBGLevel(self, value):
        self.BG_level_value = value
        return True


if __name__ == "__main__":
    DS_AVANTES_CCD.run_server()
    # Andor_test()