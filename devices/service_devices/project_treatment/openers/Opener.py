'''
Created on 17 avr. 2015

@author: saldenisov 
'''

from errors.myexceptions import NoSuchFileType

import numpy as np
from abc import abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union, Tuple
from datastructures.mes_independent.measurments_dataclass import Measurement
import logging
module_logger = logging.getLogger(__name__)


@dataclass
class CriticalInfo:
    file_path: Path
    timedelays_length:int
    wavelengths_length:int
    timedelays: np.array
    wavelengths: np.array


class Opener:
    """
    TODO: add description
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

    def fill_critical_info(self, filepath: Path) -> Tuple[bool, str]:
        if filepath.suffix not in ['.img', '.his']:
            raise NoSuchFileType
        if not filepath.exists():
            raise FileExistsError
        try:
            info = self.read_critical_info(filepath)
            self.add_critical_info(info)
            return True, ''
        except (Exception, NoSuchFileType, FileExistsError) as e:
            self.logger.error(e)
            return False, str(e)

    @abstractmethod
    def read_critical_info(self, filepath: Path) -> CriticalInfo:
        pass

    @abstractmethod
    def read_map(self, filepath: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        pass

    @abstractmethod
    def give_all_maps(self, filepath) -> Union[Measurement, Tuple[bool, str]]:
        pass