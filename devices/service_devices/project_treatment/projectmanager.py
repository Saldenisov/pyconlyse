"""
08/03/2020 DENISOV Sergey
projectmanager.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
import os
from abc import abstractmethod
from itertools import chain
import hashlib
from pathlib import Path
from time import time_ns
from typing import Union, Dict, Any, Tuple, Iterable, Generator
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
        def check_files_names(files: Union[Generator, Iterable]) -> bool:

            print()
            renamed = False
            for file in files:
                if not isinstance(file, Path):
                    try:
                        file = Path(file)
                    except:
                        BaseException(f'Function: _scanner_data {file} is Path instance. Device id={self.id}')
                if '~ID~' not in file.name:
                    renamed = True
                    file_name = '_'.join(file.name.split('.')[0:-1])
                    extension = file.name.split('.')[-1]
                    ID = hashlib.md5(file_name.encode('utf-8') + str(time_ns()).encode('utf-8')).hexdigest()
                    new_name = f'{file_name}~ID~{ID}.{extension}'
                    file.rename(file.parent / new_name)

            return renamed

        dat_files = self.data_path.rglob('*.dat')
        if check_files_names(dat_files):
            dat_files = self.data_path.rglob('*.dat')
        img_files = self.data_path.rglob('*.img')
        if check_files_names(img_files):
            img_files = self.data_path.rglob('*.img')
        zip_files = self.data_path.rglob('*.zip')
        if check_files_names(zip_files):
            zip_files = self.data_path.rglob('*.zip')

        self._files = set(chain(dat_files, img_files, zip_files))



        return True, ''

    def _scanner_project(self) -> Tuple[bool, str]:
        pass

    def description(self) -> Dict[str, Any]:
        pass



