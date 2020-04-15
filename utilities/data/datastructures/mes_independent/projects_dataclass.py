from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union, NewType, Set
from utilities.data.datastructures.mes_independent import Desription
from utilities.data.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncInput, FuncOutput,
                                                                             FuncGetControllerStateInput,
                                                                             FuncGetControllerStateOutput)

@dataclass
class Operator:
    lastname: str
    firstname: str
    email: str
    telephone: str
    birthday: str


@dataclass
class Project:
    name: str
    file_path: str
    operators: List[Operator]


@dataclass(order=True, frozen=True)
class ProjectManagerDescription(Desription):
    pass


@dataclass
class FuncGetProjectManagerControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetProjectManagerControllerStateOutput(FuncGetControllerStateOutput):
    pass


@dataclass
class FuncGetFileDescirptionInput(FuncInput):
    file_id: str


@dataclass
class FuncGetFileDescirptionOutput(FuncOutput):
    author: str = ''
    comments_file: str = ''
    data_size_bytes: int = 0
    file_creation: str = ''
    project_name: str = ''
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
class FuncGetFileTreeInput(FuncInput):
    operator_email: str = ''


@dataclass
class FuncGetFileTreeOutput(FuncOutput):
    file_tree: Dict[str, Union[str, Dict[str, str]]]
    files: Set[str]
    operator_id: str = ''


@dataclass
class FuncGetOperatorsInput(FuncInput):
    pass

@dataclass
class FuncGetOperatorsOutput(FuncOutput):
    operators: List[Operator]


@dataclass
class FuncGetProjectsInput(FuncInput):
    pass


@dataclass
class FuncGetProjectsOutput(FuncOutput):
    operators: List[Operator]