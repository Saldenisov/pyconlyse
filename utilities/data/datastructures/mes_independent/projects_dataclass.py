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
    files_paths: List[str] = field(default_factory=list)
    projects_names: List[str] = field(default_factory=list)
    projects_paths: List[str] = field(default_factory=list)
    operators: List[Operator] = field(default_factory=list)
    operators_future: List[Operator] = field(default_factory=list)


    def operators_search(self, operator_email: str) -> int:
        if self.operators:
            i = 0
            for operator in self.operators:
                if operator_email == operator.email:
                    return i
                i += 1
        return -1

    def operators_future_search(self, operator_email: str) -> int:
        if self.operators_future:
            i = 0
            for operator in self.operators_future:
                if operator_email == operator.email:
                    return i
                i += 1
        return -1

    def operators_future_add_by_index(self, operator_index: int):
        if self.operators:
            if len(self.operators) > operator_index:
                self.operators_future.append(self.operators[operator_index])

    def operators_future_remove_by_index(self, operator_index: int):
        if self.operators_future:
            if len(self.operators_future) > operator_index:
                self.operators_future.pop(operator_index)

    def operators_future_remove_element(self, operator: Operator):
        if self.operators_future:
            try:
                self.operators_future.remove(operator)
            except ValueError:
                pass


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
    file_id: str = ''
    file_name: str = ''
    author: Operator = Operator()
    comments_file: str = ''
    operators: List[Operator] = field(default_factory=list)
    file_creation: str = ''
    data_size_bytes: int = 0
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
