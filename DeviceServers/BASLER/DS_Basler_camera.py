#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
from typing import Tuple, Union
import os
from tango import AttrWriteType, DevState, DevFloat, EncodedAttribute
from tango.server import Device, attribute, command, device_property
from numpy import array
from DeviceServers.General.DS_Camera import DS_CAMERA_CCD
from DeviceServers.General.DS_general import standard_str_output

# -----------------------------

import random

from tango.server import Device, attribute, device_property, DeviceMeta, command, run
from tango import DebugIt, DispLevel, AttrWriteType, DevState
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
        self.camera.Width = value

    def get_width_min(self):
        return self.camera.Width.Min

    def get_width_max(self):
        return self.camera.Width.Max

    def set_height(self, value: int):
        self.camera.Height = value

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
        self.camera.PixelFormat = value

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
        self.camera: pylon.InstantCamera = None
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
            self.set_state(DevState.ON)
            self.get_camera_friendly_name()
            self.info(f"{self.device_name} was Opened.", True)
            return 0
        else:
            return f'Could not turn on camera it is opened already.' if self.camera else f'Could not turn on camera, ' \
                                                                                         f'because it does not exist.'

    def turn_off_local(self) -> Union[int, str]:
        if self.camera and self.camera.IsOpen():
            self.camera.Close()
            self.set_state(DevState.OFF)
            self.info(f"{self.device_name} was Closed.", True)
            return 0
        else:
            return f'Could not turn off camera it is closed already.' if self.camera else f'Could not turn on camera, ' \
                                                                                          f'because it does not exist.'

    def set_param_after_init_local(self) -> Union[int, str]:
        pass

    def _set_transport_layer_param(self) -> Union[int, str]:
        packet_size = self.parameters['Transport_Layer']['Packet_size']
        inter_packet_delay = self.parameters['Transport_Layer']['Inter-Packet_Delay']

        formed_parameters_dict = {'GevSCPSPacketSize': packet_size, 'GevSCPD': inter_packet_delay}
        if self.camera.IsOpen() and not self.grabbing:
            try:
                for param_name, param_value in formed_parameters_dict.items():
                    setattr(self.camera, param_name, param_value)
                return 0
            except (genicam.GenericException, Exception) as e:
                return f'Error appeared: {e} when setting parameter "{param_name}" for camera {self.device_name}.'
        else:
            return f'Basler_Camera {self.device_name} connected states {self.camera.IsOpen()} ' \
                   f'Camera grabbing status is {self.grabbing}'

    def _set_transport_layer(self):
        pass

    def _get_camera_device(self):
        for device in pylon.TlFactory.GetInstance().EnumerateDevices():
            if device.GetSerialNumber() == self.serial_number:
                return device
        return None

    def get_image(self):
        self.trigger()
        return self.wait(self.timeoutt)

    def trigger(self):
        if self.trigger_software:
            self.camera.TriggerSoftware()
            self.info("the camera is successfully triggered")
        else:
            print('hardware trigger enabled')

    def wait(self, timeout):
        if not self.grabbing:
            self.start_grabbing()

        # maybe we could also set autoexposure
        if self.latestimage:
            self.info("Wait in Grab LatestImageOnly strategy")
            grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_Return)
            if grabResult.IsValid():
                self.debug_stream("we could grab result")
                self.imagee = grabResult.Array
                return True
            else:
                print("Could not grab result")
                return False  # print("could not grab latest")

        else:
            self.info("Wait in Grab OneByOne strategy")
            grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_Return)
            if grabResult.IsValid():
                image = grabResult.Array
                self.imagee = array(image)
                self.debug_stream("here is the image")
                return True
            else:
                return False

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

    @command
    def start_grabbing(self):
        if self.latestimage:
            self.info("Grabbing LatestImageOnly")
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        else:
            self.info("Grabbing OneByOne")
            self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

    @command
    def stop_grabbing(self):
        self.info('Stopping Grabbing', True)
        self.camera.StopGrabbing()

    @command
    def delete_device(self):
        try:
            self.info(f'Close connection to camera with serial: {self.device.GetSerialNumber()}', True)
            self.stop_grabbing()
            self.camera.Close()
        except:
            self.error('closing camera failed!')

    @property
    def grabbing(self):
        return self.camera.IsGrabbing()

    @command(dtype_in=[float], doc_in='Input is axis_id: int', dtype_out=str, doc_out=standard_str_output)
    def trigger_mode(self, state, trigger_source):
        """"
        https://docs.baslerweb.com/trigger-source#setting-a-software-trigger-source

        There are many different types of triggering (software and hardware for example)
        What Tobias set was to be able to select Line1 and Software triggering but
        now Line1 is not working:

        (set the triggersource to any of this values: Line1, Line2, Line3,
        Line4: If available, the trigger selected can be triggered by applying
        an electrical signal to I/O line 1, 2, 3, or 4.
        """
        self.info('Enabling hardware trigger')
        self.stop_grabbing()
        state = 'On' if state else 'Off'
        self.camera.TriggerMode = 'On'
        # now the only possible type of triggering is software triggering
        self.camera.TriggerSource = 'Software'
        self.trigger_software = True
        self.start_grabbing()

        # The trigger selected can be triggered by executing a TriggerSoftware command.


    @command
    def SensorReadoutModeFast(self):
        self.camera.SensorReadoutMode.SetValue(self.SensorReadoutMode_Fast)

    @command
    def LatestImageOnly(self):
        self.info("Switching to grab mode Latest Image Only", True)
        self.latestimage = True

    @command
    def OneByOne(self):
        self.info("Switching to grab mode One By One", True)
        self.latestimage = False


if __name__ == "__main__":
    DS_Basler_camera.run_server()