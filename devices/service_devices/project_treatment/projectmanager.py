"""
08/03/2020 DENISOV Sergey
projectmanager.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
from abc import abstractmethod
from pathlib import Path
from typing import Union, Dict, Any
from devices.devices import Service
from utilities.data.datastructures.mes_independent import CmdStruct, FuncActivateInput, FuncActivateOutput
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement


import logging

module_logger = logging.getLogger(__name__)


class ProjectManager(Service):
    #TODO: UPDATE
    AVERAGE = CmdStruct('average', None, None)
    READ = CmdStruct('read', None, None)
    SAVE = CmdStruct('save', None, None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        self.device_status.active = flag
        return FuncActivateOutput(comments=f'{self.name} active state is set to {flag}',
                                  func_success=True, device_status=self.device_status)

    @abstractmethod
    def open(self, measurement: Union[Path, Measurement]):
        pass

    @abstractmethod
    def save(self, file_path: Path):
        pass

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return super().available_public_functions() + [ProjectManager.AVERAGE,
                                                       ProjectManager.READ,
                                                       ProjectManager.SAVE]

    def description(self) -> Dict[str, Any]:
        pass



