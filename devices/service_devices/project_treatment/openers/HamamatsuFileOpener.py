'''
Created on 17 avr. 2015
"Read the Hamamatsu header,DATA, Time Delays and Wavelenghs for the given __filepath

@author: saldenisov
'''

import numpy as np
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Union, Tuple
from devices.service_devices.project_treatment.openers.Opener import Opener, CriticalInfo
from datastructures.mes_independent.measurments_dataclass import Measurement, Hamamatsu
from utilities.myfunc import error_logger


@dataclass
class CriticalInfoHamamatsu(CriticalInfo):
    bytes_per_point: int
    data_pos: int
    file_type: str
    number_maps: int
    header: str
    scaling_xscale: np.double
    scaling_xunit: str
    scaling_yscale: np.double
    scaling_yunit: str
    y_offset: int


class HamamatsuFileOpener(Opener):
    """
    Opener for '.img' and '.his' formats used by Hamamatsu STREAK-cameras,

    """

    def __init__(self, **kwargs):
        super().__init__()

    def read_critical_info(self, filepath: Path) -> CriticalInfoHamamatsu:
        try:
            pos = 0
            with open(filepath, 'rb') as file:
                head_64_bytes = bytearray(file.read(64))
                pos += 64
                comments_length = int.from_bytes(head_64_bytes[2:4], byteorder='little')
                #TODO: need to find where ends real header with text
                #TODO: need to understand what are the comments, how do they relate to datastructures
                header = file.read(4610).decode(encoding='utf-8')
                pos += comments_length
            file_type = self.get_img_type(header)
            # Set scales parameters
            scaling_xscale, scaling_xunit, scaling_yscale, scaling_yunit = self.set_scales_param(header)

            wavelengths_length = int.from_bytes(head_64_bytes[4:6], byteorder='little')
            timedelays_length = int.from_bytes(head_64_bytes[6:8], byteorder='little')
            y_offset = int.from_bytes(head_64_bytes[10:12], byteorder='little')
            # Bytes for 1 pixel
            pixel_size = int.from_bytes(head_64_bytes[12:14], byteorder='little')
            if pixel_size == 3:
                bytes_per_point = 4
            elif pixel_size == 2:
                bytes_per_point = 2
            elif pixel_size == 1:
                bytes_per_point = 1

            number_maps = int.from_bytes(head_64_bytes[14:16], byteorder='little')
            if number_maps == 0:
                number_maps = 1

            timedelays = self.get_timedelays_stat(filepath=filepath, header=header, file_type=file_type,
                                                  timedelays_length=timedelays_length,
                                                  scaling_yunit=scaling_yunit, scaling_yscale=scaling_yscale)

            wavelengths = self.get_wavelengths_stat(filepath=filepath, header=header, file_type=file_type,
                                                    wavelengths_length=wavelengths_length)

            return CriticalInfoHamamatsu(bytes_per_point=bytes_per_point, data_pos=pos, file_path=filepath,
                                         file_type=file_type,
                                         number_maps=number_maps, header=header, scaling_xscale=scaling_xscale,
                                         scaling_xunit=scaling_xunit, scaling_yscale=scaling_yscale,
                                         scaling_yunit=scaling_yunit, y_offset=y_offset,
                                         timedelays_length=timedelays_length, wavelengths_length=wavelengths_length,
                                         timedelays=timedelays, wavelengths=wavelengths)
        except Exception as e:
            error_logger(self, self.read_critical_info, e)

    @lru_cache(maxsize=50)
    def read_map(self, file_path: Path, map_index=0) -> Union[Hamamatsu, Tuple[bool, str]]:
        res = True
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        if res:
            info: CriticalInfoHamamatsu = self.paths[file_path]
            size_data_bytes = info.bytes_per_point * info.timedelays_length * info.wavelengths_length

            if (map_index + 1) >= info.number_maps:
                map_index = info.number_maps - 1
            elif map_index < 0:
                map_index = 0

            with open(file_path, 'rb') as file:
                file.seek(info.data_pos + 64 * map_index + map_index * size_data_bytes, 0)  # Shift pos
                data_bytearray = bytearray(file.read(size_data_bytes))

            # Data double array
            if info.bytes_per_point == 4:
                number_type = np.int32
            elif info.bytes_per_point == 2:
                number_type = np.int16
            elif info.bytes_per_point == 1:
                number_type = np.int8
            else:
                e = Exception(f'func: read_map Wrong bytes_per_point {info.bytes_per_point}')
                self.logger.error(e)
                raise e
            data_array = np.frombuffer(data_bytearray, dtype=number_type)
            data = data_array.reshape(info.timedelays_length, info.wavelengths_length)
            return Hamamatsu(type=file_path.suffix, comments=info.header, author='', timestamp=file_path.stat().st_mtime,
                             data=data, wavelengths=info.wavelengths, timedelays=info.timedelays,
                             time_scale=info.scaling_yunit)
        else:
            return False, comments

    def get_timedelays_stat(self, filepath: Path, header: str, file_type, timedelays_length,
                            scaling_yunit, scaling_yscale) -> np.array:

        if file_type == 'Normal':
            from_byte = int(header.split("ScalingYScalingFile=")[1][2:].split(",")[0])
            with open(filepath, 'rb') as file:
                file.seek(from_byte, 0)
                # Data byte array
                timedelays_bytes = bytearray(file.read(timedelays_length * 4))
            timedelays = np.frombuffer(timedelays_bytes, dtype=np.float32)

        else:
            divider = 1
            if scaling_yunit == 'ps':
                divider = 1000
            timedelays = [i * scaling_yscale / divider for i in range(timedelays_length)]
        return timedelays

    def get_wavelengths_stat(self,filepath: Path, header: str, file_type,
                             wavelengths_length) -> np.array:
        if file_type == 'Normal':
            from_ = int(header.split("ScalingXScalingFile=")[1][2:].split(",")[0])
            with open(filepath, 'rb') as file:
                file.seek(from_, 0)
                wavelengts_bytes = bytearray(file.read(wavelengths_length * 4))

            wavelengths = np.frombuffer(wavelengts_bytes, dtype=np.float32)
        else:
            wavelengths = np.arange(wavelengths_length)

        return wavelengths

    def get_img_type(self, header) -> str:
        type_ = 'Other'
        xscaling_file = header.split("ScalingXScalingFile=")[1][1:6]
        if xscaling_file != 'Other':
            return 'Normal'
        else:
            return 'Other'

    def give_all_maps(self, filepath) -> Union[Measurement, Tuple[bool, str]]:
        res = True
        if filepath not in self.paths:
            res, comments = self.fill_critical_info(filepath)
        if res:
            info: CriticalInfoHamamatsu = self.paths[filepath]
            for map_index in range(info.number_maps):
                yield self.read_map(filepath, map_index)
        else:
            return res, comments

    def give_pair_maps(self, filepath) -> Union[Tuple[Measurement], Tuple[bool, str]]:
        res = True
        if filepath not in self.paths:
            res, comments = self.fill_critical_info(filepath)
        if res:
            info: CriticalInfoHamamatsu = self.paths[filepath]
            for map_index in range(0, info.number_maps, 2):
                yield (self.read_map(filepath, map_index), self.read_map(filepath, map_index + 1))
        else:
            return res, comments

    def set_scales_param(self, header: str):
        scalingxscale = np.double(header.split("ScalingXScale=")[1].split(",")[0])
        scalingxunit = header.split("ScalingXUnit=")[1][1:].split(",")[0][:-1]

        if scalingxunit == "No unit":
            scalingxunit = 'pixel'

        scalingyscale = np.double(header.split("ScalingYScale=")[1].split(",")[0])
        scalingyunit = header.split("ScalingYUnit=")[1][1:3]

        return scalingxscale, scalingxunit, scalingyscale, scalingyunit
