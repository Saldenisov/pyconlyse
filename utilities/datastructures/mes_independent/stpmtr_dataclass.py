from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Union, NewType, NamedTuple, TypeVar, Set
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)


relative = NewType('relative', str)
absolute = NewType('absolute', str)
move_mm = NewType('move_mm', float)
move_angle = NewType('move_angle', float)
move_microsteps = NewType('move_microsteps', int)

class MoveType(Enum):
    mm = 'mm'
    agnle = 'angle'
    microstep = 'microstep'

mm = TypeVar('mm')
angle = TypeVar('angle')
microstep = TypeVar('microstep')

@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    move_parameters: Dict[str, Union[int, float, None]] = field(default_factory=dict)  # {'microsteps': 256, 'conversion_step_mm': 0.0025,
                                                                                       # 'conversion_step_angle': None}
    type_move: Set[MoveType] = field(default_factory=lambda: set([MoveType.agnle, MoveType.mm, MoveType.microstep]))
    position: Union[move_mm, move_angle, move_microsteps] = 0
    preset_values: List[Union[int, float]] = field(default_factory=list)
    status: int = 0

    def short(self):
        return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status)


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    id: int
    position: Union[move_mm, move_angle, move_microsteps]
    status: int


@dataclass(order=True)
class StpMtrDescription(Desription):
    axes: Dict[int, AxisStpMtr]


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtrEssentials]
    device_status: DeviceStatus
    know_movements: Dict[Union[move_mm, move_angle, move_microsteps], bool] = \
        field(default_factory=lambda: {move_microsteps: False, move_mm: False, move_angle: False})
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
    pos: Union[move_mm, move_angle, move_microsteps]
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
