'''
Created on 23 avr. 2015

@author: saldenisov
'''

# import logging
import logging
from functools import lru_cache
from pathlib import Path
from typing import Union, Tuple

import numpy as np

from utilities.dataio.opener import Opener, CriticalInfo
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


class ASCIIOpener(Opener):
    """
    Opener for '.dat'

    Preferred layout::

        0 timedelay1 timedelay2 ... timedelayN
        wavelength1 X11 X12 ... X1N
        wavelength2 X21 X22 ... X2N

    Legacy files with wavelengths in the first row, timedelays in the first
    column, and a transposed body are also accepted.
    """

    ALLOWED_FILES_TYPES = ['.dat', '.raw']

    def __init__(self, **kwargs):
        super().__init__()

    @staticmethod
    def _axis_looks_like_wavelength(values: np.ndarray) -> bool:
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return False
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        return 150.0 <= minimum <= 2500.0 and 150.0 <= maximum <= 2500.0

    @classmethod
    def _read_dat(cls, file_path: Path):
        try:
            table = np.loadtxt(file_path)
        except ValueError:
            table = np.loadtxt(file_path, skiprows=1)

        row_header = np.asarray(table[0, 1:], dtype=float)
        col_header = np.asarray(table[1:, 0], dtype=float)
        body = np.asarray(table[1:, 1:], dtype=float)
        row_is_wavelength = cls._axis_looks_like_wavelength(row_header)
        col_is_wavelength = cls._axis_looks_like_wavelength(col_header)

        if row_is_wavelength and not col_is_wavelength:
            wavelengths = row_header
            timedelays = col_header
            data = body.transpose()
        else:
            wavelengths = col_header
            timedelays = row_header
            data = body

        return wavelengths, timedelays, data

    @lru_cache(maxsize=50)
    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        try:
            if file_path.suffix == '.dat':
                number_of_maps = 1
                wavelength, timedelays, _data = self._read_dat(file_path)
                return CriticalInfo(file_path, number_maps=number_of_maps, timedelays_length=len(timedelays),
                                    wavelengths_length=len(wavelength), timedelays=timedelays,
                                    wavelengths=wavelength, scaling_yunit='??')
            elif file_path.suffix == '.raw':
                raise Exception(f'Do not know how to handle {file_path.suffix} data file type.')  # !!!.raw files
            else:
                raise Exception(f'Do not know how to handle {file_path.suffix} data file type.')
        except ValueError as e:
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
            _wavelengths, _timedelays, data = self._read_dat(file_path)
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

    def average_map(self, file_path: Path, call_back_func=None):
        measurement, comments = self.read_map(file_path, 0)
        if measurement is False:
            raise ValueError(comments)
        if call_back_func:
            call_back_func(1, 1)
        return measurement.data
