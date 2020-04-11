from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union, NewType
from utilities.data.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncInput, FuncOutput,
                                                                             FuncGetControllerStateInput,
                                                                             FuncGetControllerStateOutput)

@dataclass
class FuncReadFileTreeInput(FuncInput):
    pass


@dataclass
class FuncReadFileTreeOutput(FuncOutput):
    file_tree: Dict[str, Union[str, Dict[str, str]]]
    files: Tuple[Path]
