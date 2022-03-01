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
from threading import Thread
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output
# -----------------------------

from tango.server import device_property, command
from tango import DevState


class DS_ANDOR_CCD(DS_CAMERA_CCD):
    RULES = {**DS_CAMERA_CCD.RULES}

    _version_ = '0.1'
    _model_ = 'ANDOR CCD'

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path = device_property(dtype=str)
    width = device_property(dtype=int)

    def init_device(self):
        self.dll = None
        self.serial_number_real = -1
        self.head_name = ''
        self.status_real = 0
        self.exposure_time = -1
        self.accumulate_time = -1
        self.kinetic_time = -1
        self.n_gains_max = 1
        self.gain_value = -1
        self.height_value = 256
        self.grabbing_thread = Thread(target=self.wait, args=[self.timeoutt])
        super().init_device()
        self.start_grabbing_local()

    def find_device(self) -> Tuple[int, str]:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.dll = self.load_dll()
            res = self._Initialize()
            if res:
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
        self._GetAcquisitionTimings()
        return self.exposure_time

    def set_exposure_time(self, value: float):
        self._SetExposureTime(value)

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
                self.info(f"{self.device_name} was Opened.", True)
                return 0
            else:
                self.info(f'Could not turn on camera, because it does not exist.', True)
                return res
        else:
            return f'Could not turn on camera it is opened already.'

    def turn_off_local(self) -> Union[int, str]:
        res = self._ShutDown()
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
        if self.get_state == DevState.ON:
            if self.grabbing:
                self.stop_grabbing()
            for param_name, param_value in formed_parameters_dict.items():
                func = getattr(self, f'Set{param_name}')
                res = func(*list(param_value))
                if res != True:
                    return f'Error appeared: {res} when setting parameter "{param_name}" for camera {self.device_name}.'
        else:
            return f'{self.device_name} state is {self.get_state()}.'

    def get_image(self):
        self.last_image = self.wait(self.timeoutt)

    def wait(self, timeout):
        pass
        # if not self.grabbing:
        #     self.start_grabbing()
        # try:
        #     grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_ThrowException)
        #     if grabResult.GrabSucceeded():
        #         image = self.converter.Convert(grabResult)
        #         grabResult.Release()
        #         image = np.ndarray(buffer=image.GetBuffer(),
        #                            shape=(image.GetHeight(), image.GetWidth(), 3),
        #                            dtype=np.uint16)
        #         # Convert 3D array to 2D for Tango to transfer it
        #         image2D = image.transpose(2, 0, 1).reshape(-1, image.shape[1])
        #         self.info('Image is received...')
        #         return image2D
        #     else:
        #         raise pylon.GenericException
        # except (pylon.GenericException, pylon.TimeoutException) as e:
        #     self.error(str(e))
        #     return np.arange(300).reshape(10, 10, 3)

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
        pass

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
    def load_dll(self):
        dll = ctypes.WinDLL(str(self.dll_path))
        return dll

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
        res = self.dll.GetAcquisitionTimings(ctypes.byref(exp_time), ctypes.byref(accumulate_time),
                                             ctypes.byref(kinetic_time))
        self.exposure_time = exp_time.value
        self.accumulate_time = accumulate_time.value
        self.kinetic_time = kinetic_time.value
        return True if res == 20002 else self._error_andor(res)

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
        mode = ctypes.c_int(mode)
        res = self.dll.SetTriggerMode(mode)
        return True if res == 20002 else self._error_andor(res)

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

    def _CoolerOff(self) -> Tuple[bool, str]:
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
        res = self.dll.CoolerOff()
        return True if res == 20002 else self._error_andor(res)

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

    def _GetStatus(self) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetStatus(int* status)
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
        status = ctypes.c_int(0)
        res = self.dll.GetStatus(ctypes.byref(status))
        self.status_real = status.value
        return True if res == 20002 else self._error_andor(res)

    def _GetAcquiredData(self, array: int, size: int) -> Tuple[bool, str]:

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
        serial_number = ctypes.c_int(0)
        res = self.dll.GetAcquiredData(ctypes.byref(array))
        self.array_real = array.value
        res = self.dll.GetAcquiredData(ctypes.byref(size))
        self.size_real = size.value
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
        print(f'Error: {res}, Caller: {inspect.stack()[1].function}')
        return user_def


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
        dll = ctypes.WinDLL(str(Path(self.dll_path)))
        return dll

    def _Initialize(self, dir="") -> Tuple[bool, str]:
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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
            return self._error(-1, user_def=f'Wrong mode {mode} for SetAcquisitionMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetAcquisitionMode(mode)
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

    def _SetPreAmpGain(self, index: int) -> Tuple[int, bool, str]:
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
        res = self.dll.SetVSSpeed(index)
        return True if res == 20002 else self._error(res)

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
            return self._error(-1, user_def=f'Wrong mode {mode} for SetTriggerMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetTriggerMode(mode)
        return True if res == 20002 else self._error(res)

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
            return self._error(-1, user_def=f'Wrong mode {mode} for SetFastExtTrigger. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetFastExtTrigger(mode)
        return True if res == 20002 else self._error(res)

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
            return self._error(-1, user_def=f'Wrong mode {mode} for SetReadMode. MODES: {MODES}')
        mode = ctypes.c_int(mode)
        res = self.dll.SetReadMode(mode)
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

    def _CoolerOff(self) -> Tuple[bool, str]:
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
        res = self.dll.CoolerOff()
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

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
        return True if res == 20002 else self._error(res)

    def _GetStatus(self, status: int) -> Tuple[bool, str]:
        """
        unsigned int WINAPI GetStatus(int* status)
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
    DS_ANDOR_CCD.run_server()
    # Andor_test()