from abc import abstractmethod

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, List
from taurus import Device

from DeviceServers.General.DS_general import DS_General, GeneralOrderInfo
from utilities.myfunc import ping
from dataclasses import dataclass
from typing import Dict
from bs4 import BeautifulSoup
import requests

@dataclass
class spectro_channel:
    ds_name: str
    ds: Device
    state: DevState = None

    def __post_init__(self):
        self.state = self.ds.state


class DS_AVANTES_SPECTRO(DS_General):
    """
    Device server for spectrograph using Avantes as a detection system with HAMAMATSU Flash-lamp for Gamma source
    Sync is done using arduino TTL generator code
    """
    RULES = {**DS_General.RULES}

    _version_ = '0.1'
    _model_ = 'AVANTES SPECTROMETER GAMMA-SOURCE'
    polling = 500

    signal_detector = device_property(dtype=str)  # tango name of AVANTES DS
    reference_detector = device_property(dtype=str)
    arduino_sync = device_property(dtype=str, default_value='10.20.30.47')

    @attribute(label='number of average', dtype=int, access=AttrWriteType.READ_WRITE)
    def number_average(self):
        return self.n_average

    def write_number_average(self, value: int):
       self.n_average = value

    @attribute(label='background measurement', dtype=int, access=AttrWriteType.READ_WRITE)
    def bg_measurement(self):
        return self.bg_measurement_value

    def write_bg_measurement(self, value: int):
        if value in [0, 1]:
            if value == 0:
                requests.get(url=self._arduino_addr_on)
            else:
                requests.get(url=self._arduino_addr_on_bg)
            self.get_arduino_state()

    @attribute(label='exposure time', dtype=float, access=AttrWriteType.READ_WRITE)
    def exposure_time(self):
        return self.exposure_time_value

    def write_exposure_time(self, value: float):
        self.exposure_time_value = value
        self.info(f'Exposure was set to {value}.', True)

    @attribute(label='measure every n sec', dtype=float, access=AttrWriteType.READ_WRITE)
    def every_n_sec(self):
        return self.every_n_sec_value

    def write_every_n_sec(self, value: float):
        self.every_n_sec_value = value
        self.info(f'Measure every n sec was set to {value}.', True)

    def init_device(self):
        super().init_device()
        self._set_channels()
        self.every_n_sec_value = 1
        self.exposure_time_value = 0.1  # ms
        self.n_average = 1
        self.bg_measurement_value = 0
        self.ttl_arduino_bool = False
        self._arduino_addr_on = f'http://{self.arduino_sync}/?status=LAMP+AND+AVANTES'
        self._arduino_addr_on_bg = f'http://{self.arduino_sync}/?status=ONLY+AVANTES'
        self._arduino_addr_off = f'http://{self.arduino_sync}/?status=OFF'
        self._arduino_state = f'http://{self.arduino_sync}/'
        self.set_arduino_bg()
        self.get_arduino_state()
        self.turn_on()

    def _set_channels(self):
        self.signal = spectro_channel(ds_name=self.signal_detector, ds=Device(self.signal_detector))
        self.reference = spectro_channel(ds_name=self.reference_detector, ds=Device(self.reference_detector))

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        arg_return = -1, ''
        self.info(f"Searching for Experiment device {self.device_name}", True)
        self._device_id_internal, self._uri = self.device_id, self.friendly_name.encode('utf-8')

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    def set_arduino_bg(self, state=True):
        if state:
            requests.get(url=self._arduino_addr_on_bg)
        else:
            requests.get(url=self._arduino_addr_on)
        self.get_arduino_state()

    def get_arduino_state(self):
        my_ttl_on_lamp = 0
        my_ttl_on_avantes = 0
        try:
            response = requests.get(url=self._arduino_state, timeout=2)
            if response.text:
                # Create a BeautifulSoup object to parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find the elements with labels for "my_ttl_on_lamp" and "my_ttl_on_avantes"
                label_for_lamp = soup.find('span', id='my_ttl_on_lamp')
                label_for_avantes = soup.find('span', id='my_ttl_on_avantes')

                # Get the values from the associated <span> elements
                my_ttl_on_lamp = int(label_for_lamp.text)
                my_ttl_on_avantes = int(label_for_avantes.text)
        except requests.exceptions.RequestException as e:
            self.error(e)
        finally:
            self.ttl_arduino_bool = [False, True][my_ttl_on_avantes]
            self.bg_measurement_value = my_ttl_on_lamp
            self.info(f'Arduino TTL: {self.ttl_arduino_bool}; Flash Lamp: {self.bg_measurement_value}', True)

    @command(doc_in='Measure BG', dtype_out=bool)
    def measure_bg(self):
        res = False
        self.set_arduino_bg(True)
        return res

    @command(doc_in='Measure Blank', dtype_out=bool)
    def measure_blank(self):
        res = False
        return res

    @command(doc_in='Measure Sample', dtype_out=bool)
    def measure_sample(self):
        res = False
        return res


if __name__ == "__main__":
    DS_AVANTES_SPECTRO.run_server()