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

from typing import Tuple, Union, List, Dict
from time import time_ns, time, sleep
import ctypes
import inspect
from threading import Thread
import numpy as np
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD, DS_CAMERA
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
    _fields_ = [("useSoftwarePolling", ctypes.c_uint32, 0),
                """
                brief useSoftwarePolling determines which method is used to copy data from DMA to user buffer.
                true: Use Software Polling. When there is new available data in the DMA buffer, a thread copies the data one scan at a time to the user buffer. This method is reliable up to about 33kHz. This was measured with a 3030 camera system with 1088 pixels, priority of the thread is not changed, 14.12.2021, FH.
                false: Use Interrupt. Every dma_buffer_size_in_scans/2 scan the interrupt starts a copy process, which copies dma_buffer_size_in_scans/2 scans to the user buffer. 1000 is our default value for dma_buffer_size_in_scans, so interrupt is started every 500 scans.
                """
                ("nos", ctypes.c_uint32, 100),
                """
                Number of blocks
                """
                ("nob", ctypes.c_uint32, 1),
                """
                Scan trigger input mode
                STI = {I: 0, S1: 1, S2: 2, unused: 3, STimer: 4, ASL: 5}
                """
                ("sti_mode", ctypes.c_uint32, 4),
                """
                Block trigger input mode
                BTI = {I: 0, S1: 1, S2: 2, S1 & S2: 3, BTimer: 4, S1 chopper: 5, S2 chopper: 6, S1 & S2 choppers: 7}
                """
                ("bti_mode", ctypes.c_uint32, 4),
                """
                Scan timer in microseconds.
                """
                ("stime_in_microsec", ctypes.c_uint32, 1000),
                """
                Block timer in microseconds.
                """
                ("btime_in_microsec", ctypes.c_uint32, 100000),
                """
                Scan delay after trigger in 10 ns steps.
                """
                ("sdat_in_10ns", ctypes.c_uint32, 0),
                """
                Block delay after trigger in 10 ns steps.
                """
                ("bdat_in_10ns", ctypes.c_uint32, 0),
                """
                Scan trigger slope.
                pos - 0, neg - 1, both - 2
                """
                ("sslope", ctypes.c_uint32, 0),
                """
                Block trigger slope.
                pos - 0, neg - 1, both - 2
                """
                ("bslope", ctypes.c_uint32, 1),
                """
                XCK delay in 10 ns steps
                """
                ("XCK delay in 10 ns steps", ctypes.c_uint32, 0),
                """
                SEC in 10 ns steps.
                """
                ("sec_in_10ns", ctypes.c_uint32, 0),
                """
                Trigger mode of camera control.
                XCK - 0, Ext. Trig. - 1, DAT - 2
                """
                ("trigger_mode_cc", ctypes.c_uint32, 1),
                """
                Board sel.
                0: 0
                1: board 1
                2: board 2
                3: both boards
                """
                ("board_sel", ctypes.c_uint32, 1),
                """
                Sensor type.
                0: PDA (line sensor)
                1: FFT (area sensor)
                """
                ("sensor_type", ctypes.c_uint32, 1),
                """
                Camera system
                0: 3001
                1: 3010
                2: 3030
                """
                ("camera_system", ctypes.c_uint32, 0),
                """
                Camera count
                """
                ("camcnt", ctypes.c_uint32, 1),
                """
                Pixel count
                """
                ("pixel", ctypes.c_uint32, 1088),
                """
                Mechanical shutter
                """
                ("mshut", ctypes.c_uint32, 0),
                """
                Turn leds off
                """
                ("led_off", ctypes.c_uint32, 0),
                """
                Sensor gain
                """
                ("adc_gain", ctypes.c_uint32, 0),
                """
                Temperature level
                """
                ("Temp_level", ctypes.c_uint32, 1),
                """
                Turn digital analog converter on / off
                - 0: off
                - >0: on
                """
                ("dac", ctypes.c_uint32, 0),
                """
                Enable GPX
                """
                ("enable_gpx", ctypes.c_uint32, 0),
                """
                GPX offset
                """
                ("gpx_offset", ctypes.c_uint32, 1000),
                """
                Count of lines for FFT sensors
                """
                ("FFTLines", ctypes.c_uint32, 128),
                """
                Vertical frequency for FFT sensors
                """
                ("Vfreq", ctypes.c_uint32, 7),
                """
                Mode for FFT sensors
                Full binning - 0
                Region of interest - 1
                Area - 2
                """
                ("FFTMode", ctypes.c_uint32, 0),
                """
                Count of lines which are binned in area mode for FFT sensors
                """
                ("lines_binning", ctypes.c_uint32, 1),
                """
                Number of regions for fft mode range of interest
                """
                ("number_of_regions", ctypes.c_uint32, 2),
                """
                Deprecated: Keep. Was a parameter to determine whether a region for region 
                of interest mode is filled with real or dummy data.
                """
                ("keep", ctypes.c_uint32, 0),
                """
                Size for each region for region of interest mode for FFT sensors.
                When the first region is set to 0, all regions are automatically same sized.
                """
                ("region_size", ctypes.c_uint32 * 8, [32, 32, 16, 32, 68, 0, 0, 0]),
                """
                "This is a matrix"
                Array for output levels of each digital to analog converter
                """
                ("dac_output", (ctypes.c_uint32 * MAXPCIECARDS) * 8,
                 [[51500, 51500, 51520, 51580, 51560, 51590, 51625, 51745],
                  [55000, 54530, 54530, 54530, 54530, 54530, 54530, 54530],
                  [0, 0, 0, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 0, 0, 0]
                  [0, 0, 0, 0, 0, 0, 0, 0]]),
                """
                XCK - 0
                REG/OutTrig - 1
                VON - 2
                DMA_Act - 3
                ASLS - 4
                STIMER - 5
                BTIMER - 6
                INTRSR - 7
                S1 - 8
                S2 - 9
                BON - 10
                MEASUREON - 11
                SDAT - 12
                BDAT - 13
                SSHUT - 14
                BSHUT - 15
                """
                ("TORmodus", ctypes.c_uint32, 0),
                """
                normal - 0
                ramp - 1
                custrom pattern - 2
                """
                ("ADC_Mode", ctypes.c_uint32, 0),
                """
                """
                ("ADC_custom_pattern", ctypes.c_uint32, 100),
                """
                """
                ("bec_in_10ns", ctypes.c_uint32, 0),
                """

                """
                ("cont_pause_in_microseconds", ctypes.c_uint32, 1),
                """
                """
                ("isIr", ctypes.c_uint32, 0),
                """
                """
                ("IOCtrl_impact_start_pixel", ctypes.c_uint32, 1078),
                """
                """
                ("IOCtrl_output_width_in_5ns", ctypes.c_uint32 * 8, [50, 50, 50, 50, 50, 50, 50, 0]),
                """
                """
                ("IOCtrl_output_delay_in_5ns", ctypes.c_uint32 * 8, [0, 100, 200, 300, 400, 500, 600, 0]),
                """
                """
                ("IOCtrl_T0_period_in_10ns", ctypes.c_uint32, 1000),
                """
                Size of DMA buffer in scans. 1000 is our default. 60 is also working with highspeed 
                (expt=0,02ms). 30 could be with one wrong scan every 10000 scans.
                """
                ("dma_buffer_size_in_scans", ctypes.c_uint32, 1000),
                """
                """
                ("tocnt", ctypes.c_uint32, 0),
                """
                """
                ("ticnt", ctypes.c_uint32, 0),
                ]


class DS_STRESING_IR(DS_CAMERA):
    RULES = {**DS_CAMERA.RULES}

    _version_ = '0.2'
    _model_ = 'STRESING IR Detector'

    camera_type = device_property(dtype=str)

    def init_device(self):
        self.number_of_boards = 0
        super().init_device()

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
            if res:
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
        res = self._GetStatus()
        if self.status_real != 20073:
            sleep(1)
        res = self._ShutDown()
        self.camera = None
        if res == True:
            self.set_state(DevState.OFF)
            self.info(f"{self.device_name} was Closed.", True)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return res

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
            while self.abort is not True and self.camera:
                a = time()
                res = self._SetNumberKinetics(self.n_kinetics)
                res = self._StartAcquisition()
                res = self._GetData(size=1024 * self.n_kinetics * 2)
                if res == True:
                    data2D = np.reshape(self.array_real, (-1, 1024))
                    data2D.astype('int16')

                    for spectrum in data2D:
                        time_stamp = time_ns()
                        self.time_stamp_deque.append(time_stamp)
                        self.data_deque.append(spectrum)

                        data_archive = self.form_archive_data(spectrum.reshape((1, 1024)),
                                                              name='spectra', time_stamp=time_stamp, dt='int16')
                        self.write_to_archive(data_archive)

                        if self.orders:
                            orders_to_delete = []
                            for order_name, order_info in self.orders.items():
                                if (time() - order_info.order_timestamp) >= 100:
                                    orders_to_delete.append(order_name)
                                elif not order_info.order_done:
                                    order_info.order_array = np.vstack([order_info.order_array, spectrum])

                                if order_info.order_length * 3 == len(order_info.order_array) - 1:
                                    order_info.order_done = True

                            if orders_to_delete:
                                for order_name in orders_to_delete:
                                    del self.orders[order_name]

                    self.info('Image is received...')
                else:
                    self.error(res)
                    data2D = np.zeros(1024 * self.n_kinetics * 2).reshape(-1, 1024)
                self.last_image = data2D
                b = time()
                self.info(f'Time passed: {b - a}')
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

    # DLL functions
    @dll_lock
    def _DLLCCDDrvInit(self) -> Tuple[bool, str]:
        """
        int32_t DLLCCDDrvInit(uint8_t * number_of_boards);
        """
        number_of_boards = ctypes.c_int8(0)
        res = self.dll.DLLCCDDrvInit(ctypes.byref(number_of_boards))
        self.number_of_boards = number_of_boards.value
        return True if self.number_of_boards >= 0 else self._error_stresing(res)

    @dll_lock
    def _DLLInitBoard(self) -> Tuple[bool, str]:
        """
        int32_t DLLInitBoard(void );
        """
        res = self.dll.DLLInitBoard()
        return True if res == 0 else self._error_stresing(res)

    def _DLLConvertErrorCodeToMsg(self, error_code: int) -> str:
        """
        CStr DLLConvertErrorCodeToMsg(int32_t status);
        """
        error_code = ctypes.c_int32(error_code)
        res = self.dll.DLLConvertErrorCodeToMsg(error_code)
        return res

    def _InitMeasurement(self) -> Tuple[bool, str]:
        """
        void  DLLSetGlobalSettings(void *struct global_settings);
        int32_t DLLInitMeasurement(void );
        """
        global_settings = GlobalSettings()
        res = self.dll.DLLInitMeasurement(ctypes.POINTER(global_settings))
        return True if res == 0 else self._error_stresing(res)

    def _DLLSetGammaValue(self, white: int, black: int):
        """
        void
        """
        white =ctypes.c_uint32(white)
        black =ctypes.c_uint32(black)
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


    def _error_stresing(self, code: int, user_def='') -> str:
        if user_def != '':
            return user_def
        res = self._DLLConvertErrorCodeToMsg(code)
        print(f'Error: {res}, Caller: {inspect.stack()[1].function} : {inspect.stack()[2].function}')
        return res


if __name__ == "__main__":
    DS_STRESING_IR.run_server()