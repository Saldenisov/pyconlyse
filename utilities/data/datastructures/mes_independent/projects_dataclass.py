from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union, NewType, Set
from utilities.data.datastructures.mes_independent import Desription
from utilities.data.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncInput, FuncOutput,
                                                                             FuncGetControllerStateInput,
                                                                             FuncGetControllerStateOutput)

@dataclass(frozen=True)  # To make it hashable
class Operator:
    lastname: str = ''
    firstname: str = ''
    email: str = ''
    telephone: str = ''
    birthday: str = ''


@dataclass
class Project:
    project_name: str
    project_file_path: str
    project_description: str


@dataclass
class ProjectManagerControllerState:
    device_status: DeviceStatus
    db_md5_sum: str  # Allows to check if DB was updated
    files_len: int
    operators_len: int
    projects_len: int


@dataclass
class ProjectManagerViewState:
    controller_state: ProjectManagerControllerState
    files_paths: list = field(default_factory=list)
    projects_names: list = field(default_factory=list)
    projects_paths: list = field(default_factory=list)
    operators_names: list = field(default_factory=list)


@dataclass(order=True, frozen=True)
class ProjectManagerDescription(Desription):
    pass


@dataclass
class FuncGetProjectManagerControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetProjectManagerControllerStateOutput(FuncGetControllerStateOutput):
    state: ProjectManagerControllerState


@dataclass
class FuncGetFileDescriptionInput(FuncInput):
    file_id: str


@dataclass
class FuncGetFileDescriptionOutput(FuncOutput):
    author: Operator = Operator()
    comments_file: str = ''
    data_size_bytes: int = 0
    file_name: str = ''
    file_creation: str = ''
    operators: List[Operator] = field(default_factory=list)
    timedelays_size: int = 0
    wavelengths_size: int = 0


@dataclass
class FuncGetProjectDescirptionInput(FuncInput):
    file_id: str


@dataclass
class FuncGetProjectDescirptionOutput(FuncOutput):
    author: str = ''
    comments_file: str = ''
    data_size_bytes: int = 0
    file_creation: str = ''
    project_name: str = ''


@dataclass
class FuncGetFilesInput(FuncInput):
    author_email: str = ''
    operator_email: Union[str, List[str]] = ''


@dataclass
class FuncGetFilesOutput(FuncOutput):
    files: List[str]
    operator_email: Union[str, List[str]] = ''


@dataclass
class FuncGetOperatorsInput(FuncInput):
    operator_id: Union[int, List[int]] = field(default_factory=list)

@dataclass
class FuncGetOperatorsOutput(FuncOutput):
    operators: List[Operator]


@dataclass
class FuncGetProjectsInput(FuncInput):
    author_email: str = ''
    operator_email: Union[str, List[str]] = ''


@dataclass
class FuncGetProjectsOutput(FuncOutput):
    projects_names: List[str]
    projects_files: List[str]
    operator_email: Union[str, List[str]] = ''
