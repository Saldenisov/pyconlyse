#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
from tango import AttrWriteType, DevState, DevFloat, EncodedAttribute
from tango.server import Device, attribute, command, device_property
from pypylon import pylon
from numpy import array


# -----------------------------

class BaslerCamera(Device):
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
    polling = 5000
    polling_infinite = 100000
    image = attribute(label='image', max_dim_x=4096,
                      max_dim_y=4096, dtype=((DevFloat,),), access=AttrWriteType.READ, polling_period=polling)

    serial_number = device_property(dtype="str")
    friendly_name = device_property(dtype="str")
    ip_address = device_property(dtype="str")

    real_serial_number = attribute(label='serial number', dtype="str", access=AttrWriteType.READ)

    model_name = attribute(label='model name', dtype="str", access=AttrWriteType.READ)

    exposure = attribute(label='exposure time', dtype="float",
                         access=AttrWriteType.READ_WRITE, memorized=True,
                         hw_memorized=False, polling_period=polling)

    exposure_min = attribute(label='exposure time min', dtype="float",
                             access=AttrWriteType.READ, polling_period=polling_infinite)

    exposure_max = attribute(label='exposure time max', dtype="float",
                             access=AttrWriteType.READ, polling_period=polling_infinite)

    gain = attribute(label='gain', dtype="int",
                     access=AttrWriteType.READ_WRITE, memorized=True,
                     hw_memorized=False, polling_period=polling)

    gain_min = attribute(label='gain min', dtype="int",
                         access=AttrWriteType.READ, polling_period=polling_infinite)

    gain_max = attribute(label='gain max', dtype="int",
                         access=AttrWriteType.READ, polling_period=polling_infinite)

    width = attribute(label='width of the image', dtype="int",
                      access=AttrWriteType.READ_WRITE, memorized=True,
                      hw_memorized=False, polling_period=polling)

    width_min = attribute(label='width min', dtype="int",
                          access=AttrWriteType.READ, polling_period=polling_infinite)

    width_max = attribute(label='width max', dtype="int",
                          access=AttrWriteType.READ, polling_period=polling_infinite)

    height = attribute(label='height of the image', dtype="int",
                       access=AttrWriteType.READ_WRITE, memorized=True,
                       hw_memorized=False, polling_period=polling)

    height_min = attribute(label='height min', dtype="int",
                           access=AttrWriteType.READ, polling_period=polling_infinite)

    height_max = attribute(label='height max', dtype="int",
                           access=AttrWriteType.READ, polling_period=polling_infinite)

    offsetX = attribute(label='offset x axis', dtype="int",
                        access=AttrWriteType.READ_WRITE, memorized=True,
                        hw_memorized=False, polling_period=polling)

    offsetY = attribute(label='offset y axis', dtype="int",
                        access=AttrWriteType.READ_WRITE, memorized=True,
                        hw_memorized=False, polling_period=polling)

    format_pixel = attribute(label='pixel format', dtype="str",
                             access=AttrWriteType.READ_WRITE, memorized=True,
                             hw_memorized=False, polling_period=polling)

    report_framerate = attribute(label='max framerate', dtype="float",
                                 access=AttrWriteType.READ, polling_period=polling_infinite)

    binning_horizontal = attribute(label='binning_horizontal', dtype="int",
                                   access=AttrWriteType.READ_WRITE, memorized=True,
                                   hw_memorized=False, polling_period=polling)

    binning_vertical = attribute(label='binning_vertical', dtype="int",
                                 access=AttrWriteType.READ_WRITE, memorized=True,
                                 hw_memorized=False, polling_period=polling)

    sensor_readout_mode = attribute(label='sensor readout mode', dtype="str",
                                    access=AttrWriteType.READ, polling_period=polling_infinite)

    timeoutt = 5000

    def init_device(self):
        # connect to camera
        Device.init_device(self)
        self.set_state(DevState.INIT)

        try:
            self.device = self.get_camera_device()
            if self.device is not None:
                instance = pylon.TlFactory.GetInstance()

                self.camera = pylon.InstantCamera(instance.CreateDevice(self.device))
                self.camera.Open()
            self.trigger_software = False
            self.latestimage = True
            print('Init was done to camera with serial: {:s}'.format(self.device.GetSerialNumber()))
            self.set_state(DevState.ON)
        except:
            print('Could not open camera')
            self.set_state(DevState.OFF)

    def get_camera_device(self):
        print('we get camera device')
        for device in pylon.TlFactory.GetInstance().EnumerateDevices():
            if device.GetSerialNumber() == self.serial_number:
                return device
        return None

    def read_real_serial_number(self):
        return self.device.GetSerialNumber()

    def read_model_name(self):
        print("polling now")
        return self.camera.GetDeviceInfo().GetModelName()

    def read_friendly_name(self):
        return self.camera.GetDeviceInfo().GetFriendlyName()

    def read_exposure(self):
        return self.camera.ExposureTimeAbs()

    def write_exposure(self, value):
        # if value < self.camera.ExposureTimeAbs.Min:
        #     print("exposure: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.ExposureTimeAbs.SetValue(self.camera.ExposureTimeAbs.Min)
        # if value > self.camera.ExposureTimeAbs.Max:
        #     print("exposure: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.ExposureTimeAbs.SetValue(self.camera.ExposureTimeAbs.Max)
        # else:
        self.camera.ExposureTimeAbs.SetValue(value)

    def read_exposure_min(self):
        return self.camera.ExposureTimeAbs.Min

    def read_exposure_max(self):
        return self.camera.ExposureTimeAbs.Max

    def read_gain(self):
        self.ggain = self.camera.GainRaw()
        return self.ggain

    def write_gain(self, value):
        # if value < self.camera.GainRaw.Min:
        #     print("gain: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.GainRaw.SetValue(self.camera.GainRaw.Min)
        # if value > self.camera.GainRaw.Max:
        #     print("gain: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.GainRaw.SetValue(self.camera.GainRaw.Max)
        # else:
        self.camera.GainRaw.SetValue(value)

    def read_width_min(self):
        return self.camera.Width.Min

    def read_width_max(self):
        return self.camera.Width.Max

    def read_height_min(self):
        return self.camera.Height.Min

    def read_height_max(self):
        return self.camera.Height.Max

    def read_gain_min(self):
        return self.camera.GainRaw.Min

    def read_gain_max(self):
        return self.camera.GainRaw.Max

    def read_format_pixel(self):
        return self.camera.PixelFormat()

    def write_format_pixel(self, value):
        if type(value) == str:
            self.camera.PixelFormat = value
        else:
            self.camera.PixelFormat = self.camera.PixelFormat()

    def read_width(self):
        return self.camera.Width()

    def write_width(self, value):
        # if value < self.camera.Width.Min:
        #     print("width: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.Width = self.camera.Width.Min
        # if value >self.camera.Width.Max:
        #     print("width: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.Width = self.camera.Width.Max
        # else:
        self.camera.Width = value

    def read_height(self):
        return self.camera.Height()

    def write_height(self, value):
        # if value < self.camera.Height.Min:
        #     print("height: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.Height = self.camera.Height.Min
        # if value > self.camera.Height.Max:
        #     print("height: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.Height = self.camera.Height.Max
        # else:
        self.camera.Height = value

    def read_offsetX(self):
        return self.camera.OffsetX()

    def write_offsetX(self, value):
        self.camera.OffsetX = value

    def read_offsetY(self):
        return self.camera.OffsetY()

    def write_offsetY(self, value):
        self.camera.OffsetY = value

    def read_report_framerate(self):
        return self.camera.ResultingFrameRateAbs()

    def read_binning_horizontal(self):
        return self.camera.BinningHorizontal()

    def write_binning_horizontal(self, value):
        # if value < self.camera.BinningHorizontal.Min:
        #     print("binning horizontal: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.BinningHorizontal = self.camera.BinningHorizontal.Min
        # if value > self.camera.BinningHorizontal.Max:
        #     print("binning horizontal: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.BinningHorizontal = self.camera.BinningHorizontal.Max
        # else:
        self.camera.BinningHorizontal = value

    def read_binning_vertical(self):
        return self.camera.BinningVertical()

    def write_binning_vertical(self, value):
        # if value < self.camera.BinningVertical.Min:
        #     print("binning vertical: The value you are trying to write is below the minimum allowed by the settings")
        #     self.camera.BinningVertical = self.camera.BinningVertical.Min
        # if value > self.camera.BinningVertical.Max:
        #     print("binning vertical: The value you are trying to write is above the maximum allowed by the settings")
        #     self.camera.BinningVertical = self.camera.BinningVertical.Max
        # else:
        self.camera.BinningVertical = value

    def read_sensor_readout_mode(self):
        return self.camera.SensorReadoutMode.GetValue()

    def read_image(self):
        self.debug_stream("trying to get the image")
        self.acquire_image()
        self.debug_stream("acquired")
        self.imagee = array(self.imagee)
        # print("this is image",type(self.imagee))
        return self.imagee

    # def read_image_encoded(self):
    # #maybe without the parentesis
    #     print("until here it is fine")
    #     self.acquire_image()
    #     self.debug_stream("acquired")
    #     self.imagee = array(self.imagee)
    #     print("the image is about to be encoded")
    #     encoded = EncodedAttribute().encode_gray8(self.imagee)
    #     print("the image is encoded")
    #     print(encoded)
    #     return encoded #self.imagee

    def acquire_image(self):
        self.trigger()
        return self.wait(self.timeoutt)

    def trigger(self):
        if self.trigger_software:
            self.camera.TriggerSoftware()
            print("the camera is successfully triggered")
        else:
            print('hardware trigger enabled')

    def wait(self, timeout):
        if not self.grabbing:
            self.start_grabbing()

        # maybe we could also set autoexposure
        if self.latestimage:
            print("Wait in Grab LatestImageOnly strategy")
            grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_Return)
            if grabResult.IsValid():
                self.debug_stream("we could grab result")
                self.imagee = grabResult.Array
                return True
            else:
                print("Could not grab result")
                return False  # print("could not grab latest")

        else:
            print("Wait in Grab OneByOne strategy")
            grabResult = self.camera.RetrieveResult(timeout, pylon.TimeoutHandling_Return)
            if grabResult.IsValid():
                image = grabResult.Array
                self.imagee = array(image)
                self.debug_stream("here is the image")
                return True
            else:
                return False

    def start_grabbing(self):
        if self.latestimage:
            print("Grabbing LatestImageOnly")
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        else:
            print("Grabbing OneByOne")
            self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

    @command()
    def stop_grabbing(self):
        print('Stopping Grabbing')
        self.camera.StopGrabbing()

    @command()
    def delete_device(self):
        try:
            print('Close connection to camera with serial: {:s}'.format(self.device.GetSerialNumber()))
            self.stop_grabbing()
            self.camera.Close()
        except:
            print('closing camera failed!')

    @property
    def grabbing(self):
        return self.camera.IsGrabbing()

    @command()
    def TriggerMode(self):
        print('Enabling hardware trigger')
        self.stop_grabbing()
        self.camera.TriggerMode = 'On'
        # now the only possible type of triggering is software triggering
        self.camera.TriggerSource = 'Software'
        self.trigger_software = True
        self.start_grabbing()
        pass

        # The trigger selected can be triggered by executing a TriggerSoftware command.
        '''
        https://docs.baslerweb.com/trigger-source#setting-a-software-trigger-source

        There are many different types of triggering (software and hardware for example)
        What Tobias set was to be able to select Line1 and Software triggering but
        now Line1 is not working:

        (set the triggersource to any of this values: Line1, Line2, Line3, 
        Line4: If available, the trigger selected can be triggered by applying 
        an electrical signal to I/O line 1, 2, 3, or 4.
        '''

    @command()
    def DisablingTriggerMode(self):
        print("disabling trigger mode")
        self.stop_grabbing()
        # Trigger signals are generated automatically by the camera.
        self.camera.TriggerMode = 'Off'
        self.trigger_software = False
        self.start_grabbing()
        pass

    @command()
    def SensorReadoutModeFast(self):
        self.camera.SensorReadoutMode.SetValue(self.SensorReadoutMode_Fast)

    @command()
    def LatestImageOnly(self):
        print("Switching to grab mode Latest Image Only")
        self.latestimage = True
        pass

    @command()
    def OneByOne(self):
        print("Switching to grab mode One By One")
        self.latestimage = False
        pass


if __name__ == "__main__":
    BaslerCamera.run_server()