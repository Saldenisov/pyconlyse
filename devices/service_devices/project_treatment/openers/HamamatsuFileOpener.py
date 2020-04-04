'''
Created on 17 avr. 2015
"Read the Hamamatsu header,DATA, Time Delays and Wavelenghs for the given __filepath

@author: saldenisov
'''

import struct
import numpy as np
import os
from dataclasses import dataclass
from pathlib import Path
from errors.myexceptions import NoSuchFileType
from utilities.data.datastructures.mes_independent.measurments_dataclass import Hamamatsu



import logging
module_logger = logging.getLogger(__name__)

@dataclass
class CriticalInfo:
    bytes_per_point: int
    data_pos: int
    file_type: str
    number_maps: int
    header: str
    scaling_xscale: np.double
    scaling_xunit: str
    scaling_yscale: np.double
    scaling_yunit: str
    timedelays: np.array
    wavelength: np.array


class HamamatsuFileOpener:
    """
    Opener for '.img' format used by STREAK-cameras,
    developped by Hamamatsu Corporation.

    Takes *.img file opens it and extract data,
    timedelays, wavelengths as numpy arrays
    """

    def __init__(self, filepath: Path, logger=None):
        if not logger:
            logger = module_logger
        self.logger = logger
        if filepath.suffix not in ['.img', '.his']:
            raise NoSuchFileType
        if not filepath.exists():
            raise FileExistsError
        self.filepath = filepath
        self.measurement: Hamamatsu = None
        self.read_header()

    def fill_criticial_info(self):
        pass

    def read_header(self) -> str:
        pos = 0
        with open(self.filepath, 'rb') as file:
            settings_header = bytearray(file.read(64))
            pos += 64
            # header string
            header_length = int.from_bytes(settings_header[2:4], byteorder='little')
            self.header = bytearray(file.read(header_length)).decode(encoding='UTF-8')
            pos += header_length
            self.data_pos = pos
            # Get file type
            self.file_type = self.get_img_type(self.header)

            # Set scales parameters
            self.scaling_xscale, self.scaling_xunit, self.scaling_yscale, self.scaling_yunit = self.set_scales_param(self.header)

            # Wavelength array size in pixels
            self.wavelengths_length = int.from_bytes(settings_header[4:6], byteorder='little')
            # Time array size in pixels
            self.timedelays_length = int.from_bytes(settings_header[6:8], byteorder='little')
            # Data size type
            pixel_size = int.from_bytes(settings_header[12:14], byteorder='little')
            if pixel_size == 3:
                self.bytes_per_point = 4
            elif pixel_size == 2:
                self.bytes_per_point = 2
            elif pixel_size == 1:
                self.bytes_per_point = 1

    def read_data(self, map_index=0) -> Hamamatsu:
        """
        Read .img or .his file and return one measurement
        :return:
        """
        # Size of data in bytes
        size_data_bytes = self.bytes_per_point * self.timedelays_length * self.wavelengths_length

        with open(self.filepath, 'rb') as file:
            file.seek(self.pos, 0)
            # Data byte array
            data_bytearray = bytearray(file.read(size_data_bytes))

        # Data double array
        data_array = np.frombuffer(data_bytearray, dtype='int32')
        self.__data = np.array(data_array.reshape(self.timedelays_length, self.wavelengths_length))


        # Arrays of wavelength and time-delays
        self.timedelays = self.get_timedelays_stat()



        self.wavelengths = self.get_wavelengths_stat()

    def get_timedelays_stat(self):
        timedelays = np.empty(self.timedelays_length)

        if self.file_type == 'Normal':
            from_ = int(self.header.split("ScalingYScalingFile=")[1][2:].split(",")[0])
            with open(self.filepath, 'rb') as file:
                file.seek(from_, 0)
                # Data byte array
                timedelays_bytes = bytearray(file.read(self.timedelays_length  * self.bytes_per_point))
            timedelays = [(struct.unpack('f', timedelays_bytes[i: i + self.bytes_per_point])[0])
                          for i in range(0, self.timedelays_length * self.bytes_per_point, self.bytes_per_point)]
        else:
            divider = 1
            if self.scalingyunit == 'ps':
                divider = 1000
            timedelays = [i * self.scalingyscale / divider for i in range(self.timedelays_length)]
        return np.array(timedelays)

    def get_wavelengths_stat(self):
        wavelengths = np.empty(self.wavelength_length)
        if self.file_type == 'Normal':
            from_ = int(self.header.split("ScalingXScalingFile=")[1][2:].split(",")[0])
            with open(self.filepath, 'rb') as file:
                file.seek(from_, 0)
                # Data byte array
                wavelengts_bytes = bytearray(file.read(self.wavelengths_length  * self.bytes_per_point))
            wavelengths = [struct.unpack('f', wavelengts_bytes[i: i + self.bytes_per_point])[0]
                           for i in range(0, self.wavelength_length * self.bytes_per_point, self.bytes_per_point)]
        else:
            wavelengths = np.arange(self.wavelength_length)

        return np.array(wavelengths)

    def get_img_type(self, header) -> str:
        type_ = 'Other'
        xscaling_file = header.split("ScalingXScalingFile=")[1][1:6]
        if xscaling_file != 'Other':
            return 'Normal'
        else:
            return 'Other'

    def set_scales_param(self, header: str):
        scalingxscale = np.double(header.split("ScalingXScale=")[1].split(",")[0])
        scalingxunit = header.split("ScalingXUnit=")[1][1:].split(",")[0][:-1]

        if scalingxunit == "No unit":
            scalingxunit = 'pixel'

        scalingyscale = np.double(header.split("ScalingYScale=")[1].split(",")[0])
        scalingyunit = header.split("ScalingYUnit=")[1][1:3]

        return scalingxscale, scalingxunit, scalingyscale, scalingyunit


# =============================================================================

Ham = HamamatsuFileOpener(Path('C:\\dev\\pyconlyse\\prev_projects\\DATAFIT\\test.img'))
a = Ham.read_data()
# =============================================================================