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
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output
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


class DS_ANDOR_CCD(DS_CAMERA_CCD):
    RULES = {**DS_CAMERA_CCD.RULES}

    _version_ = '0.1'
    _model_ = 'ANDOR CCD'

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path = device_property(dtype=str)
    width = device_property(dtype=int)
    wavelengths = device_property(dtype=str)

    def init_device(self):
        self._dll_lock = True
        self.dll = None
        self.serial_number_real = -1
        self.head_name = ''
        self.status_real = 0
        self.exposure_time_local = -1
        self.accumulate_time_local = -1
        self.kinetic_time_local = -1
        self.n_gains_max = 1
        self.gain_value = -1
        self.height_value = 256
        self.grabbing_thread: Thread = None
        self.abort = False
        self.n_kinetics = 3
        self.data_deque = deque(maxlen=1000)
        self.time_stamp_deque = deque(maxlen=1000)
        self.orders: Dict[str, OrderInfo] = {}
        super().init_device()
        self.register_variables_for_archive()
        self.wavelengths = eval(self.wavelengths)
        self.start_grabbing()

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

    @command(dtype_in=int, dtype_out=str, doc_in='Takes number of spectra', doc_out='return name of order')
    def register_order(self, number_spectra: int):
        s = 20  # number of characters in the string.
        name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=s))
        order_info = OrderInfo(number_spectra, False, time(), False, np.array([self.wavelengths]))
        self.orders[name] = order_info
        return name

    @command(dtype_in=str, doc_in='Order name', dtype_out=bool)
    def is_order_ready(self, name):
        res = False
        if name in self.orders:
            order = self.orders[name]
            res = order.order_done
        return res

    @command(dtype_in=str, doc_in='Order name', dtype_out=str)
    def give_order(self, name):
        res = self.last_image
        if name in self.orders:
            order = self.orders[name]
            order.ready_to_delete = True
            res = order.order_array
        res = res.astype(dtype=np.int16)
        res = res.tobytes()
        res = zlib.compress(res)
        return str(res)

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
    def load_dll(self):
        dll = ctypes.WinDLL(str(self.dll_path))
        self._dll_lock = False
        return dll

    @dll_lock
    def _Initialize(self, dir='') -> Tuple[bool, str]:
        """
        unsigned int WINAPI Initialize(char* dir)
        Description         This function will initialize the Andor SDK System. As part of the initialization procedure on
                            some cameras (i.e. Classic, iStar and earlier iXion) the DLL will need access to a
                            DETECTOR.INI which contains information relating to the detector head, number pixels,
                            readout speeds etc. If your system has multiple cameras then see the section Controlling
                            multiple cameras
        Parameters          char* dir: Path to the directory containing the files
        Return              unsigned int
                            DRV_SUCCESS             Initialisation successful.
                            DRV_VXDNOTINSTALLED     VxD not loaded.
                            DRV_INIERROR            Unable to load “DETECTOR.INI”.
                            DRV_COFERROR            Unable to load “*.COF”.
                            DRV_FLEXERROR           Unable to load “*.RBF”.
                            DRV_ERROR_ACK           Unable to communicate with card.
                            DRV_ERROR_FILELOAD      Unable to load “*.COF” or “*.RBF” files.
                            DRV_ERROR_PAGELOCK      Unable to acquire lock on requested memory.
                            DRV_USBERROR            Unable to detect USB device or not USB2.0.
                            DRV_ERROR_NOCAMERA      No camera found
        """
        dir_char = ctypes.c_char_p(dir.encode('utf-8'))
        res = self.dll.Initialize(dir_char)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetCameraSerialNumber(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetCameraSerialNumber (int* number)
        Description         This function will retrieve camera’s serial number.
        Parameters          int *number: Serial Number.
        Return              unsigned int
                            DRV_SUCCESS             Serial Number returned.
                            DRV_NOT_INITIALIZED     System not initialized.
        """
        serial_number = ctypes.c_int(0)
        res = self.dll.GetCameraSerialNumber(ctypes.byref(serial_number))
        self.serial_number_real = serial_number.value
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetHeadModel(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetHeadModel(char* name)
        Description This function will retrieve the type of CCD attached to your system.
        Parameters char* name: A user allocated array of characters for storage of the Head Model. This
        should be declared as size MAX_PATH.
        Return unsigned int
        DRV_SUCCESS
        DRV_NOT_INITIALIZED
        Name returned.
        System not initialized.
        :return:
        """
        head = ctypes.c_char_p('HeadName                     '.encode('utf-8'))
        res = self.dll.GetHeadModel(head)
        self.head_name = head
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetNumberPreAmpGains(self):
        """
        unsigned int WINAPI GetNumberPreAmpGains(int* noGains)
        Description Available in some systems are a number of pre amp gains that can be applied to the
        data as it is read out. This function gets the number of these pre amp gains available.
        The functions GetPreAmpGain and SetPreAmpGain can be used to specify which of
        these gains is to be used.
        Parameters int* noGains: number of allowed pre amp gains
        :return:
        Return unsigned int
        DRV_SUCCESS
        DRV_NOT_INITIALIZED
        DRV_ACQUIRING
        Number of pre amp gains returned.
        System not initialized.
        Acquisition in progress.
        """
        nogains = ctypes.c_int()
        res = self.dll.GetNumberPreAmpGains(nogains)
        self.n_gains_max =  nogains - 1
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetNumberADChannels(self):
        """
        unsigned int WINAPI GetNumberADChannels(int* channels)
        Description         As your Andor SDK system may be capable of operating with more than one A-D
                            converter, this function will tell you the number available.
        Parameters          int* channels: number of allowed channels
        Return              unsigned int
                            DRV_SUCCESS         Number of channels returned
        """
        n_ad_channels = ctypes.c_int(0)
        res = self.dll.GetNumberADChannels(ctypes.byref(n_ad_channels))
        self.n_ad_channels = n_ad_channels.value
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetKineticCycleTime(self, time: float):
        """
        unsigned int WINAPI SetKineticCycleTime(float time)
        Description This function will set the kinetic cycle time to the nearest valid value not less than the
        given value. The actual time used is obtained by GetAcquisitionTimings. . Please refer to
        SECTION 5 – ACQUISITION MODES for further information.
        Parameters float time: the kinetic cycle time in seconds.
        Return unsigned int
        DRV_SUCCESS
        DRV_NOT_INITIALIZED
        DRV_ACQUIRING
        DRV_P1INVALID
        Cycle time accepted.
        System not initialized.
        Acquisition in progress.
        Time invalid
        """
        res = self.dll.SetKineticCycleTime(ctypes.c_float(time))
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetAcquisitionMode(self, mode: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetAcquisitionMode(int mode)
        Description         This function will set the acquisition mode to be used on the next StartAcquisition.
        Parameters          int mode: the acquisition mode.
        Valid values:
                            1 Single Scan
                            2 Accumulate
                            3 Kinetics
                            4 Fast Kinetics
                            5 Run till abort
        Return              unsigned int
        DRV_SUCCESS             Acquisition mode set.
        DRV_NOT_INITIALIZED     System not initialized.
        DRV_ACQUIRING           Acquisition in progress.
        DRV_P1INVALID           Acquisition Mode invalid.

    NOTE: In Mode 5 the system uses a “Run Till Abort” acquisition mode. In Mode 5 only, the camera
    continually acquires data until the AbortAcquisition function is called. By using the SetDriverEvent
    function you will be notified as each acquisition is completed.
        """
        MODES = {1: 'Single Scan', 2: 'Accumulate', 3: 'Kinetics', 4: 'Fast Kinetics', 5: 'Run Till abort'}
        if mode not in MODES:
            return self._error_andor(-1, user_def=f'Wrong mode {mode} for SetAcquisitionMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetAcquisitionMode(mode)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetExposureTime(self, exp_time: float) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetExposureTime(float time)
        Description             This function will set the exposure time to the nearest valid value not less than the given
                                value. The actual exposure time used is obtained by GetAcquisitionTimings. . Please
                                refer to SECTION 5 – ACQUISITION MODES for further information.
        Parameters              float time: the exposure time in seconds.
        Return                  unsigned int
                                DRV_SUCCESS             Exposure time accepted.
                                DRV_NOT_INITIALIZED     System not initialized.
                                DRV_ACQUIRING           Acquisition in progress.
                                DRV_P1INVALID           Exposure Time invalid.
        NOTE: For Classics, if the current acquisition mode is Single-Track, Multi-Track or Image then this
        function will actually set the Shutter Time. The actual exposure time used is obtained from the
        GetAcquisitionTimings function.
        """
        exp_time = ctypes.c_float(exp_time)
        res = self.dll.SetExposureTime(exp_time)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetAcquisitionTimings(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetAcquisitionTimings(float* exposure, float* accumulate, float* kinetic)
        Description This function will return the current “valid” acquisition timing information. This function
        should be used after all the acquisitions settings have been set, e.g. SetExposureTime,
        SetKineticCycleTime and SetReadMode etc. The values returned are the actual times
        used in subsequent acquisitions.
        This function is required as it is possible to set the exposure time to 20ms, accumulate
        cycle time to 30ms and then set the readout mode to full image. As it can take 250ms to
        read out an image it is not possible to have a cycle time of 30ms.
        Parameters float* exposure: valid exposure time in seconds
        float* accumulate: valid accumulate cycle time in seconds
        float* kinetic: valid kinetic cycle time in seconds
        :return:
        Return unsigned int
        DRV_SUCCESS
        DRV_NOT_INITIALIZED
        DRV_ACQUIRING
        DRV_INVALID_MODE
        Timing information returned.
        System not initialized.
        Acquisition in progress.
        Acquisition or readout mode is not available
        """
        exp_time = ctypes.c_float()
        accumulate_time = ctypes.c_float()
        kinetic_time = ctypes.c_float()
        res = self.dll.GetAcquisitionTimings(ctypes.byref(exp_time),
                                             ctypes.byref(accumulate_time),
                                             ctypes.byref(kinetic_time))
        self.exposure_time_local = exp_time.value
        self.accumulate_time_local = accumulate_time.value
        self.kinetic_time_local = kinetic_time.value
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetHSSpeed(self, typ: int, index: int) -> Tuple[bool, str]:
        """
            unsigned int WINAPI SetHSSpeed(int typ, int index)
        Description         This function will set the speed at which the pixels are shifted into the output node during
                            the readout phase of an acquisition. Typically your camera will be capable of operating at
                            several horizontal shift speeds. To get the actual speed that an index corresponds to use
                            the GetHSSpeed function.
        Parameters          int typ: output amplification.
                            Valid values:       0 electron multiplication/Conventional(clara).
                                                1 conventional/Extended NIR mode(clara).
                            int index: the horizontal speed to be used
                            Valid values        0 to GetNumberHSSpeeds()-1
        Return              unsigned int
                            DRV_SUCCESS             Horizontal speed set.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_P1INVALID           Mode is invalid.
                            DRV_P2INVALID           Index is out off range
        """
        typ = ctypes.c_int(typ)
        index = ctypes.c_int(index)
        res = self.dll.SetHSSpeed(typ, index)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetVSSpeed(self, index: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetVSSpeed(int index)
        Description         This function will set the vertical speed to be used for subsequent acquisitions
        Parameters          int index: index into the vertical speed table
                            Valid values 0 to GetNumberVSSpeeds-1
        Return              unsigned int
                            DRV_SUCCESS             Vertical speed set.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_P1INVALID           Index out of range.
        """
        index = ctypes.c_int(index)
        res = self.dll.SetVSSpeed(index)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetADChannel(self, channel: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetADChannel(int channel)
        Description     This function will set the AD channel to one of the possible A-Ds of the system. This AD
                        channel will be used for all subsequent operations performed by the system.
        Parameters      int index: the channel to be used
                        Valid values: 0 to GetNumberADChannels-1
        Return          unsigned int
                        DRV_SUCCESS     AD channel set.
                        DRV_P1INVALID   Index is out off range.
        """
        channel = ctypes.c_int(channel)
        res = self.dll.SetADChannel(channel)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetPreAmpGain(self, index: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetPreAmpGain(int index)
        Description             This function will set the pre amp gain to be used for subsequent acquisitions. The actual
                                gain factor that will be applied can be found through a call to the GetPreAmpGain
                                function.
                                The number of Pre Amp Gains available is found by calling the GetNumberPreAmpGains
                                function.
        Parameters              int index: index pre amp gain table
                                Valid values 0 to GetNumberPreAmpGains-1
        Return                  unsigned int
                                DRV_SUCCESS             Pre amp gain set.
                                DRV_NOT_INITIALIZED     System not initialized.
                                DRV_ACQUIRING           Acquisition in progress.
                                DRV_P1INVALID           Index out of range
        """
        index = ctypes.c_int(index)
        res = self.dll.SetPreAmpGain(index)
        result = True if res == 20002 else self._error_andor(res)
        if result:
            self.gain_value = index
        else:
            self.gain_value = -1
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetTriggerMode(self, mode: int) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetTriggerMode(int mode)
        Description         This function will set the trigger mode that the camera will operate in.
        Parameters          int mode: trigger mode
        Valid values:
                            0. Internal
                            1. External
                            6. External Start
                            7. External Exposure (Bulb)
                            9. External FVB EM (only valid for EM Newton models in FVB mode)
                            10. Software Trigger
                            12. External Charge Shifting
        Return              unsigned int
                            DRV_SUCCESS             Trigger mode set.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_P1INVALID           Trigger mode invalid
        """
        MODES = {0: 'Internal', 1: 'External', 6: 'External Start', 7: 'External Exposure (Bulb)', 9: 'External FVB EM (only valid for EM Newton models in FVB mode', 10: 'Software Trigger', 12: 'External Charge Shifting'}
        if mode not in MODES:
            return self._error_andor(-1, user_def=f'Wrong mode {mode} for SetTriggerMode. MODES: {MODES}')
        self.trigger_mode_value = mode
        mode = ctypes.c_int(mode)
        res = self.dll.SetTriggerMode(mode)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetFastExtTrigger(self, mode: int) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetFastExtTrigger(int mode)
        Description         This function will enable fast external triggering. When fast external triggering is enabled
                            the system will NOT wait until a “Keep Clean” cycle has been completed before
                            accepting the next trigger. This setting will only have an effect if the trigger mode has
                            been set to External via SetTriggerMode.
        Parameters          int mode:
                            0 Disabled
                            1 Enabled
        Return              unsigned int
                            DRV_SUCCESS         Parameters accepted.
        """
        MODES = {0: 'Disabled', 1: 'Enabled'}
        if mode not in MODES:
            return self._error_andor(-1, user_def=f'Wrong mode {mode} for SetFastExtTrigger. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetFastExtTrigger(mode)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetReadMode(self, mode: int) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetReadMode(int mode)
        Description         This function will set the readout mode to be used on the subsequent acquisitions.
        Parameters          int mode: readout mode
                            Valid values:
                                        0 Full Vertical Binning
                                        1 Multi-Track
                                        2 Random-Track
                                        3 Single-Track
                                        4 Image
        Return              unsigned int
                            DRV_SUCCESS             Readout mode set.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_P1INVALID           Invalid readout mode passed.
        """
        MODES = {0: 'Full Vertical Binning', 1: 'Multi-Track', 2: 'Random-Track', 3: 'Single-Track', 4: 'Image'}
        if mode not in MODES:
            return self._error_andor(-1, user_def=f'Wrong mode {mode} for SetReadMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetReadMode(mode)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetMultiTrack(self, typ: int, index: int, offset: int, bottom=0, gap=0) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetMultiTrack(int number, int height, int offset, int* bottom, int *gap)
        Description This function will set the multi-Track parameters. The tracks are automatically spread
        evenly over the detector. Validation of the parameters is carried out in the following
        order:
        - Number of tracks,
        - Track height
        - Offset.
        The first pixels row of the first track is returned via ‘bottom’.
        The number of rows between each track is returned via ‘gap’.
        Parameters      int number: number tracks
                        Valid values 1 to number of vertical pixels
                        int height: height of each track
                        Valid values >0 (maximum depends on number of tracks)
                        int offset: vertical displacement of tracks
                        Valid values depend on number of tracks and track height
                        int* bottom: first pixels row of the first track
                        int* gap: number of rows between each track (could be 0)
                        Return unsigned int
                                                DRV_SUCCESS             Parameters set.
                                                DRV_NOT_INITIALIZED     System not initialized.
                                                DRV_ACQUIRING           Acquisition in progress.
                                                DRV_P1INVALID           Number of tracks invalid.
                                                DRV_P2INVALID           Track height invalid.
                                                DRV_P3INVALID           Offset invalid.
        """
        typ = ctypes.c_int(typ)
        index = ctypes.c_int(index)
        offset = ctypes.c_int(offset)
        bottom = ctypes.byref(ctypes.c_int(bottom))
        gap = ctypes.byref(ctypes.c_int(gap))
        res = self.dll.SetMultiTrack(typ, index, offset, bottom, gap)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetBaselineClamp(self, state: int) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetBaselineClamp(int state)
        Description         This function turns on and off the baseline clamp functionality. With this feature enabled
                            the baseline level of each scan in a kinetic series will be more consistent across the
                            sequence.
        Parameters          int state: Enables/Disables Baseline clamp functionality
                                        1 – Enable Baseline Clamp
                                        0 – Disable Baseline Clamp
        Return      unsigned int
                    DRV_SUCCESS             Parameters set.
                    DRV_NOT_INITIALIZED     System not initialized.
                    DRV_ACQUIRING           Acquisition in progress.
                    DRV_NOT_SUPPORTED       Baseline Clamp not supported on this camera
                    DRV_P1INVALID           State parameter was not zero or one
        """
        state = ctypes.c_int(state)
        res = self.dll.SetBaselineClamp(state)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetTemperature(self, temperature: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI SetTemperature(int temperature)
        Description         This function will set the desired temperature of the detector. To turn the cooling ON and
                            OFF use the CoolerON and CoolerOFF function respectively.
        Parameters          int temperature: the temperature in Centigrade.
                            Valid range is given by GetTemperatureRange
        Return              unsigned int
                            DRV_SUCCESS             Temperature set.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_ERROR_ACK           Unable to communicate with card.
                            DRV_P1INVALID           Temperature invalid.
                            DRV_NOT_SUPPORTED       The camera does not support setting the temperature.

            NOTE: Not available on Luca R cameras – automatically cooled to -20.
        """
        temperature = ctypes.c_int(temperature)
        res = self.dll.SetTemperature(temperature)
        return True if res == 20002 else self._error_andor(res)

    def _SetCooler(self, state: bool):
        if state:
            res = self._CoolerON()
        else:
            res = self._CoolerOFF()
        return res

    @dll_lock
    def _CoolerON(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI CoolerON(void)
        Description         Switches ON the cooling. On some systems the rate of temperature change is controlled
                            until the temperature is within 3º of the set value. Control is returned immediately to the
                            calling application.
        Parameters          NONE
        Return              unsigned int
                            DRV_SUCCESS             Temperature controller switched ON.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_ERROR_ACK           Unable to communicate with card.

        NOTE:
            The temperature to which the detector will be cooled is set via SetTemperature. The temperature
            stabilization is controlled via hardware, and the current temperature can be obtained via
            GetTemperature. The temperature of the sensor is gradually brought to the desired temperature to
            ensure no thermal stresses are set up in the sensor.
            Can be called for certain systems during an acquisition. This can be tested for using
            GetCapabilities.
        """
        res = self.dll.CoolerON()
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _CoolerOFF(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI CoolerOFF(void)
        Description         Switches OFF the cooling. The rate of temperature change is controlled in some models
                            until the temperature reaches 0º. Control is returned immediately to the calling
                            application.
        Parameters          NONE
        Return              unsigned int
                            DRV_SUCCESS             Temperature controller switched OFF.
                            DRV_NOT_INITIALIZED     System not initialized.
                            DRV_ACQUIRING           Acquisition in progress.
                            DRV_ERROR_ACK           Unable to communicate with card.
                            DRV_NOT_SUPPORTED       Camera does not support switching cooler off.

        NOTE: Not available on Luca R cameras – always cooled to -20.
        NOTE: (Classic & ICCD only)
            1. When the temperature control is switched off the temperature of the sensor is gradually
                raised to 0ºC to ensure no thermal stresses are set up in the sensor.
            2. When closing down the program via ShutDown you must ensure that the temperature of the
                detector is above -20ºC, otherwise calling ShutDown while the detector is still cooled will
                cause the temperature to rise faster than certified.

        """
        res = self.dll.CoolerOFF()
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _ShutDown(self):
        """
        unsigned int WINAPI ShutDown(void)
        Description         This function will close the AndorMCD system down.
        Parameters          NONE
        Return              unsigned int
                            DRV_SUCCESS         System shut down.

        NOTE:
            1. For Classic & ICCD systems, the temperature of the detector should be above -20ºC before
            shutting down the system.
            2. When dynamically loading a DLL which is statically linked to the SDK library, ShutDown MUST be
            called before unloading.
        """
        res = self.dll.ShutDown()
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _SetNumberKinetics(self, number: int) -> Tuple[int, bool, str]:
        """
        unsigned int WINAPI SetNumberKinetics(int number)
    Description         This function will set the number of scans (possibly accumulated scans) to be taken
                        during a single acquisition sequence. This will only take effect if the acquisition mode is
                        Kinetic Series.
    Parameters          int number: number of scans to store
    Return              unsigned int
                        DRV_SUCCESS             Series length set.
                        DRV_NOT_INITIALIZED     System not initialized.
                        DRV_ACQUIRING           Acquisition in progress.
                        DRV_P1INVALID           Number in series invalid
        """
        number = ctypes.c_int(number)
        res = self.dll.SetNumberKinetics(number)
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _PrepareAcquisition(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI PrepareAcquisition(void)
    Description     This function reads the current acquisition setup and allocates and configures any
                    memory that will be used during the acquisition. The function call is not required as it will
                    be called automatically by the StartAcquisition function if it has not already been called
                    externally.
                    However for long kinetic series acquisitions the time to allocate and configure any
                    memory can be quite long which can result in a long delay between calling
                    StartAcquisition and the acquisition actually commencing. For iDus, there is an additional
                    delay caused by the camera being set-up with any new acquisition parameters. Calling
                    PrepareAcquisition first will reduce this delay in the StartAcquisition call.
    Parameters      NONE
    Return          unsigned int
                    DRV_SUCCESS             Acquisition prepared.
                    DRV_NOT_INITIALIZED     System not initialized.
                    DRV_ACQUIRING           Acquisition in progress.
                    DRV_VXDNOTINSTALLED     VxD not loaded.
                    DRV_ERROR_ACK           Unable to communicate with card.
                    DRV_INIERROR            Error reading “DETECTOR.INI”.
                    DRV_ACQERROR            Acquisition settings invalid.
                    DRV_ERROR_PAGELOCK      Unable to allocate memory.
                    DRV_INVALID_FILTER      Filter not available for current acquisition.
                    DRV_IOCERROR            Integrate On Chip setup error.
                    DRV_BINNING_ERROR       Range not multiple of horizontal binning.
                    DRV_SPOOLSETUPERROR     Error with spool settings.
        """
        res = self.dll.PrepareAcquisition()
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _StartAcquisition(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI StartAcquisition(void)
    Description         This function starts an acquisition. The status of the acquisition can be monitored via
                        GetStatus().
    Parameters          NONE
    Return              unsigned int
                        DRV_SUCCESS             Acquisition started.
                        DRV_NOT_INITIALIZED     System not initialized.
                        DRV_ACQUIRING           Acquisition in progress.
                        DRV_VXDNOTINSTALLED     VxD not loaded.
                        DRV_ERROR_ACK           Unable to communicate with card.
                        DRV_INIERROR            Error reading “DETECTOR.INI”.
                        DRV_ACQERROR            Acquisition settings invalid.
                        DRV_ERROR_PAGELOCK      Unable to allocate memory.
                        DRV_INVALID_FILTER      Filter not available for current acquisition.
                        DRV_BINNING_ERROR       Range not multiple of horizontal binning.
                        DRV_SPOOLSETUPERROR     Error with spool settings.
        """
        res = self.dll.StartAcquisition()
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _GetStatus(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetStatus(int* status)
        Description         This function will return the current status of the Andor SDK system. This function should
                            be called before an acquisition is started to ensure that it is IDLE and during an acquisition
                            to monitor the process.
        Parameters          int* status: current status
                            DRV_IDLE   20073                 IDLE waiting on instructions.
                            DRV_TEMPCYCLE               Executing temperature cycle.
                            DRV_ACQUIRING    20072           Acquisition in progress.
                            DRV_ACCUM_TIME_NOT_MET      Unable to meet Accumulate cycle time.
                            DRV_KINETIC_TIME_NOT_MET    Unable to meet Kinetic cycle time.
                            DRV_ERROR_ACK   20013            Unable to communicate with card.
                            DRV_ACQ_BUFFER              Computer unable to read the data via the ISA slot
                                                        at the required rate.
                            DRV_ACQ_DOWNFIFO_FULL       Computer unable to read data fast enough to stop
                                                        camera memory going full.
                            DRV_SPOOLERROR              Overflow of the spool buffer.
        Return              unsigned int
                            DRV_SUCCESS                 Status returned
                            DRV_NOT_INITIALIZED         System not initialized
        """
        status = ctypes.c_int(0)
        res = self.dll.GetStatus(ctypes.byref(status))
        self.status_real = status.value
        return True if res == 20002 else self._error_andor(res)

    def _GetData(self, size: int):
        i = 0
        while True:
            sleep(0.015)
            self._GetStatus()
            i += 1
            if self.status_real == 20073 or i > 100 or self.abort:
                break
        if not self.abort:
            res = self._GetAcquiredData(size)
        else:
            res = 'Was aborted'
        return res
    @dll_lock
    def _GetAcquiredData(self, size: int) -> Tuple[bool, str]:

        """
            unsigned int WINAPI GetAcquiredData(at_32* arr, unsigned long size)
            Description         This function will return the data from the last acquisition. The data are returned as long
                                integers (32-bit signed integers). The “array” must be large enough to hold the complete
                                data set.
            Parameters          at_32* arr: pointer to data storage allocated by the user.
                                unsigned long size: total number of pixels.
            Return              unsigned int
                                DRV_SUCCESS             Data copied.
                                DRV_NOT_INITIALIZED     System not initialized.
                                DRV_ACQUIRING           Acquisition in progress.
                                DRV_ERROR_ACK           Unable to communicate with card.
                                DRV_P1INVALID           Invalid pointer (i.e. NULL).
                                DRV_P2INVALID           Array size is incorrect.
                                DRV_NO_NEW_DATA         No acquisition has taken place
        """
        array = (ctypes.c_int32 * size)()
        array_p = ctypes.cast(array, ctypes.POINTER(ctypes.c_int32))
        res = self.dll.GetAcquiredData(array_p, ctypes.c_long(size))
        self.array_real = np.array(array[:])
        return True if res == 20002 else self._error_andor(res)

    @dll_lock
    def _AbortAcquisition(self):
        """
        unsigned int WINAPI AbortAcquisition(void)
        Description This function aborts the current acquisition if one is active.
        Parameters NONE
                Return unsigned int
                DRV_SUCCESS
                DRV_NOT_INITIALIZED
                DRV_IDLE
                DRV_VXDNOTINSTALLED
                DRV_ERROR_ACK
        Acquisition aborted.
        System not initialized.
        The system is not currently acquiring.
        VxD not loaded.
        Unable to communicate with card
        """
        res = self.dll.AbortAcquisition()
        return True if res == 20002 else self._error_andor(res)

    def _error_andor(self, code: int, user_def='') -> str:
        """
        :param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors = {20001: 'DRV_ERROR_CODES', 20002: 'DRV_SUCCESS', 20003: 'DRV_VXDNOTINSTALLED', 20004: 'DRV_ERROR_SCAN',
                  20005: 'DRV_ERROR_CHECK_SUM', 20006: 'DRV_ERROR_FILELOAD', 20007: 'DRV_UNKNOWN_FUNCTION',
                  20008: 'DRV_ERROR_VXD_INIT', 20009: 'DRV_ERROR_ADDRESS', 20010: 'DRV_ERROR_PAGELOCK',
                  20011: 'DRV_ERROR_PAGE_UNLOCK', 20012: 'DRV_ERROR_BOARDTEST', 20013: 'DRV_ERROR_ACK',
                  20014: 'DRV_ERROR_UP_FIFO', 20015: 'DRV_ERROR_PATTERN', 20017: 'DRV_ACQUISITION_ERRORS',
                  20018: 'DRV_ACQ_BUFFER', 20019: 'DRV_ACQ_DOWNFIFO_FULL', 20020: 'DRV_PROG_UNKNOWN_INSTRUCTION',
                  20021: 'DRV_ILLEGAL_OP_CODE', 20022: 'DRV_KINETIC_TIME_NOT_MET', 20023: 'DRV_ACCUM_TIME_NOT_MET',
                  20024: 'DRV_NO_NEW_DATA', 20025: 'PCI_DMA_FAIL', 20026: 'DRV_SPOOLERROR',
                  20027: 'DRV_SPOOLSETUPERROR', 20029: 'SATURATED', 20033: 'DRV_TEMPERATURE_CODES',
                  20034: 'DRV_TEMPERATURE_OFF', 20035: 'DRV_TEMP_NOT_STABILIZED', 20036: 'DRV_TEMPERATURE_STABILIZED',
                  20037: 'DRV_TEMPERATURE_NOT_REACHED', 20038: 'DRV_TEMPERATURE_OUT_RANGE',
                  20039: 'DRV_TEMPERATURE_NOT_SUPPORTED', 20040: 'DRV_TEMPERATURE_DRIFT', 20049: 'DRV_GENERAL_ERRORS',
                  20050: 'DRV_INVALID_AUX', 20051: 'DRV_COF_NOTLOADED', 20052: 'DRV_FPGAPROG', 20053: 'DRV_FLEXERROR',
                  20054: 'DRV_GPIBERROR', 20055: 'ERROR_DMA_UPLOAD', 20064: 'DRV_DATATYPE', 20065: 'DRV_DRIVER_ERRORS',
                  20066: 'DRV_P1INVALID', 20067: 'DRV_P2INVALID', 20068: 'DRV_P3INVALID', 20069: 'DRV_P4INVALID',
                  20070: 'DRV_INIERROR', 20071: 'DRV_COFERROR', 20072: 'DRV_ACQUIRING', 20073: 'DRV_IDLE',
                  20074: 'DRV_TEMPCYCLE', 20075: 'DRV_NOT_INITIALIZED', 20076: 'DRV_P5INVALID', 20077: 'DRV_P6INVALID',
                  20078: 'DRV_INVALID_MODE', 20079: 'DRV_INVALID_FILTER', 20080: 'DRV_I2CERRORS',
                  20081: 'DRV_DRV_I2CDEVNOTFOUND', 20082: 'DRV_I2CTIMEOUT', 20083: 'DRV_P7INVALID',
                  20089: 'DRV_USBERROR', 20090: 'DRV_IOCERROR', 20091: 'DRV_VRMVERSIONERROR',
                  20093: 'DRV_USB_INTERRUPT_ENDPOINT_ERROR', 20094: 'DRV_RANDOM_TRACK_ERROR',
                  20095: 'DRV_INVALID_TRIGGER_MODE', 20096: 'DRV_LOAD_FIRMWARE_ERROR',
                  20097: 'DRV_DIVIDE_BY_ZERO_ERROR', 20098: 'DRV_INVALID_RINGEXPOSURES', 20099: 'DRV_BINNING_ERROR',
                  20990: 'DRV_ERROR_NOCAMERA', 20991: 'DRV_NOT_SUPPORTED', 20992: 'DRV_NOT_AVAILABLE',
                  20115: 'DRV_ERROR_MAP', 20116: 'DRV_ERROR_UNMAP', 20117: 'DRV_ERROR_MDL', 20118: 'DRV_ERROR_UNMDL',
                  20119: 'DRV_ERROR_BUFFSIZE', 20121: 'DRV_ERROR_NOHANDLE', 20130: 'DRV_GATING_NOT_AVAILABLE',
                  20131: 'DRV_FPGA_VOLTAGE_ERROR', 20099: 'DRV_BINNING_ERROR', 20100: 'DRV_INVALID_AMPLIFIER',
                  20101: 'DRV_INVALID_COUNTCONVERT_MODE'}
        res = ''
        if code not in errors and user_def == '':
            res = f"Wrong code number {code}"
        elif user_def != '':
            res = user_def
        else:
            if code != 0:
                res = errors[code]
            else:
                res = user_def
        print(f'Error: {res}, Caller: {inspect.stack()[1].function} : {inspect.stack()[2].function}')
        return user_def


if __name__ == "__main__":
    DS_ANDOR_CCD.run_server()
    # Andor_test()