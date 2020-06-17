'''
Created on 23 avr. 2015

@author: saldenisov
'''

# import logging
import logging
from functools import lru_cache
import numpy as np
from pathlib import Path
from typing import Union, Tuple
from utilities.datastructures.mes_independent import Measurement
from devices.service_devices.project_treatment.openers.Opener import Opener, CriticalInfo
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


class ASCIIOpener(Opener):
    """
    Opener for '.dat'
    0 wave1 wave2   wave3   ...   waveN
    timedelay1  X11   X12   X13 ... X14
    timedelay2  X21   X22   X23 ... X24
    timedelay3  X31   X32   X33 ... X34
    .........   ... ... ... ....    ...
    timedelayN  XN1   XN2   XN3 ... XN4
    """

    ALLOWED_FILES_TYPES = ['.dat', '.raw']

    def __init__(self, **kwargs):
        super().__init__()

    @lru_cache(maxsize=50)
    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        try:
            if file_path.suffix == '.dat':
                number_of_maps = 1
                data = np.loadtxt(file_path)
                timedelays = data[0][1:]
                wavelength = data[:,0][1:]
                return CriticalInfo(file_path, number_maps=number_of_maps, timedelays_length=len(timedelays),
                                    wavelengths_length=len(wavelength), timedelays=timedelays, wavelengths=wavelength)
            elif file_path.suffix == '.raw':
                raise Exception(f'Do not know how to handle {file_path.suffix} data file type.')  # !!!.raw files
            else:
                raise Exception(f'Do not know how to handle {file_path.suffix} data file type.')

        except Exception as e:
            error_logger(self, self.read_critical_info, e)
            raise e

    @lru_cache(maxsize=50)
    def read_map(self, file_path: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        else:
            res = True
        if res:
            info: CriticalInfo = self.paths[file_path]
            data = np.loadtxt(file_path)
            data = np.transpose(data[1:, 1:])
            return Measurement(type=file_path.suffix, comments='', author='', timestamp=file_path.stat().st_mtime,
                               data=data, wavelengths=info.wavelengths, timedelays=info.timedelays, time_scale='??'), ''
        return False, comments

    def give_all_maps(self, file_path) -> Union[Measurement, Tuple[bool, str]]:
        res = True
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        if res:
            info: CriticalInfo = self.paths[file_path]
            for map_index in range(info.number_maps):
                yield self.read_map(file_path, map_index)[0]
        else:
            return res, comments
