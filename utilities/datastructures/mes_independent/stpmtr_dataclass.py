from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union, NewType, NamedTuple
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)


relative = NewType('relative', str)
absolute = NewType('absolute', str)
move_mm = NewType('move_mm', float)
move_angle = NewType('move_angle', float)
move_steps = NewType('move_steps', tuple)


@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    position: float = 0.0
    preset_values: List[Union[int, float]] = field(default_factory=list)
    status: int = 0

    def short(self):
        return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status)


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    id: int
    position: float
    status: int


@dataclass(order=True)
class StpMtrDescription(Desription):
    axes: Dict[int, AxisStpMtr]
    known_movements: Dict[Union[move_mm, move_angle, move_steps], bool]


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtrEssentials]
    device_status: DeviceStatus
    know_movements: Dict[Union[move_mm, move_angle, move_steps], bool] = \
        field(default_factory=lambda: {move_steps: False, move_mm: False})
    axes_previous: Dict[int, AxisStpMtrEssentials] = None
    device_status_previous: DeviceStatus = None
    start_stop: list = field(default_factory=list)


@dataclass
class FuncActivateAxisInput(FuncInput):
    axis_id: int
    flag: bool
    com: str = 'activate_axis'


@dataclass
class FuncActivateAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]
    com: str = 'activate_axis'


@dataclass
class FuncGetStpMtrControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetStpMtrControllerStateOutput(FuncGetControllerStateOutput):
    axes: Dict[int, AxisStpMtr] = None
    microsteps: int = None



@dataclass
class FuncGetPosInput(FuncInput):
    axis_id: int
    com: str = 'get_pos'


@dataclass
class FuncGetPosOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]
    com: str = 'get_pos'


@dataclass
class FuncMoveAxisToInput(FuncInput):
    axis_id: int
    pos: Union[move_mm, move_angle, move_steps]
    how: Union[relative, absolute]
    com: str = 'move_axis_to'


@dataclass
class FuncMoveAxisToOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]
    com: str = 'move_axis_to'


@dataclass
class FuncStopAxisInput(FuncInput):
    axis_id: int
    com: str = 'stop_axis'


@dataclass
class FuncStopAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]
    com: str = 'stop_axis'
