'''
Created on 23 avr. 2015

@author: saldenisov
'''

# import logging
import os
import logging
from functools import lru_cache
import numpy as np
from pathlib import Path
from typing import Union, Tuple
from datastructures.mes_independent import Measurement
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

    ALLOWED_FILES_TYPES = ['.his', '.img']

    def __init__(self, **kwargs):
        super().__init__()

    @lru_cache(maxsize=100)
    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        try:
            if file_path not in self.paths:
                timedelays = np.loadtxt(file_path)
                wavelength = np.loadtxt(file_path)
                return CriticalInfo(file_path, timedelays_length=len(timedelays), wavelengths_length=len(wavelength))
            else:
                return
        except Exception as e:
            error_logger(self, self.read_critical_info, e)


    def read_map(self, file_path: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        pass

    def give_all_maps(self, file_path) -> Union[Measurement, Tuple[bool, str]]:
        pass


def asciiopener(filepath):
    '''
    Works as an opener for datastructures files: '.csv' and (tab- and
    ',' seperated) '.txt' files
    Two columns datastructures and multicolumn datastructures used for TRABS representation
    Wavelength(first column) vs Timedelay (first row) -->
    0    0    1    2    3    4    5    ...
    400    0    0    0    0    0
    401    0    0    0    0    0
    402    0    0    0    0    0
    ...    0    0    0    0    0
    '''
    try:
        fileextension = os.path.splitext(filepath)[1]
        if fileextension not in ('.csv', '.txt', '.dat'):
            raise NoSuchFileType
        try:
            # try to open file with tab-sep delimiter
            with open(filepath, encoding='utf-8') as file:
                data = np.loadtxt(file)
        except ValueError:
            # in case of ',' delimiter try this
            try:
                with open(filepath, encoding='utf-8') as file:
                    data = np.loadtxt(file, delimiter=',')
            except ValueError:
                raise

        # in case of two columns datastructures: (X, Y)
        if data.shape[1] == 2:
            timedelays = data[:, 0]
            # adds wavelength array in order to present datastructures as a map
            N = 100
            wavelengths = np.arange(400, 400 + N +1, dtype=float)
            _data = np.transpose(np.repeat([data[:, 1]], N + 1, 0))

        # in case of matrix datastructures representation (e.g. TRABS)
        if data.shape[1] > 5:
            timedelays = np.delete(data[0], 0)
            wavelengths = np.delete(data[:, 0], 0)
            _data = np.delete(np.delete(data, 0, axis=0), 0, axis=1)
            _data = np.transpose(_data)

    except (FileNotFoundError, NoSuchFileType):
        raise
    return {'datastructures': _data,
            'timedelays': timedelays,
            'wavelengths': wavelengths}