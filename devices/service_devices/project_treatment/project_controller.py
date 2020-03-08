"""
08/03/2020 DENISOV Sergey
project_controller.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
from abc import abstractmethod
from pathlib import Path
from typing import Union, Dict, Any
from devices import CmdStruct
from devices.devices import Service
from utilities.data.datastructures.mes_independent import Measurement


import logging

module_logger = logging.getLogger(__name__)


class ProjectController(Service):
    AVERAGE = CmdStruct('average', {'experiments': []})
    READ = CmdStruct('read', {'file_path': ''})
    SAVE = CmdStruct('save', {'file_path': '', 'overwrite': True})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def open(self, measurement: Union[Path, Measurement]):
        pass

    @abstractmethod
    def save(self, file_path: Path):
        pass

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        pass

    def description(self) -> Dict[str, Any]:
        pass

    def activate(self, flag: bool):
        pass

