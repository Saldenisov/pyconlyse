#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Tuple, Union


import numpy as np
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output
from collections import OrderedDict
# -----------------------------

from tango.server import device_property, command
from tango import DevState
from pypylon import pylon, genicam


class DS_Basler_camera(DS_CAMERA_CCD):
    '''
    Basler
    This controls the connection to Basler Cameras. One can also see many of
    the properties form the camera as well as the image observed by it.
    Moreover, if the camera is configured for triggered image acquisition,
    you can trigger image captures at particular points in time (in timeoutt).

    There are two types of grab strategies: one by one (the images are
    processed in the order of their arrival) or latest only (The images are processed
    in the order of their arrival but only the last received image is kept in
    the output queue.This strategy can be useful when the acquired images are
    only displayed on the screen. If the processor has been busy for a while
    and images could not be displayed automatically the latest image is
    displayed when processing time is available again.).

    Sensor readout mode: normal (the readout time for each row of pixels
    remains unchanged), fast (the readout time for each row of pixels is
                              reduced, compared to normal readout. )
    '''
    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    ip_address = device_property(dtype=str)

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


if __name__ == "__main__":
    DS_Basler_camera.run_server()