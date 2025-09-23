"""
Created on 05 june 2024

@author: saldenisov
"""

# import logging
import logging
from functools import lru_cache
from pathlib import Path
from typing import Union, Tuple
import h5py
import numpy as np

from gui.controllers.openers.Opener import Opener, CriticalInfo
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.myfunc import error_logger
from utilities.errors.myexceptions import NoSuchFileType

module_logger = logging.getLogger(__name__)


class H5Opener(Opener):
    ALLOWED_FILES_TYPES = ['.h5']

    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        if file_path.suffix in self.ALLOWED_FILES_TYPES:
            with h5py.File(file_path, "r") as f:
                timedelays = np.array(f['timedelays'])
                wavelengths = np.array(f['wavelengths'])
                n_maps = f['raw_data'].shape[0]
                comments = f['metadata'].attrs['description']
            scalingyunit = comments.split("ScalingYUnit=")[1][1:3]
            return CriticalInfo(file_path=file_path,
                                timedelays_length=len(timedelays),
                                wavelengths_length=len(wavelengths),
                                timedelays=timedelays,
                                wavelengths=wavelengths,
                                number_maps=n_maps,
                                scaling_yunit=scalingyunit
                                )
        else:
            raise NoSuchFileType(file_path.suffix)

    def read_map(self, file_path: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        else:
            res = True
        if res:
            info: CriticalInfo = self.paths[file_path]
            with h5py.File(file_path, "r") as f:
                comments = f['metadata'].attrs['description']
                data = f['raw_data'][map_index]
            scalingyunit = comments.split("ScalingYUnit=")[1][1:3]
            return Measurement(type=file_path.suffix,
                               comments=comments,
                               author='',
                               timestamp=file_path.stat().st_mtime,
                               data=data,
                               wavelengths=info.wavelengths,
                               timedelays=info.timedelays,
                               time_scale=scalingyunit
                               ), ''
        else:
            return False, comments

    def average_map(self, file_path: Path, call_back_func=None):
        with h5py.File(file_path, "r") as f:
            data = np.array(f['raw_data'])
        return np.average(data, axis=0)

    def give_all_maps(self, file_path) -> Union[Measurement, Tuple[bool, str]]:
        res = True
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        if res:
            info: CriticalInfo = self.paths[file_path]
            with h5py.File(file_path, "r") as f:
                comments = f['metadata'].attrs['description']
                data = np.array(f['raw_data'])
            scalingyunit = comments.split("ScalingYUnit=")[1][1:3]
            for data_i in data:
                yield Measurement(type=file_path.suffix,
                                  comments=comments,
                                  author='',
                                  timestamp=file_path.stat().st_mtime,
                                  data=data_i,
                                  wavelengths=info.wavelengths,
                                  timedelays=info.timedelays,
                                  time_scale=scalingyunit
                                  )

        else:
            return res, comments