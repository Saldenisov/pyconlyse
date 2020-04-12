from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union, NewType, Set
from utilities.data.datastructures.mes_independent import Desription
from utilities.data.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncInput, FuncOutput,
                                                                             FuncGetControllerStateInput,
                                                                             FuncGetControllerStateOutput)


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
class FuncGetFileTreeInput(FuncInput):
    pass


@dataclass
class FuncGetFileTreeOutput(FuncOutput):
    file_tree: Dict[str, Union[str, Dict[str, str]]]
    files: Set[str]
