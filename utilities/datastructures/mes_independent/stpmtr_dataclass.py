from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Union, NewType, NamedTuple, TypeVar, Set
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)


relative = NewType('relative', str)
absolute = NewType('absolute', str)
mm = NewType('mm', float)
angle = NewType('angle', float)
microstep = NewType('microstep', int)
step = NewType('microstep', int)


class MoveType(Enum):
    angle = 'angle'
    mm = 'mm'
    microstep = 'microstep'
    step = 'step'

    def __repr__(self):
        return str(self)


@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    basic_unit: MoveType = MoveType.microstep
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    move_parameters: Dict[str, Union[int, float, str]] = field(default_factory=dict)  # {'microsteps': 256, 'conversion_step_mm': 0.0025,
                                                                                       # 'basic_unit': 'angle' or 'step', 'mm'}
    type_move: Set[MoveType] = field(default_factory=lambda: set([MoveType.angle, MoveType.mm,
                                                                  MoveType.step, MoveType.microstep]))
    position: Union[mm, angle, microstep] = 0.0
    preset_values: List[Set[Union[Union[int, float], MoveType]]] = field(default_factory=list)
    status: int = 0  # 0 - not active, 1 - active, 2 - moving

    def short(self, unit: MoveType = None, callback_position_calc=None):
        if not callback_position_calc:
            return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status, unit=self.basic_unit)
        else:
            if unit:
                pos = callback_position_calc(self, self.position, unit)
                if isinstance(pos, tuple):
                    return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status,
                                                unit=self.basic_unit)
                else:
                    return AxisStpMtrEssentials(id=self.id,
                                                position=pos,
                                                status=self.status,
                                                unit=unit)
            else:
                return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status,
                                            unit=self.basic_unit)


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    id: int
    position: Union[mm, angle, microstep]
    unit: MoveType
    status: int


@dataclass(order=True)
class StpMtrDescription(Desription):
    axes: Dict[int, AxisStpMtr]


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtrEssentials]
    device_status: DeviceStatus
    know_movements: Dict[Union[mm, angle, microstep], bool] = \
        field(default_factory=lambda: {microstep: False, mm: False, angle: False})
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
    pos: Union[int, float]
    how: Union[relative, absolute]
    move_type: Union[MoveType, None] = None
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
