"""
08/03/2020 DENISOV Sergey
projectmanager_controller.py contains abstract services capable of treating experiments datastructures:
open, analyze, transform
"""
from datetime import datetime
from itertools import chain, tee
from pathlib import Path
import hashlib
from time import time_ns
from typing import Any, Iterable, Generator
from utilities.database import db_create_connection, db_execute_select, db_execute_insert
from devices.devices import Service
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import file_md5
from utilities.datastructures.mes_independent import *


import logging

module_logger = logging.getLogger(__name__)


class ProjectManager_controller(Service):
    # TODO: UPDATE
    GET_PROJECT = CmdStruct(None, None)
    GET_FILE = CmdStruct(None, None)
    GET_FILE_DESCRIPTION = CmdStruct(FuncGetFileDescriptionInput, FuncGetFileDescriptionOutput)
    GET_FILES = CmdStruct(FuncGetFilesInput, FuncGetFilesOutput)
    GET_PROJECTS = CmdStruct(FuncGetProjectsInput, FuncGetProjectsOutput)
    GET_OPERATORS = CmdStruct(FuncGetOperatorsInput, FuncGetOperatorsOutput)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_path: Path = Path(self.get_settings('Parameters')['data_folder'])
        self.database_path: Path = Path(self.get_settings('Parameters')['database'])
        self.power(FuncPowerInput(True))  # ProjectManager is always on
        self.activate(FuncActivateInput(True))  # ProjectManager is always active
        res, comments = self._scan_files()
        if not res:
            raise ProjectManagerError(self, f'During __init__: comments={comments}')
        self.state = self.get_state()

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        self.device_status.active = flag
        return FuncActivateOutput(comments=f'{self.name} active state is set to {flag}',
                                  func_success=True, device_status=self.device_status)

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return (*super().available_public_functions(), ProjectManager_controller.GET_FILES,
                                                       ProjectManager_controller.GET_PROJECTS,
                                                       ProjectManager_controller.GET_OPERATORS,
                                                       ProjectManager_controller.GET_FILE_DESCRIPTION)

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

    def get_state(self):
        files_len = -1
        project_len = -1
        operators_len = -1
        COMMENTS = ''
        conn = db_create_connection(self.database_path)
        # Files
        res, comments = db_execute_select(conn, 'SELECT COUNT(*) FROM Files', False)
        COMMENTS += comments
        COMMENTS += comments
        if res:
            files_len = res
        # Projects
        res, comments = db_execute_select(conn, "SELECT COUNT(*) FROM Files where file_path like '%.h5'", False)
        COMMENTS += comments
        if res:
            project_len = res
        # Operators
        res, comments = db_execute_select(conn, "SELECT COUNT(*) FROM Operators", False)
        COMMENTS += comments
        if res:
            operators_len = res
        conn.close()
        db_md5_checksum = file_md5(self.database_path)
        return ProjectManagerControllerState(self.device_status, db_md5_checksum, files_len, operators_len, project_len)

    def get_controller_state(self, func_input: FuncGetProjectManagerControllerStateInput) \
            -> FuncGetProjectManagerControllerStateOutput:
        """
        State of cotroller is returned
        :return:  FuncGetControllerStateOutput
        """
        if file_md5(self.database_path) != self.state.db_md5_sum:
            self.state = self.get_state()
        return FuncGetProjectManagerControllerStateOutput(comments='', func_success=True,
                                                          device_status=self.device_status,
                                                          state=self.state)

    def get_file_description(self, func_input: FuncGetFileDescriptionInput) -> FuncGetFileDescriptionOutput:
        conn = db_create_connection(self.database_path)
        author = Operator()
        comments_file = ''
        data_size_bytes = 0
        file_creation = ''
        file_name = ''
        operators: List[Operator] = []
        timedelays_size = 0
        wavelengths_size = 0
        COMMENTS = ''

        # Get author Operator
        res, comments = db_execute_select(conn, f"Select author_id from Files where file_id='{func_input.file_id}'")
        if res:
            res = self.get_operators(FuncGetOperatorsInput(res))
            author: Operator = res.operators[0]
            COMMENTS = f'{COMMENTS}.{res.comments}'
        COMMENTS = f'{COMMENTS}.{comments}'
        # comments
        res, comments = db_execute_select(conn, f"Select comments from Files where file_id='{func_input.file_id}'")
        if res:
            comments_file = res
        COMMENTS = f'{COMMENTS}.{comments}'
        # file name
        cmd = f"Select file_name from Files where file_id='{func_input.file_id}'"
        res, comments = db_execute_select(conn, cmd)
        if res:
            file_name = res
        COMMENTS = f'{COMMENTS}.{comments}'
        # file creation
        cmd = f"Select file_creation from Files where file_id='{func_input.file_id}'"
        res, comments = db_execute_select(conn, cmd)
        if res:
            file_creation = res
        COMMENTS = f'{COMMENTS}.{comments}'
        # operators
        cmd = f"Select operator_id from GlueOperatorFile where file_id='{func_input.file_id}'"
        res, comments = db_execute_select(conn, cmd, True)
        if res:
            operators_ids = []
            for entree in res:
                operators_ids.append(entree[0])
            res = self.get_operators(FuncGetOperatorsInput(operators_ids))
            operators = res.operators

        COMMENTS = f'{COMMENTS}.{comments}'
        # File' datastructures info
        res, comments = db_execute_select(conn, f"Select file_path from Files where file_id='{func_input.file_id}'")
        if res:
            file_path = Path(self.data_path.parents[0] / res)
            data_size_bytes = file_path.stat().st_size
        COMMENTS = f'{COMMENTS}.{comments}'
        conn.close()
        if res:
            return FuncGetFileDescriptionOutput(comments, True, author=author, comments_file=comments_file,
                                                data_size_bytes=data_size_bytes, file_name=file_name,
                                                file_id=func_input.file_id, operators=operators,
                                                file_creation=file_creation, timedelays_size=timedelays_size,
                                                wavelengths_size=wavelengths_size)
        else:
            return FuncGetFileDescriptionOutput(comments, False)

    def get_files(self, func_input: FuncGetFilesInput) -> FuncGetFilesOutput:
        conn = db_create_connection(self.database_path)
        if not func_input.operator_email and not func_input.author_email:
            com = "SELECT file_path from Files"
        elif func_input.author_email:
            com = f"Select file_path from Files where author_id=(SELECT operator_id From Operators " \
                  f"where email='{func_input.author_email}')"
        else:
            if isinstance(func_input.operator_email, str):
                com = f"Select file_path from Files where file_id IN " \
                      f"(Select file_id from GlueOperatorFile where operator_id = " \
                      f"(SELECT operator_id From Operators where email='{func_input.operator_email}'))"

            elif isinstance(func_input.operator_email, list):
                i = 0
                com_b = f"Select file_name, file_path from Files where file_id IN " \
                        f"(Select file_id from GlueOperatorFile where operator_id IN " \
                        f"(SELECT operator_id From Operators where email="

                for email in func_input.operator_email:
                    if i == 0:
                        com_b = com_b + f"'{email}'"
                    else:
                        com_b = com_b + f" or email='{email}'"
                    i += 1
                com_end = f"))"
                com = com_b + com_end
        res, comments = db_execute_select(conn, com, True)
        conn.close()
        if res:
            try:
                files_db = (Path(value[0]) for value in res)
                files = []
                for file in files_db:
                    files.append(str(file))
                self._files = files
                res = True
            except (KeyError, ValueError, TypeError) as e:
                res = False
                comments = f'{comments} {e}'
            return FuncGetFilesOutput(comments=comments, func_success=res, operator_email=func_input.operator_email,
                                      files=files)
        else:
            return FuncGetFilesOutput(comments=comments, func_success=False,
                                      operator_email=func_input.operator_email, files=[])

    def get_operators(self, func_input: FuncGetOperatorsInput) -> FuncGetOperatorsOutput:

        conn = db_create_connection(self.database_path)
        param: List[str] = list(Operator.__annotations__.keys())
        cmd = f"SELECT {', '.join(param)} from Operators"
        if isinstance(func_input.operator_id, list):
            if func_input.operator_id == []:
                pass
            else:
                operators_ids = [str(oper) for oper in func_input.operator_id]
                operators_ids = '(' + ','.join(operators_ids) + ')'
                cmd = f"{cmd} where operator_id IN {operators_ids}"
        elif isinstance(func_input.operator_id, int):
            cmd = f"{cmd} where operator_id='{func_input.operator_id}'"


        res, comments = db_execute_select(conn, cmd, True)
        conn.close()
        if res:
            operators = []
            try:
                for entree in res:
                    operators.append(Operator(*entree))
                res = True
            except TypeError as e:
                    res = False
                    comments = f'{comments} {e}'
            self._operators = operators
            return FuncGetOperatorsOutput(comments, res, operators)
        else:
            return FuncGetOperatorsOutput(comments, False, [])

    def get_projects(self, func_input: FuncGetProjectsInput) -> FuncGetProjectsOutput:
        conn = db_create_connection(self.database_path)
        if not func_input.operator_email and not func_input.author_email:
            com = "Select file_name, file_path from Files where file_path like '%.h5'"
        elif func_input.author_email:
            com = f"Select file_name, file_path from Files where author_id = " \
                  f"(SELECT operator_id From Operators where email='{func_input.author_email}')" \
                  f" and file_path like '%.h5'"
        else:
            if isinstance(func_input.operator_email, str):
                com= f"Select file_name, file_path from Files where file_id IN " \
                     f"(Select file_id from GlueOperatorFile where operator_id=(SELECT operator_id " \
                     f"From Operators where email='{func_input.au}')) and file_path like '%.h5'"
            elif isinstance(func_input.operator_email, list):
                i=0
                com_b = f"Select file_name, file_path from Files where file_id IN " \
                        f"(Select file_id from GlueOperatorFile where operator_id IN (SELECT operator_id " \
                        f"From Operators where email="

                for email in func_input.operator_email:
                    if i==0:
                        com_b = com_b + f"'{email}'"
                    else:
                        com_b = com_b + f" or email='{email}'"
                    i += 1
                com_end = f")) and file_path like '%.h5'"
                com = com_b + com_end
        res, comments = db_execute_select(conn, com, True)
        conn.close()
        if res:
            projects_names = []
            projects_paths = []
            for entree in res:
                try:
                    projects_names.append(entree[0])
                    projects_paths.append(entree[1])
                    res = True
                except (KeyError, ValueError) as e:
                    res = False
                    comments = f'{comments} {e}'
            return FuncGetProjectsOutput(comments, res, projects_names, projects_paths, func_input.operator_email)
        else:
            return FuncGetOperatorsOutput(comments, False, [], [], func_input.operator_email)

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
        his_files, his_files_c = tee(self.data_path.rglob('*.his'))
        if check_files_names(his_files_c):
            his_files = self.data_path.rglob('*.his')
        zip_files, zip_files_c = tee(self.data_path.rglob('*.zip'))
        if check_files_names(zip_files_c):
            zip_files = self.data_path.rglob('*.zip')
        hdf_files, hdf_files_c = tee(self.data_path.rglob('*.h5'))
        if check_files_names(hdf_files_c):
            hdf_files = self.data_path.rglob('*.h5')

        _files: List[Path] = list(chain(dat_files, img_files, his_files, zip_files, hdf_files))

        conn = db_create_connection(self.database_path)
        res, comments = db_execute_select(conn, "SELECT file_path from Files", True)
        if res:
            files_db = [Path(self.data_path.parents[0] / value[0]) for value in res]
            files_to_insert = []
            for file_path in _files:
                if file_path not in files_db:
                    file_name = file_path.stem
                    file_id = file_name.split('~ID~')[1]
                    file_creation = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d (%H:%M:%S)")
                    files_to_insert.append((file_id, file_path.name,
                                            str(file_path.relative_to(self.data_path.parents[0])),
                                            file_creation, -1, ''))
            if files_to_insert:
                res, comments = db_execute_insert(conn, 'INSERT INTO Files VALUES(?,?,?,?,?,?);',
                                              files_to_insert, True)
            else:
                res, comments = True, 'Files in DB are up-to-date'
        conn.close()
        return res, comments

    def _scanner_project(self) -> Tuple[bool, str]:
        # TODO: fill project_table in DB
        pass


class ProjectManagerError(BaseException):
    def __init__(self, controller: ProjectManager_controller, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
