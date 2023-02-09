#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
import zlib
from pathlib import Path
import random
import string
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union, List, Dict, Any
from time import time_ns, time, sleep
import ctypes
import inspect
from threading import Thread
import numpy as np
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output, DS_General
from collections import OrderedDict, deque
from utilities.tools.decorators import dll_lock
# -----------------------------

from tango.server import device_property, command, attribute, AttrWriteType
from tango import DevState, DevFloat
from dataclasses import dataclass


@dataclass
class OrderInfo:
    order_length: int
    order_done: bool
    order_timestamp: int
    ready_to_delete: bool
    order_array: np.ndarray


class GlobalSettings(ctypes.Structure):
    MAXPCIECARDS = 5

    _fields_ = [("useSoftwarePolling", ctypes.c_uint32),
                ("nos", ctypes.c_uint32),
                ("nob", ctypes.c_uint32),
                ("sti_mode", ctypes.c_uint32),
                ("bti_mode", ctypes.c_uint32),
                ("stime_in_microsec", ctypes.c_uint32),
                ("btime_in_microsec", ctypes.c_uint32),
                ("sdat_in_10ns", ctypes.c_uint32),
                ("bdat_in_10ns", ctypes.c_uint32),
                ("sslope", ctypes.c_uint32),
                ("bslope", ctypes.c_uint32),
                ("sec_in_10ns", ctypes.c_uint32),
                ("XCK delay in 10 ns steps", ctypes.c_uint32),
                ("trigger_mode_cc", ctypes.c_uint32),
                ("board_sel", ctypes.c_uint32),
                ("sensor_type", ctypes.c_uint32),
                ("camera_system", ctypes.c_uint32),
                ("camcnt", ctypes.c_uint32),
                ("pixel", ctypes.c_uint32),
                ("mshut", ctypes.c_uint32),
                ("led_off", ctypes.c_uint32),
                ("sensor_gain", ctypes.c_uint32),
                ("adc_gain", ctypes.c_uint32),
                ("Temp_level", ctypes.c_uint32),
                ("dac", ctypes.c_uint32),
                ("enable_gpx", ctypes.c_uint32),
                ("gpx_offset", ctypes.c_uint32),
                ("FFTLines", ctypes.c_uint32),
                ("Vfreq", ctypes.c_uint32),
                ("FFTMode", ctypes.c_uint32),
                ("lines_binning", ctypes.c_uint32),
                ("number_of_regions", ctypes.c_uint32),
                ("keep", ctypes.c_uint32),
                ("region_size", ctypes.c_uint32 * 8),
                ("dac_output", (ctypes.c_uint32 * MAXPCIECARDS) * 8),
                ("TORmodus", ctypes.c_uint32),
                ("ADC_Mode", ctypes.c_uint32),
                ("ADC_custom_pattern", ctypes.c_uint32),
                ("bec_in_10ns", ctypes.c_uint32),
                ("cont_pause_in_microseconds", ctypes.c_uint32),
                ("isIr", ctypes.c_uint32),
                ("IOCtrl_impact_start_pixel", ctypes.c_uint32),
                ("IOCtrl_output_width_in_5ns", ctypes.c_uint32 * 8),
                ("IOCtrl_output_delay_in_5ns", ctypes.c_uint32 * 8),
                ("IOCtrl_T0_period_in_10ns", ctypes.c_uint32),
                ("dma_buffer_size_in_scans", ctypes.c_uint32),
                ("tocnt", ctypes.c_uint32),
                ("ticnt", ctypes.c_uint32)
                ]

    _defaults_ = {"useSoftwarePolling": 0,
                "nos": 100,
                "nob": 1,
                "sti_mode": 4,
                "bti_mode": 4,
                "stime_in_microsec": 1000,
                "btime_in_microsec": 100000,
                "sdat_in_10ns": 0,
                "bdat_in_10ns": 0,
                "sslope": 0,
                "bslope": 1,
                "sec_in_10ns": 0,
                "XCK delay in 10 ns steps": 0,
                "trigger_mode_cc": 1,
                "board_sel": 1,
                "sensor_type": 1,
                "camera_system": 0,
                "camcnt": 1,
                "pixel": 1088,
                "mshut": 0,
                "led_off": 0,
                "sensor_gain": 0,
                "adc_gain": 1,
                "Temp_level": 1,
                "dac": 0,
                "enable_gpx": 0,
                "gpx_offset": 1000,
                "FFTLines": 128,
                "Vfreq": 7,
                "FFTMode": 0,
                "lines_binning": 1,
                "number_of_regions": 2,
                "keep": 0,
                "region_size": [32, 32, 16, 32, 68, 0, 0, 0],
                "dac_output":
                 [[51500, 51500, 51520, 51580, 51560, 51590, 51625, 51745],
                  [55000, 54530, 54530, 54530, 54530, 54530, 54530, 54530],
                  [0, 0, 0, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 0, 0, 0]],
                "TORmodus": 0,
                "ADC_Mode": 0,
                "ADC_custom_pattern": 100,
                "bec_in_10ns": 0,
                "cont_pause_in_microseconds": 1,
                "isIr": 0,
                "IOCtrl_impact_start_pixel": 1078,
                "IOCtrl_output_width_in_5ns": [50, 50, 50, 50, 50, 50, 50, 0],
                "IOCtrl_output_delay_in_5ns": [0, 100, 200, 300, 400, 500, 600, 0],
                "IOCtrl_T0_period_in_10ns": 1000,
                "dma_buffer_size_in_scans": 1000,
                "tocnt": 0,
                "ticnt": 0
                }

    def __init__(self, settings):
        for name, value in settings.items():
            if isinstance(value, list):
                value = np.asarray(value, dtype=np.uint)
                if len(value.shape) == 1:
                    arr = (ctypes.c_uint * value.shape[0])(*value)
                elif len(value.shape) == 2:
                    arr = ((ctypes.c_uint * value.shape[0]) * value.shape[1])()
                    # value = np.transpose(value)
                    # for x in range(value.shape[0]):
                    #     for y in range(value.shape[1]):
                    #         arr[x][y] = value[x][y]
                    # print(np.ctypeslib.as_array(arr))
                value = arr
            setattr(self, name, value)


class DS_STRESING_IR(DS_CAMERA_CCD):
    RULES = {**DS_CAMERA_CCD.RULES}

    _version_ = '0.2'
    _model_ = 'STRESING IR Detector'

    camera_type = device_property(dtype=str)
    wavelengths = device_property(dtype=str)

    def init_device(self):
        super().init_device()
        self.number_of_boards = 0
        self.wavelengths = eval(self.wavelengths)

    @attribute(label='number of kinetics', dtype=int, access=AttrWriteType.READ_WRITE)
    def number_kinetics(self):
        return self.n_kinetics

    def write_number_kinetics(self, value: int):
       self.n_kinetics = value

    def find_device(self) -> Tuple[int, str]:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.dll = self.load_dll()
            res = self._Initialize()
            if res == True:
                self.camera = True
                self.set_state(DevState.ON)
                self._GetCameraSerialNumber()
                argreturn = 1, str(self.serial_number_real).encode('utf-8')
            else:
                self.error(f'Could not initialize camera.')
            self._device_id_internal, self._uri = argreturn

    def get_camera_friendly_name(self):
        return self.friendly_name

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)

    def get_camera_serial_number(self) -> Union[str, int]:
        self._GetCameraSerialNumber()
        return self.serial_number_real

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
        pass

    def get_trigger_delay(self) -> str:
        return -1

    def get_exposure_min(self):
        return 0.00001

    def get_exposure_max(self):
        return 1

    def set_gain(self, value: int):
        self._SetPreAmpGain(value)

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
        return 256

    def get_offsetX(self) -> int:
        return self.camera.OffsetX()

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
            res = self._Initialize()
            if res == True:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('10.20.30.131', 5025))
                data = '*RCL 8\n'.encode('ascii')
                s.send(data)
                sleep(.1)
                s.close()
                self.info(f"{self.device_name} was Opened.", True)
                self.set_state(DevState.ON)
                return 0
            else:
                self.info(f'Could not turn on camera, because it does not exist.', True)
                return res
        else:
            return f'Could not turn on camera it is opened already.'

    def turn_off_local(self) -> Union[int, str]:
        if self.grabbing:
            self.stop_grabbing_local()
        res = self._Shutdown()
        self.camera = None
        self.dll = None
        if res == True:
            self.set_state(DevState.OFF)
            self.info(f"{self.device_name} was Closed.", True)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return res

    def set_param_after_init_local(self) -> Union[int, str]:
        return 0

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
            while self.abort is not True and self.camera:
                a = time()
                res = self._DLLReadFFLoop(1)
                res = self._StartAcquisition()
                res = self._GetData(size=1024 * self.n_kinetics * 2)
                if res == True:
                    data2D = np.reshape(self.array_real, (-1, 1024))
                    data2D.astype(np.uint16)
                    self.treat_orders(data2D)
                    self.info('Image is received...')
                else:
                    self.error(res)
                    data2D = np.zeros(1024 * self.n_kinetics * 2).reshape(-1, 1024)
                self.last_image = data2D
                b = time()
                self.info(f'Time passed: {b - a}')
            else:

        except Exception as e:
            self.error(e)

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
            self.abort = False
            self.grabbing_thread = Thread(target=self.wait, args=[self.timeoutt])
            self.grabbing_thread.start()
        return 0

    def stop_grabbing_local(self):
        res = self._AbortAcquisition()
        self.abort = True
        return 0

    def grabbing_local(self):
        res = False
        if self.camera:
            if self.status_real == 20072:
                res = True
        return res

    def set_trigger_mode(self, state):
        self._SetTriggerMode(state)

    def get_trigger_mode(self) -> int:
        return self.trigger_mode_value

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def _Initialize(self):
        res = self._DLLCCDDrvInit()
        if res != True:
            return res

        res = self._DLLInitBoard()
        if res != True:
            return res

        res = self._DLLSetGlobalSettings()
        if res != True:
            return res

        res = self._DLLInitMeasurement()

        return res

    def _GetCameraSerialNumber(self):
        self.serial_number_real = self.serial_number

    def _Shutdown(self):
        self.dll.DLLStopFFLoop()
        self.dll.DLLCCDDrvExit(ctypes.c_uint32(1))
        return True

    # DLL functions
    @dll_lock
    def _DLLCCDDrvInit(self) -> Tuple[bool, str]:
        """
        int32_t DLLCCDDrvInit(uint8_t * number_of_boards);
        """
        number_of_boards = ctypes.c_int8(0)
        res = self.dll.DLLCCDDrvInit(ctypes.byref(number_of_boards))
        self.number_of_boards = int(number_of_boards.value)
        return True if self.number_of_boards > 0 else self._error_stresing(res)

    @dll_lock
    def _DLLInitBoard(self) -> Tuple[bool, str]:
        """
        int32_t DLLInitBoard(void );
        """
        res = self.dll.DLLInitBoard()
        return True if res == 0 else self._error_stresing(res)

    @dll_lock
    def _DLLConvertErrorCodeToMsg(self, error_code: int) -> str:
        """
        CStr DLLConvertErrorCodeToMsg(int32_t status);
        """
        error_code = ctypes.c_int(error_code)
        self.dll.DLLConvertErrorCodeToMsg.restype = ctypes.c_char_p
        res = self.dll.DLLConvertErrorCodeToMsg(error_code)
        return res

    @dll_lock
    def _DLLInitMeasurement(self) -> Tuple[bool, str]:
        """
        int32_t DLLInitMeasurement(void );
        """
        res = self.dll.DLLInitMeasurement()
        return True if res == 0 else self._error_stresing(res)

    def _DLLSetGlobalSettings(self):
        settings: Dict[str, Any] = self.parameters['Acquisition_Controls']['Measurement_Settings']
        global_settings = GlobalSettings(settings=settings)
        global_settings_pointer = ctypes.byref(global_settings)
        res = self.dll.DLLSetGlobalSettings(global_settings_pointer)
        return True if res == 0 else self._error_stresing(res)

    def _DLLSetGammaValue(self, white: int, black: int):
        """
        void
        """
        white = ctypes.c_uint32(white)
        black = ctypes.c_uint32(black)
        self.dll.DLLSetGammaValue(white, black)
        return True

    def _DLLReadFFLoop(self):
        """
        void  DLLReadFFLoop(void );
        """
        self.dll.DLLReadFFLoop()
        return True

    def _DLLisMeasureOn(self, drv: int):
        """
        int32_t DLLisMeasureOn(uint32_t drv, uint8_t *measureOn);
        """
        drv = ctypes.c_uint32(drv)
        measureOn = ctypes.c_uint8(0)
        res = self.dll.DLLisMeasureOn(drv, ctypes.POINTER(measureOn))
        self.measure_on = bool(measureOn.value)
        return True if res == 0 else self._error_stresing(res)

    def DLLAbortMeasurement(self, drv: int):
        """
        int32_t DLLAbortMeasurement(uint32_t drv);
        """
        drv = ctypes.c_uint32(drv)
        res = self.DLLAbortMeasurement(drv)
        return True if res == 0 else self._error_stresing(res)

    def _error_stresing(self, code: int, user_def='') -> str:
        if user_def != '':
            return user_def
        res = self._DLLConvertErrorCodeToMsg(code)
        print(f'Error: {res}, Caller: {inspect.stack()[1].function} : {inspect.stack()[2].function} '
              f': {inspect.stack()[3].function}')
        return res


if __name__ == "__main__":
    DS_STRESING_IR.run_server()