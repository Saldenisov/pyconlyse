"""
08/03/2020 DENISOV Sergey
project_controller.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
from abc import abstractmethod
from pathlib import Path
from typing import Union, Dict, Any
from devices.devices import Service
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement


import logging

module_logger = logging.getLogger(__name__)


class ProjectController(Service):
    #TODO: UPDATE
    #AVERAGE = CmdStruct('average', )
    #READ = CmdStruct('read', )
    #SAVE = CmdStruct('save', )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def open(self, measurement: Union[Path, Measurement]):
        pass

    @abstractmethod
    def save(self, file_path: Path):
        pass

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return super().available_public_functions() + [ProjectController.AVERAGE,
                                                       ProjectController.READ,
                                                       ProjectController.SAVE]

    def description(self) -> Dict[str, Any]:
        pass

    def activate(self, flag: bool):
        pass

