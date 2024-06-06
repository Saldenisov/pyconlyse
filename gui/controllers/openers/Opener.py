"""
Created on 17 avr. 2015

@author: saldenisov 
"""

import logging
from abc import abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Union, Tuple

import numpy as np

from utilities.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.errors.myexceptions import NoSuchFileType
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


@dataclass
class CriticalInfo:
    file_path: Path
    number_maps: int
    timedelays_length: int
    wavelengths_length: int
    timedelays: np.array
    wavelengths: np.array
    scaling_yunit: str


class Opener:
    """
    Opener class is designed to opem experimental files:
    .dat, .his, .img.
    See for details special classes HamamatsuOpener, ASCIIOpener
    """

    def __init__(self, logger=None):
        if not logger:
            logger = module_logger
        self.logger = logger
        self.paths: Dict[Path, CriticalInfo] = OrderedDict()

    def add_critical_info(self, info: CriticalInfo):
        if info.file_path not in self.paths:
            if len(self.paths) > 100:
                self.paths.popitem()  # Remove first element from ordered dict
            self.paths[info.file_path] = info

    def fill_critical_info(self, file_path: Path) -> Tuple[bool, str]:
        if file_path.suffix not in ['.img', '.his', '.dat', '.h5']:
            raise NoSuchFileType(file_path.suffix)
        if not file_path.exists():
            raise FileExistsError()
        try:
            info = self.read_critical_info(file_path)
            self.add_critical_info(info)
            return True, ''
        except (Exception, NoSuchFileType, FileExistsError) as e:
            error_logger(self, self.fill_critical_info, e)
            return False, str(e)

    @abstractmethod
    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        pass

    @abstractmethod
    @lru_cache(maxsize=50, typed=True)
    def read_map(self, file_path: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        pass

    @abstractmethod
    def give_all_maps(self, file_path) -> Union[Measurement, Tuple[bool, str]]:
        pass

    @abstractmethod
    def average_map(self, file_path: Path, call_back_func=None):
        pass