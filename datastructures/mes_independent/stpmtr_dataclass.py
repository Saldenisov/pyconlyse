from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union, NewType
from datastructures.mes_independent.general import Desription, FuncInput, FuncOutput
from datastructures.mes_independent.devices_dataclass import (Desription, DeviceStatus, FuncGetControllerStateInput,
                                                              FuncGetControllerStateOutput)


@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    position: float = ''
    preset_values: List[Union[int, float]] = field(default_factory=list)
    status: int = 0

    def short(self):
        return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status)


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    id: int
    position: float
    status: int


@dataclass(order=True, frozen=True)
class StpMtrDescription(Desription):
    axes: Dict[int, AxisStpMtr]


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtrEssentials]
    device_status: DeviceStatus
    axes_previous: Dict[int, AxisStpMtrEssentials] = None
    device_status_previous: DeviceStatus = None
    start_stop: list = field(default_factory=list)


@dataclass
class FuncActivateAxisInput(FuncInput):
    axis_id: int
    flag: bool


@dataclass
class FuncActivateAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncGetStpMtrControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetStpMtrControllerStateOutput(FuncGetControllerStateOutput):
    axes: Dict[int, AxisStpMtr]



@dataclass
class FuncGetPosInput(FuncInput):
    axis_id: int


@dataclass
class FuncGetPosOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


relative = NewType('relative', str)
absolute = NewType('absolute', str)


@dataclass
class FuncMoveAxisToInput(FuncInput):
    axis_id: int
    pos: Union[int, float]
    how: Union[relative, absolute]


@dataclass
class FuncMoveAxisToOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncStopAxisInput(FuncInput):
    axis_id: int


@dataclass
class FuncStopAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


