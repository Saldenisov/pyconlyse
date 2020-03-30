"""
08/03/2020 DENISOV Sergey
projectmanager.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
import os
from abc import abstractmethod
from itertools import chain
from pathlib import Path
from typing import Union, Dict, Any, Tuple
from devices.devices import Service
from utilities.data.datastructures.mes_independent import (CmdStruct, FuncActivateInput, FuncActivateOutput,
                                                           FuncGetControllerStateInput, FuncGetControllerStateOutput)
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
        self.projects_path: Path = Path(self.get_settings('Parameters')['projects_folder'])
        self.data_path: Path = Path(self.get_settings('Parameters')['data_folder'])
        res, comments = self._scanner_data()

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        self.device_status.active = flag
        return FuncActivateOutput(comments=f'{self.name} active state is set to {flag}',
                                  func_success=True, device_status=self.device_status)

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return super().available_public_functions() + [ProjectManager.AVERAGE,
                                                       ProjectManager.READ,
                                                       ProjectManager.SAVE]

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        return super()._check_if_connected()

    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        """
        State of cotroller is returned
        :return:  FuncGetControllerStateOutput
        """
        comments = ''
        return FuncGetControllerStateOutput(device_status=self.device_status,
                                            comments=comments, func_success=True)


    def open(self, measurement: Union[Path, Measurement]):
        pass

    def save(self, file_path: Path):
        pass

    def _scanner_data(self) -> Tuple[bool, str]:
        dat_files = self.data_path.rglob('*.dat')
        img_files = self.data_path.rglob('*.img')
        zip_files = self.data_path.rglob('*.zip')
        files = tuple(chain(dat_files, img_files, zip_files))

        return True, ''

    def _scanner_project(self) -> Tuple[bool, str]:
        pass

    def description(self) -> Dict[str, Any]:
        pass



