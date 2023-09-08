from abc import abstractmethod
from typing import Union, Any
import zlib
import random
import string
import numpy as np
from tango import AttrWriteType, DispLevel, DevState, DevFloat
from tango.server import attribute, command, device_property
from dataclasses import dataclass
from time import time, time_ns
from DeviceServers.General.DS_general import DS_General
from collections import OrderedDict, deque
from typing import Dict
import ctypes
polling_infinite = 10000

from DeviceServers.General.DS_general import GeneralOrderInfo
from threading import Thread

@dataclass
class OrderInfo(GeneralOrderInfo):
    order_length: int
    order_array: np.ndarray


class DS_CAMERA(DS_General):
    RULES = {'set_param_after_init': [DevState.ON], 'start_grabbing': [DevState.ON],
             'stop_grabbing': [DevState.ON, DevState.FAULT, DevState.RUNNING],
             **DS_General.RULES}

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path = device_property(dtype=str)
    serial_number = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    parameters = device_property(dtype=str)

    def register_order_local(self, name, value):
        order_info = OrderInfo(order_length=value[0], order_done=False, order_timestamp=time(),
                               ready_to_delete=False, order_array=np.array([self.wavelengths]))
        self.orders[name] = order_info
        return 0

    def give_order_local(self, name) -> Any:
        res = self.last_image
        if name in self.orders:
            order = self.orders[name]
            order.ready_to_delete = True
            res = order.order_array
        res = res.astype(dtype=np.uint16)
        return res

    def init_device(self):
        self._dll_lock = True
        self.dll = None
        self.data_deque = deque(maxlen=1000)
        self.time_stamp_deque = deque(maxlen=1000)
        self.bg_measurement_value = 0
        self.serial_number_real = -1
        self.head_name = ''
        self.status_real = 0
        self.exposure_time_value = -1
        self.exposure_delay_value = -1
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

        self.trigger_type_value = 0
        self.trigger_source_value = 0
        self.trigger_mode_value = 0

        super().init_device()

    def load_dll(self):
        dll = ctypes.WinDLL(str(self.dll_path))
        self._dll_lock = False
        return dll


class DS_CAMERA_CCD(DS_CAMERA):
    RULES = {**DS_CAMERA.RULES}

    # Cameras' attributes
    @attribute(label="Friendly name", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ_WRITE)
    def device_friendly_name(self):
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

    @attribute(label='trigger delay', dtype=float, access=AttrWriteType.READ_WRITE)
    def trigger_delay(self):
        return self.get_trigger_delay()

    def write_trigger_delay(self, value):
        self.set_trigger_delay(value)

    @abstractmethod
    def set_trigger_delay(self, value: float):
        pass

    @abstractmethod
    def get_trigger_delay(self) -> float:
        pass

    @attribute(label='trigger mode', dtype=int, access=AttrWriteType.READ_WRITE)
    def trigger_mode(self):
        return self.get_trigger_mode()

    def write_trigger_mode(self, value):
        self.set_trigger_mode(value)

    @abstractmethod
    def set_trigger_mode(self, value):
        pass

    @abstractmethod
    def get_trigger_mode(self) -> int:
        pass

    @attribute(label='trigger source', dtype=int, access=AttrWriteType.READ_WRITE)
    def trigger_source(self):
        return self.get_trigger_source()

    def write_trigger_source(self, value):
        self.set_trigger_source(value)

    @abstractmethod
    def set_trigger_source(self, value):
        pass

    @abstractmethod
    def get_trigger_source(self) -> int:
        pass

    @attribute(label='trigger type', dtype=int, access=AttrWriteType.READ_WRITE)
    def trigger_type(self):
        return self.get_trigger_type()

    def write_trigger_type(self, value):
        self.set_trigger_type(value)

    @abstractmethod
    def set_trigger_type(self, value):
        pass

    @abstractmethod
    def get_trigger_type(self) -> int:
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

    @attribute(label='Give list of orders?', dtype=str, access=AttrWriteType.READ,
               polling_period=DS_General.polling_main)
    def orders_dict(self):
        return str(self.orders)

    @attribute(label='image', max_dim_x=4096, max_dim_y=4096, dtype=((DevFloat,),), access=AttrWriteType.READ)
    def image(self):
        self.get_image()
        self.info("Acquired")
        return self.last_image

    @attribute(label='Center of gravity', dtype=str, access=AttrWriteType.READ)
    def cg(self):
        return str(self.CG_position)

    @abstractmethod
    def get_image(self):
        pass

    def init_device(self):
        self.latestimage = True
        self.last_image: np.array = None
        self.trigger_software = False
        self.camera = None
        self.CG_position = {'X': 0, 'Y': 0}
        super().init_device()
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
        state_ok = self.check_func_allowance(self.stop_grabbing)
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

    def treat_orders(self, data2D: np.ndarray):
        for spectrum in data2D:
            time_stamp = time_ns()
            self.time_stamp_deque.append(time_stamp)
            self.data_deque.append(spectrum)

            data_archive = self.form_archive_data(spectrum.reshape((1, self.width)),
                                                  name='spectra', time_stamp=time_stamp, dt=np.uint16)
            # self.write_to_archive(data_archive)

            if self.orders:
                orders_to_delete = []
                for order_name, order_info in self.orders.items():
                    if (time() - order_info.order_timestamp) >= 100:
                        orders_to_delete.append(order_name)

                    elif not order_info.order_done:
                        order_info.order_array = np.vstack([order_info.order_array, spectrum])

                    if order_info.order_length == len(order_info.order_array) - 1:
                        order_info.order_done= True

                if orders_to_delete:
                    for order_name in orders_to_delete:
                        del self.orders[order_name]

