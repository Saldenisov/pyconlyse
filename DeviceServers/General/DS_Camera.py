from abc import abstractmethod
from tango import AttrWriteType, DevState, DevFloat, EncodedAttribute
from tango.server import Device, attribute, command, device_property
import numpy as np
from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any

from DeviceServers.General.DS_general import DS_General, standard_str_output


class DS_CAMERA_CCD(DS_General):
    RULES = {'set_param_after_init': [DevState.ON], 'start_grabbing': [DevState.ON],
             'stop_grabbing': [DevState.ON],
             **DS_General.RULES}

    serial_number = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    parameters = device_property(dtype=str)

    # Cameras' attributes
    @attribute(label="Friendly name", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ_WRITE)
    def camera_friendly_name(self):
        val = self.get_camera_friendly_name()
        self.friendly_name = val
        self.info(f'Friendly name of camera is read: {val}')
        return self.friendly_name

    def write_camera_friendly_name(self, value):
        self.info(f'Setting friendly name of camera to: {value}.', True)
        self.set_camera_friendly_name(value)

    @abstractmethod
    def get_camera_friendly_name(self) -> str:
        pass

    @abstractmethod
    def set_camera_friendly_name(self, value):
        pass

    @attribute(label="Serial number", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Serial number of camera.")
    def camera_serial_number(self):
        return self.get_camera_serial_number()

    @abstractmethod
    def get_camera_serial_number(self) -> Union[str, int]:
        pass

    @attribute(label='Model name', dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ)
    def camera_model_name(self):
        return self.get_camera_model_name()

    @abstractmethod
    def get_camera_model_name(self) -> str:
        pass

    @attribute(label='exposure time', dtype=float, access=AttrWriteType.READ_WRITE)
    def exposure_time(self):
        return self.get_exposure_time()

    def write_exposure_time(self, value: float):
        self.set_exposure_time(value)

    @abstractmethod
    def get_exposure_time(self) -> float:
        pass

    @abstractmethod
    def set_exposure_time(self, value: float):
        pass

    @attribute(label='exposure time min', dtype=float, access=AttrWriteType.READ)
    def exposure_min(self):
        return self.get_exposure_min()

    @abstractmethod
    def get_exposure_min(self):
        pass

    @attribute(label='exposure time max', dtype=float, access=AttrWriteType.READ)
    def exposure_max(self):
        return self.get_exposure_max()

    @abstractmethod
    def get_exposure_max(self):
        pass

    @attribute(label='gain', dtype=int, access=AttrWriteType.READ_WRITE)
    def gain(self):
        self.ggain = self.get_gain()
        return self.ggain

    def write_gain(self, value: int):
        self.set_gain(value)

    @abstractmethod
    def set_gain(self, value: int):
        pass

    @abstractmethod
    def get_gain(self) -> int:
        pass

    @attribute(label='gain min', dtype=int, access=AttrWriteType.READ)
    def gain_min(self):
        return self.get_gain_min()

    @abstractmethod
    def get_gain_min(self) -> int:
        pass

    @attribute(label='gain max', dtype=int, access=AttrWriteType.READ)
    def gain_max(self):
        return self.get_gain_max()

    @abstractmethod
    def get_gain_max(self) -> int:
        pass

    @attribute(label='width of the image', dtype=int, access=AttrWriteType.READ_WRITE)
    def width(self):
        return self.get_width()

    def write_width(self, value):
        self.set_width(value)

    @abstractmethod
    def get_width(self) -> int:
        pass

    @abstractmethod
    def set_width(self, value: int):
        pass

    @attribute(label='width min', dtype=int, access=AttrWriteType.READ)
    def width_min(self):
        return self.get_width_min()

    @abstractmethod
    def get_width_min(self):
        pass

    @attribute(label='width max', dtype=int, access=AttrWriteType.READ)
    def width_max(self):
        return self.get_width_max()

    @abstractmethod
    def get_width_max(self):
        pass

    @attribute(label='height of the image', dtype=int, access=AttrWriteType.READ_WRITE)
    def height(self):
        return self.get_height()

    def write_height(self, value: int):
        self.set_height(value)

    @abstractmethod
    def set_height(self, value: int):
        pass

    @abstractmethod
    def get_height(self) -> int:
        pass

    def turn_on_local(self) -> Union[int, str]:
        pass

    @attribute(label='height min', dtype=int, access=AttrWriteType.READ)
    def height_min(self):
        return self.get_height_min()

    @abstractmethod
    def get_height_min(self) -> int:
        pass

    @attribute(label='height max', dtype=int, access=AttrWriteType.READ)
    def height_max(self):
        return self.get_height_max()

    @abstractmethod
    def get_height_max(self) -> int:
        pass

    @attribute(label='offset x axis', dtype=int, access=AttrWriteType.READ_WRITE)
    def offsetX(self):
        return self.get_offsetX()

    def write_offsetX(self, value):
        self.set_offsetX(value)

    @abstractmethod
    def get_offsetX(self) -> int:
        pass

    @abstractmethod
    def set_offsetX(self, value: int):
        pass

    @attribute(label='offset y axis', dtype=int, access=AttrWriteType.READ_WRITE)
    def offsetY(self):
        return self.get_offsetY()

    def write_offsetY(self, value):
        self.set_offsetY(value)

    @abstractmethod
    def get_offsetY(self) -> int:
        pass

    @abstractmethod
    def set_offsetY(self, value: int):
        pass

    @attribute(label='pixel format', dtype=str, access=AttrWriteType.READ_WRITE)
    def format_pixel(self):
        return self.get_format_pixel()

    def write_format_pixel(self, value):
        self.set_format_pixel(value)

    @abstractmethod
    def set_format_pixel(self, value: str):
        pass

    @abstractmethod
    def get_format_pixel(self) -> str:
        pass

    @attribute(label='actual framerate', dtype=float, access=AttrWriteType.READ)
    def framerate(self):
        return self.get_framerate()

    @abstractmethod
    def get_framerate(self):
        pass

    @attribute(label='binning_horizontal', dtype=int, access=AttrWriteType.READ_WRITE)
    def binning_horizontal(self):
        return self.get_binning_horizontal()

    def write_binning_horizontal(self, value):
        self.set_binning_horizontal(value)

    @abstractmethod
    def set_binning_horizontal(self, value: int):
        pass

    @abstractmethod
    def get_binning_horizontal(self) -> int:
        pass

    @attribute(label='binning_vertical', dtype=int, access=AttrWriteType.READ_WRITE)
    def binning_vertical(self):
        return self.get_binning_vertical()

    def write_binning_vertical(self, value):
        self.set_binning_vertical(value)

    @abstractmethod
    def set_binning_vertical(self, value: int):
        pass

    @abstractmethod
    def get_binning_vertical(self) -> int:
        pass

    @attribute(label='sensor readout mode', dtype=str, access=AttrWriteType.READ)
    def sensor_readout_mode(self):
        return self.get_sensor_readout_mode()

    @abstractmethod
    def get_sensor_readout_mode(self) -> str:
        pass

    @attribute(label='Camera is grabbing?', dtype=bool, access=AttrWriteType.READ,
               polling_period=DS_General.polling_main)
    def isgrabbing(self):
        return self.grabbing

    @attribute(label='image', max_dim_x=4096, max_dim_y=4096, dtype=((DevFloat,),), access=AttrWriteType.READ)
    def image(self):
        self.get_image()
        self.info("Acquired")
        return self.last_image

    @abstractmethod
    def get_image(self):
        pass

    def init_device(self):
        self.latestimage = True
        self.last_image: np.array = None
        self.camera = None
        self.trigger_software = False
        super().init_device()
        self.parameters = eval(self.parameters)
        self.turn_on()
        self.set_param_after_init()

    def set_param_after_init(self):
        state_ok = self.check_func_allowance(self.set_param_after_init)
        if state_ok == 1:
            self.info(f"Setting parameters for {self.device_name}.", True)
            res = self.set_param_after_init_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Parameters for device {self.device_name} was set.", True)
        else:
            self.error(f"Setting parameters for {self.device_name} did not work, "
                       f"check state of the device {self.get_state()}.")

    @abstractmethod
    def set_param_after_init_local(self) -> Union[int, str]:
        pass

    @command
    def LatestImageOnly(self):
        self.info("Switching to grab mode Latest Image Only", True)
        self.latestimage = True

    @command
    def OneByOne(self):
        self.info("Switching to grab mode One By One", True)
        self.latestimage = False

    @command
    def start_grabbing(self):
        state_ok = self.check_func_allowance(self.start_grabbing)
        if state_ok == 1:
            self.info(f"Starting grabbing for {self.device_name}.", True)
            res = self.start_grabbing_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Grabbing is started for device {self.device_name}.", True)
        else:
            self.error(f"Starting grabbing for {self.device_name} did not work, "
                       f"check state of the device {self.get_state()}.")


    @abstractmethod
    def start_grabbing_local(self):
        pass

    @command
    def stop_grabbing(self):
        state_ok = self.check_func_allowance(self.start_grabbing)
        if state_ok == 1:
            self.info(f"Stopping grabbing for {self.device_name}.", True)
            res = self.stop_grabbing_local()
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Grabbing is stopped for device {self.device_name}.", True)
        else:
            self.error(f"Stopping grabbing for {self.device_name} did not work, "
                       f"check state of the device {self.get_state()}.")

    @abstractmethod
    def stop_grabbing_local(self):
        pass

    @property
    def grabbing(self):
        return self.grabbing_local()

    @abstractmethod
    def grabbing_local(self):
        pass
