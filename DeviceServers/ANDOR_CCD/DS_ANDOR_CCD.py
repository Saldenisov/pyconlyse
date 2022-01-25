#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union
import ctypes
import inspect

import numpy as np
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output
from collections import OrderedDict
# -----------------------------

from tango.server import device_property, command
from tango import DevState
from pypylon import pylon, genicam



class DS_ANDOR_CCD(DS_CAMERA_CCD):

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path= device_property(dtype=str)

    def get_camera_friendly_name(self):
        return self.camera.DeviceUserID.GetValue()

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)
        self.camera.DeviceUserID.SetValue(str(value))

    def get_camera_serial_number(self) -> Union[str, int]:
        return self.device.GetSerialNumber()

    def get_camera_model_name(self) -> str:
        return self.camera.GetDeviceInfo().GetModelName()

    def get_exposure_time(self) -> float:
        return self.camera.ExposureTimeAbs()

    def set_exposure_time(self, value: float):
        self.camera.ExposureTimeAbs.SetValue(value)

    def set_trigger_delay(self, value: str):
        self.camera.TriggerDelayAbs.SetValue(value)

    def get_trigger_delay(self) -> str:
        return self.camera.TriggerDelayAbs()

    def get_exposure_min(self):
        return self.camera.ExposureTimeAbs.Min

    def get_exposure_max(self):
        return self.camera.ExposureTimeAbs.Max

    def set_gain(self, value: int):
        self.camera.GainRaw.SetValue(value)

    def get_gain(self) -> int:
        return self.camera.GainRaw()

    def get_gain_min(self) -> int:
        return self.camera.GainRaw.Min

    def get_gain_max(self) -> int:
        return self.camera.GainRaw.Max

    def get_width(self) -> int:
        return self.camera.Width()

    def set_width(self, value: int):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing
        self.camera.Width.SetValue(value)
        if was_grabbing:
            self.start_grabbing

    def get_width_min(self):
        return self.camera.Width.Min

    def get_width_max(self):
        return self.camera.Width.Max

    def set_height(self, value: int):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing
        self.camera.Height.SetValue(value)
        if was_grabbing:
            self.start_grabbing

    def get_height(self) -> int:
        return self.camera.Height()

    def get_height_min(self):
        return self.camera.Height.Min

    def get_height_max(self):
        return self.camera.Height.Max

    def get_offsetX(self) -> int:
        return self.camera.OffsetX()

    def set_offsetX(self, value: int):
        self.camera.OffsetX = value

    def get_offsetY(self) -> int:
        return self.camera.OffsetY()

    def set_offsetY(self, value: int):
        self.camera.OffsetY = value

    def set_format_pixel(self, value: str):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing()
        self.camera.PixelFormat = value
        if was_grabbing:
            self.start_grabbing()

    def get_format_pixel(self) -> str:
        return self.camera.PixelFormat()

    def get_framerate(self):
        return self.camera.ResultingFrameRateAbs()

    def set_binning_horizontal(self, value: int):
        self.camera.BinningHorizontal = value

    def get_binning_horizontal(self) -> int:
        return self.camera.BinningHorizontal()

    def set_binning_vertical(self, value: int):
        self.camera.BinningVertical = value

    def get_binning_vertical(self) -> int:
        return self.camera.BinningVertical()

    def get_sensor_readout_mode(self) -> str:
        return self.camera.SensorReadoutMode.GetValue()

    def init_device(self):
        self.pixel_format = None
        self.camera: pylon.InstantCamera = None
        self.converter: pylon.ImageFormatConverter = None
        self.device = None
        super().init_device()

    def find_device(self) -> Tuple[int, str]:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.device = self._get_camera_device()
            if self.device is not None:
                try:
                    instance = pylon.TlFactory.GetInstance()
                    self.camera = pylon.InstantCamera(instance.CreateDevice(self.device))
                    self.turn_on_local()
                    argreturn = 1, str(self.camera.GetDeviceInfo().GetSerialNumber()).encode('utf-8')
                except Exception as e:
                    self.error(f'Could not open camera. {e}')
            else:
                self.error(f'Could not find camera.')
            self._device_id_internal, self._uri = argreturn
            return argreturn

    def turn_on_local(self) -> Union[int, str]:
        if self.camera and not self.camera.IsOpen():
            self.camera.Open()
            self.converter = pylon.ImageFormatConverter()
            self.set_state(DevState.ON)
            self.get_camera_friendly_name()
            self.info(f"{self.device_name} was Opened.", True)
            return 0
        else:
            return f'Could not turn on camera it is opened already.' if self.camera else f'Could not turn on camera, ' \
                                                                                         f'because it does not exist.'

    def turn_off_local(self) -> Union[int, str]:
        if self.camera and self.camera.IsOpen():
            if self.grabbing:
                self.stop_grabbing()
            self.camera.Close()
            self.set_state(DevState.OFF)
            self.info(f"{self.device_name} was Closed.", True)
            return 0
        else:
            return f'Could not turn off camera it is closed already.' if not self.camera.IsOpen() \
                else f'Could not turn on camera, because it does not exist.'

    def set_param_after_init_local(self) -> Union[int, str]:
        functions = [self.set_transport_layer, self.set_analog_controls, self.set_aio_controls,
                     self.set_acquisition_controls, self.set_image_format]
        results = []
        for func in functions:
            results.append(func())
        results_s = ''
        for res in results:
            if res != 0:
                results_s = results_s + res
        return results_s if results_s else 0

    def set_acquisition_controls(self):
        exposure_time = self.parameters['Acquisition_Controls']['ExposureTimeAbs']
        trigger_mode = self.parameters['Acquisition_Controls']['TriggerMode']
        trigger_delay = self.parameters['Acquisition_Controls']['TriggerDelayAbs']
        frame_rate = self.parameters['Acquisition_Controls']['AcquisitionFrameRateAbs']
        trigger_source = self.parameters['Acquisition_Controls']['TriggerSource']
        formed_parameters_dict = {'TriggerSource': trigger_source, 'TriggerMode': trigger_mode,
                                  'TriggerDelayAbs': trigger_delay, 'ExposureTimeAbs': exposure_time,
                                  'AcquisitionFrameRateAbs': frame_rate, 'AcquisitionFrameRateEnable': True}
        if trigger_mode == 'Trigger Software':
            self.trigger_software = True
        return self._set_parameters(formed_parameters_dict)

    def set_transport_layer(self) -> Union[int, str]:
        packet_size = self.parameters['Transport_layer']['Packet_size']
        inter_packet_delay = self.parameters['Transport_layer']['Inter-Packet_Delay']
        formed_parameters_dict = {'GevSCPSPacketSize': packet_size, 'GevSCPD': inter_packet_delay}
        return self._set_parameters(formed_parameters_dict)

    def set_analog_controls(self):
        gain_mode = self.parameters['Analog_Controls']['GainAuto']
        gain = self.parameters['Analog_Controls']['GainRaw']
        blacklevel = self.parameters['Analog_Controls']['BlackLevelRaw']
        balance_ratio = self.parameters['Analog_Controls']['BalanceRatioRaw']
        formed_parameters_dict_analog_controls = {'GainAuto': gain_mode, 'GainRaw': gain, 'BlackLevelRaw': blacklevel,
                                                  'BalanceRatioRaw': balance_ratio}
        return self._set_parameters(formed_parameters_dict_analog_controls)

    def set_aio_controls(self):
        width = self.parameters['AOI_Controls']['Width']
        height = self.parameters['AOI_Controls']['Height']
        offset_x = self.parameters['AOI_Controls']['OffsetX']
        offset_y = self.parameters['AOI_Controls']['OffsetY']
        formed_parameters_dict_AOI = OrderedDict()
        formed_parameters_dict_AOI['Width'] = width
        formed_parameters_dict_AOI['Height'] = height
        formed_parameters_dict_AOI['OffsetX'] = offset_x
        formed_parameters_dict_AOI['OffsetY'] = offset_y
        return self._set_parameters(formed_parameters_dict_AOI)

    def set_image_format(self):
        pixel_format = self.parameters['Image_Format_Control']['PixelFormat']
        formed_parameters_dict_image_format = {'PixelFormat': pixel_format}
        # to change, what if someone wants color converter
        self.converter.OutputPixelFormat = pylon.PixelType_RGB16packed
        # self.converter.OutputPixelFormat = pylon.PixelType_Mono8
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        return self._set_parameters(formed_parameters_dict_image_format)

    def _set_parameters(self, formed_parameters_dict):
        if self.camera.IsOpen():
            if self.grabbing:
                self.stop_grabbing()
            try:
                for param_name, param_value in formed_parameters_dict.items():
                    setattr(self.camera, param_name, param_value)
                return 0
            except (genicam.GenericException, Exception) as e:
                return f'Error appeared: {e} when setting parameter "{param_name}" for camera {self.device_name}.'
        else:
            return f'Basler_Camera {self.device_name} connected states {self.camera.IsOpen()} ' \
                   f'Camera grabbing status is {self.grabbing}.'

    def _get_camera_device(self):
        for device in pylon.TlFactory.GetInstance().EnumerateDevices():
            if device.GetSerialNumber() == self.serial_number:
                return device
        return None

    def get_image(self):
        self.last_image = self.wait(self.timeoutt)

    def wait(self, timeout):
        if not self.grabbing:
            self.start_grabbing()
        try:
            grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_ThrowException)
            if grabResult.GrabSucceeded():
                image = self.converter.Convert(grabResult)
                grabResult.Release()
                image = np.ndarray(buffer=image.GetBuffer(),
                                   shape=(image.GetHeight(), image.GetWidth(), 3),
                                   dtype=np.uint16)
                # Convert 3D array to 2D for Tango to transfer it
                image2D = image.transpose(2, 0, 1).reshape(-1, image.shape[1])
                self.info('Image is received...')
                return image2D
            else:
                raise pylon.GenericException
        except (pylon.GenericException, pylon.TimeoutException) as e:
            self.error(str(e))
            return np.arange(300).reshape(10, 10, 3)

    def get_controller_status_local(self) -> Union[int, str]:
        r = 0
        if self.camera.IsOpen():
            self.set_status(DevState.ON)
        else:
            a = os.system('ping -c 1 -n 1 -w 1 ' + str(self.ip_address))
            if a == 0:
                self.set_status(DevState.OFF)
            else:
                self.set_status(DevState.FAULT)
                r = f'{self.ip_address} is not reachable.'
        return r

    def start_grabbing_local(self):
        if self.latestimage:
            try:
                self.info("Grabbing LatestImageOnly", True)
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                return 0
            except Exception as e:
                return str(e)
        else:
            try:
                self.info("Grabbing OneByOne", True)
                self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
                return 0
            except Exception as e:
                return str(e)

    def stop_grabbing_local(self):
        try:
            self.camera.StopGrabbing()
            return 0
        except Exception as e:
            return str(e)

    def grabbing_local(self):
        if self.camera:
            return self.camera.IsGrabbing()
        else:
            return False

    @command(dtype_in=int, doc_in='state 1 or 0', dtype_out=str, doc_out=standard_str_output)
    def set_trigger_mode(self, state):
        state = 'On' if state else 'Off'
        self.info(f'Enabling hardware trigger: {state}', True)
        restart = False
        if self.grabbing:
            self.stop_grabbing()
            restart = True
        try:
            print(self.camera)
            self.camera.TriggerMode = state
        except Exception as e:
            self.error(e)
            return str(e)
        if restart:
            self.start_grabbing()
        return str(0)

    # DLL functions


class Andor_test():

    def __init__(self):
        self.n_ad_channels = None
        self.serial_number_real = None

        from pathlib import Path
        self.dll_path = Path('C:/dev/pyconlyse/DeviceServers/ANDOR_CCD/atmcd32d.dll')
        self.dll = self.load_dll()

        self._Initialize()
        func = [self._GetCameraSerialNumber(), self._GetNumberADChannels(), self._SetAcquisitionMode(3),
                self._SetExposureTime(0.0001),
                self._SetHSSpeed(0, 1), self._SetVSSpeed(1), self._SetADChannel(1), self._SetPreAmpGain(0),
                self._SetTriggerMode(1), self._SetFastExtTrigger(0), self._SetReadMode(1),
                self._SetMultiTrack(2, 128, 0), self._SetBaselineClamp(1), self._SetTemperature(-80), self._CoolerON(),
                self._ShutDown()]

        results = []

        for f in func:
            results.append(f)

        print(results)


    """
    INIT
    1) uint32_t Initialize(const CStr directory); DONE
    2) uint32_t SetAcquisitionMode(int32_t mode); DONE
    3) uint32_t SetExposureTime(float time); DONE
    4) uint32_t SetHSSpeed(int32_t type, int32_t index); DONE
    5) uint32_t SetVSSpeed(int32_t index); DONE
    6) uint32_t SetADChannel(int32_t channel); DONE
    7) uint32_t SetPreAmpGain(int32_t index); DONE
    8) uint32_t SetTriggerMode(int32_t mode); DONE
    9) uint32_t SetFastExtTrigger(int32_t mode); DONE
    10) uint32_t SetReadMode(int32_t mode); DONE
    11) uint32_t SetMultiTrack(int32_t number, int32_t height, int32_t offset, int32_t *bottom, int32_t *gap); DONE 
    12) uint32_t SetBaselineClamp(int32_t state); True
    13) uint32_t SetTemperature(int32_t temperature); -50
    14) uint32_t CoolerON(void );
    
    READ RAW
    1) uint32_t SetNumberKinetics(int32_t number);
    2) uint32_t PrepareAcquisition(void );
    3) uint32_t StartAcquisition(void );
    4) uint32_t GetStatus(int32_t *status);
    5) uint32_t GetAcquiredData(int32_t *array, uint32_t size);
    """

    def load_dll(self):
        dll = ctypes.WinDLL(str(self.dll_path))
        return dll

    def _Initialize(self, dir="") -> Tuple[bool, str]:
        dir_char = ctypes.c_char_p(dir.encode('utf-8'))
        res = self.dll.Initialize(dir_char)
        return True if res == 20002 else self._error(res)

    def _GetCameraSerialNumber(self) -> Tuple[bool, str]:
        serial_number = ctypes.c_int(0)
        res = self.dll.GetCameraSerialNumber(ctypes.byref(serial_number))
        self.serial_number_real = serial_number.value
        return True if res == 20002 else self._error(res)

    def _GetNumberADChannels(self):
        n_ad_channels = ctypes.c_int(0)
        res = self.dll.GetNumberADChannels(ctypes.byref(n_ad_channels))
        self.n_ad_channels = n_ad_channels.value
        return True if res == 20002 else self._error(res)

    def _SetAcquisitionMode(self, mode: int) -> Tuple[bool, str]:
        """
        mode:
            1 Single Scan
            2 Accumulate
            3 Kinetics
            4 Fast Kinetics
            5 Run till abort
        """
        MODES = {1: 'Single Scan', 2: 'Accumulate', 3: 'Kinetics', 4: 'Fast Kinetics', 5: 'Run Till abort'}
        if mode not in MODES:
            return self._error(-1, user_def=f'Wrong mode {mode} for SetAcquisitionMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetAcquisitionMode(mode)
        return True if res == 20002 else self._error(res)

    def _SetExposureTime(self, exp_time: float) -> Tuple[bool, str]:
        exp_time = ctypes.c_float(exp_time)
        res = self.dll.SetExposureTime(exp_time)
        return True if res == 20002 else self._error(res)

    def _SetHSSpeed(self, typ: int, index: int) -> Tuple[bool, str]:
        typ = ctypes.c_int(typ)
        index = ctypes.c_int(index)
        res = self.dll.SetHSSpeed(typ, index)
        return True if res == 20002 else self._error(res)

    def _SetVSSpeed(self, index: int) -> Tuple[bool, str]:
        index = ctypes.c_int(index)
        res = self.dll.SetVSSpeed(index)
        return True if res == 20002 else self._error(res)

    def _SetADChannel(self, channel: int) -> Tuple[bool, str]:
        channel = ctypes.c_int(channel)
        res = self.dll.SetADChannel(channel)
        return True if res == 20002 else self._error(res)

    def _SetPreAmpGain(self, index: int) -> Tuple[int, bool, str]:
        index = ctypes.c_int(index)
        res = self.dll.SetVSSpeed(index)
        return True if res == 20002 else self._error(res)

    def _SetTriggerMode(self, mode: int) -> Tuple[int, bool, str]:

        MODES = {0: 'Internal', 1: 'External', 6: 'External Start', 7: 'External Exposure (Bulb)', 9: 'External FVB EM (only valid for EM Newton models in FVB mode', 10: 'Software Trigger', 12: 'External Charge Shifting'}
        if mode not in MODES:
            return self._error(-1, user_def=f'Wrong mode {mode} for SetTriggerMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetTriggerMode(mode)
        return True if res == 20002 else self._error(res)

    def _SetFastExtTrigger(self, mode: int) -> Tuple[int, bool, str]:

        MODES = {0: 'Disabled', 1: 'Enabled'}
        if mode not in MODES:
            return self._error(-1, user_def=f'Wrong mode {mode} for SetFastExtTrigger. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetFastExtTrigger(mode)
        return True if res == 20002 else self._error(res)

    def _SetReadMode(self, mode: int) -> Tuple[int, bool, str]:

        MODES = {0: 'Full Vertical Binning', 1: 'Multi-Track', 2: 'Random-Track', 3: 'Single-Track', 4: 'Image'}
        if mode not in MODES:
            return self._error(-1, user_def=f'Wrong mode {mode} for SetReadMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetReadMode(mode)
        return True if res == 20002 else self._error(res)

    def _SetMultiTrack(self, typ: int, index: int, offset: int, bottom=0, gap=0) -> Tuple[int, bool, str]:
        """
        Description This function will set the multi-Track parameters. The tracks are automatically spread
        evenly over the detector. Validation of the parameters is carried out in the following
        order:
        - Number of tracks,
        - Track height
        - Offset.
        The first pixels row of the first track is returned via ‘bottom’.
        The number of rows between each track is returned via ‘gap’.
        Parameters int number: number tracks
        Valid values 1 to number of vertical pixels
        int height: height of each track
        Valid values >0 (maximum depends on number of tracks)
        int offset: vertical displacement of tracks
        Valid values depend on number of tracks and track height
        int* bottom: first pixels row of the first track
        int* gap: number of rows between each track (could be 0)
        """
        typ = ctypes.c_int(typ)
        index = ctypes.c_int(index)
        offset = ctypes.c_int(offset)
        bottom = ctypes.byref(ctypes.c_int(bottom))
        gap = ctypes.byref(ctypes.c_int(gap))
        res = self.dll.SetMultiTrack(typ, index, offset, bottom, gap)
        return True if res == 20002 else self._error(res)

    def _SetBaselineClamp(self, state: int) -> Tuple[int, bool, str]:
        state = ctypes.c_int(state)
        res = self.dll.SetBaselineClamp(state)
        return True if res == 20002 else self._error(res)

    def _SetTemperature(self, temperature: int) -> Tuple[bool, str]:
        temperature = ctypes.c_int(temperature)
        res = self.dll.SetTemperature(temperature)
        return True if res == 20002 else self._error(res)

    def _CoolerON(self) -> Tuple[bool, str]:
        res = self.dll.CoolerON()
        return True if res == 20002 else self._error(res)

    def _CoolerOff(self) -> Tuple[bool, str]:
        res = self.dll.CoolerOff()
        return True if res == 20002 else self._error(res)

    def _ShutDown(self):
        res = self.dll.ShutDown()
        return True if res == 20002 else self._error(res)

    def _SetNumberKinetics(self, number: int) -> Tuple[int, bool, str]:
        """
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
        return True if res == 20002 else self._error(res)

    def _PrepareAcquisition(self) -> Tuple[bool, str]:
        """
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
        return True if res == 20002 else self._error(res)

    def _StartAcquisition(self) -> Tuple[bool, str]:
        """
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
        return True if res == 20002 else self._error(res)

    def _GetStatus(self, status: int) -> Tuple[bool, str]:
    """
    Description         This function will return the current status of the Andor SDK system. This function should
                        be called before an acquisition is started to ensure that it is IDLE and during an acquisition
                        to monitor the process.
    Parameters          int* status: current status
                        DRV_IDLE                    IDLE waiting on instructions.
                        DRV_TEMPCYCLE               Executing temperature cycle.
                        DRV_ACQUIRING               Acquisition in progress.
                        DRV_ACCUM_TIME_NOT_MET      Unable to meet Accumulate cycle time.
                        DRV_KINETIC_TIME_NOT_MET    Unable to meet Kinetic cycle time.
                        DRV_ERROR_ACK               Unable to communicate with card.
                        DRV_ACQ_BUFFER              Computer unable to read the data via the ISA slot
                                                    at the required rate.
                        DRV_ACQ_DOWNFIFO_FULL       Computer unable to read data fast enough to stop
                                                    camera memory going full.
                        DRV_SPOOLERROR              Overflow of the spool buffer.
    Return              unsigned int
                        DRV_SUCCESS                 Status returned
                        DRV_NOT_INITIALIZED         System not initialized
    """
    serial_number = ctypes.c_int(0)
    res = self.dll.GetStatus(ctypes.byref(status))
    self.status_real = status.value
    return True if res == 20002 else self._error(res)

    def _GetAcquiredData(self, array: int, size: int) -> Tuple[bool, str]:

        """
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
    serial_number = ctypes.c_int(0)
    res = self.dll.GetAcquiredData(ctypes.byref(array))
    self.array_real = array.value
    res = self.dll.GetAcquiredData(ctypes.byref(size))
    self.size_real = size.value
    return True if res == 20002 else self._error(res)



    def _error(self, code: int, user_def='') -> str:
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
        print(f'Error: {res}, Caller: {inspect.stack()[1].function}')
        return user_def



if __name__ == "__main__":
    # DS_ANDOR_CCD.run_server()
    a = Andor_test()