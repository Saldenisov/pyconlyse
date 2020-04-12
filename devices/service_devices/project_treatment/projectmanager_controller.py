"""
08/03/2020 DENISOV Sergey
projectmanager_controller.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
import os
from abc import abstractmethod
from datetime import datetime
from itertools import chain, tee
import hashlib
from pathlib import Path
from time import time_ns
from typing import Union, Dict, Any, Tuple, Iterable, Generator
from database import db_create_connection, db_close_conn, db_execute_select, db_execute_insert
from devices.devices import Service
from errors.myexceptions import DeviceError
from utilities.myfunc import paths_to_dict
from utilities.data.datastructures.mes_independent import (CmdStruct, FuncActivateInput, FuncActivateOutput,
                                                           FuncPowerInput, FuncGetControllerStateInput,
                                                           FuncGetControllerStateOutput)
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.data.datastructures.mes_independent.projects_dataclass import (ProjectManagerDescription,
                                                                              FuncGetProjectManagerControllerStateInput,
                                                                              FuncGetProjectManagerControllerStateOutput,
                                                                              FuncGetFileTreeInput,
                                                                              FuncGetFileTreeOutput)


import logging

module_logger = logging.getLogger(__name__)


class ProjectManager_controller(Service):
    # TODO: UPDATE
    AVERAGE = CmdStruct('average', None, None)
    GET_PROJECT = CmdStruct('get_project', None, None)
    GET_FILE = CmdStruct('get_file', None, None)
    GET_FILE_TREE = CmdStruct('get_file_tree', FuncGetFileTreeInput, FuncGetFileTreeOutput)
    GET_PROJECT_TREE = CmdStruct('get_project_tree', None, None)

    SAVE_FILE = CmdStruct('save', None, None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.projects_path: Path = Path(self.get_settings('Parameters')['projects_folder'])
        self.data_path: Path = Path(self.get_settings('Parameters')['data_folder'])
        self.database_path: Path = Path(self.get_settings('Parameters')['database'])
        self.power(FuncPowerInput(True))  # ProjectManager is always on
        self.activate(FuncActivateInput(True))  # ProjectManager is always active
        res, comments = self._scan_files()
        if not res:
            raise ProjectManagerError(self, f'During __init__: comments={comments}')

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        self.device_status.active = flag
        return FuncActivateOutput(comments=f'{self.name} active state is set to {flag}',
                                  func_success=True, device_status=self.device_status)

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return  (*super().available_public_functions(), ProjectManager_controller.AVERAGE,
                                                       ProjectManager_controller.GET_FILE_TREE,
                                                       ProjectManager_controller.SAVE_FILE)

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        return super()._check_if_connected()

    def description(self) -> ProjectManagerDescription:
        """
        Description with important parameters
        :return: StpMtrDescription with parameters essential for understanding what this device is used for
        """
        try:
            parameters = self.get_settings('Parameters')
            return ProjectManagerDescription(info=parameters['info'], GUI_title=parameters['title'])
        except KeyError as e:
            return DeviceError(self, f'Could not set description of controller from database: {e}')

    def get_controller_state(self, func_input: FuncGetProjectManagerControllerStateInput) \
            -> FuncGetProjectManagerControllerStateOutput:
        """
        State of cotroller is returned
        :return:  FuncGetControllerStateOutput
        """
        comments = ''
        return FuncGetProjectManagerControllerStateOutput(device_status=self.device_status,
                                                          comments=comments, func_success=True)

    def get_file_tree(self, func_input: FuncGetFileTreeInput) -> FuncGetFileTreeOutput:
        conn = db_create_connection(self.database_path)
        files_db, files_db_c = tee((Path(value) for value in db_execute_select(conn,
                                                                               "SELECT file_path from Files", True)))
        file_tree = paths_to_dict(files_db_c)
        files = set()
        for file in files_db:
            files.add(str(file))
        return FuncGetFileTreeOutput(comments='', func_success=True, file_tree=file_tree, files=files)

    def open(self, measurement: Union[Path, Measurement]):
        pass

    def save(self, file_path: Path):
        pass

    def _scan_files(self) -> Tuple[bool, str]:
        def check_files_names(files: Union[Generator, Iterable]) -> bool:
            renamed = False
            for file in files:
                if not isinstance(file, Path):
                    try:
                        file = Path(file)
                    except:
                        BaseException(f'Function: _scanner_data {file} is Path instance. Device id={self.id}')
                if '~ID~' not in file.name:
                    renamed = True
                    ID = hashlib.md5(file.name.encode('utf-8') + str(time_ns()).encode('utf-8')).hexdigest()
                    new_name = f'{file.stem}~ID~{ID}{file.suffix}'
                    file.rename(file.parent / new_name)
            return renamed

        dat_files, dat_files_c = tee(self.data_path.rglob('*.dat'))
        if check_files_names(dat_files_c):
            dat_files = self.data_path.rglob('*.dat')
        img_files, img_files_c = tee(self.data_path.rglob('*.img'))
        if check_files_names(img_files_c):
            img_files = self.data_path.rglob('*.img')
        zip_files, zip_files_c = tee(self.data_path.rglob('*.zip'))
        if check_files_names(zip_files_c):
            zip_files = self.data_path.rglob('*.zip')
        hdf_files, hdf_files_c = tee(self.data_path.rglob('*.h5'))
        if check_files_names(hdf_files_c):
            hdf_files = self.data_path.rglob('*.h5')

        self._files = set(chain(dat_files, img_files, zip_files, hdf_files))

        conn = db_create_connection(self.database_path)
        files_db = [Path(value) for value in db_execute_select(conn, "SELECT file_path from Files", True)]

        files_to_insert = []
        for file_path in self._files:
            if file_path not in files_db:
                file_name = file_path.stem
                file_id = file_name.split('~ID~')[1]
                file_creation = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d (%H:%M:%S.%f)")
                file_path = str(file_path)
                files_to_insert.append((file_id, file_name, file_path, file_creation, -1))
        if files_to_insert:
            res, comments = db_execute_insert(conn,  'INSERT INTO Files VALUES(?,?,?,?,?);', files_to_insert, True)
        else:
            res, comments = True, ''
        db_close_conn(conn)
        return res, comments

    def _scanner_project(self) -> Tuple[bool, str]:
        # TODO: fill project_table in DB
        pass


class ProjectManagerError(BaseException):
    def __init__(self, controller: ProjectManager_controller, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
