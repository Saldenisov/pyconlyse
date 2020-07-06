from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Union, NewType, Set

from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription

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

    def short(self, unit: MoveType = None):
        if unit:
            pos = self.convert_to_basic_unit(unit)
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

    def convert_pos_to_unit(self, unit: MoveType) -> Union[Tuple[bool, str], Union[int, float]]:
        return self.convert_from_to_unit(self.position, self.basic_unit, unit)

    def convert_to_basic_unit(self, unit: MoveType, val: Union[int, float])\
            -> Union[Tuple[bool, str], Union[int, float]]:
        return self.convert_from_to_unit(val, unit, self.basic_unit)

    def convert_from_to_unit(self, val: Union[int, float], unit_from: MoveType, unit_to: MoveType) \
            -> Union[Tuple[bool, str], Union[int, float]]:
        error_text = f'Axis axis_id={self.id} cannot convert microstep to angle. Error='
        # microstep to step
        if unit_from is unit_to:
            return val
        if unit_from is MoveType.microstep and unit_to is MoveType.step:
            try:
                return val / self.move_parameters['microsteps']
            except KeyError as e:
                return False, error_text + str(e)
        # step to microstep
        elif unit_from is MoveType.step and unit_to is MoveType.microstep:
            try:
                return int(val * self.move_parameters['microsteps'])
            except KeyError as e:
                return False, error_text + str(e)
        # microstep to angle
        elif unit_from is MoveType.microstep and unit_to is MoveType.angle:
            try:
                conversion_step_angle = self.move_parameters['conversion_step_angle']
                return val * conversion_step_angle / self.move_parameters['microsteps']
            except KeyError as e:
                return False, error_text + str(e)
        # angle to step
        elif unit_from is MoveType.angle and unit_to is MoveType.step:
            try:
                conversion_step_angle = self.move_parameters['conversion_step_angle']
                return val / conversion_step_angle
            except KeyError as e:
                return False, error_text + str(e)
        # angle to microstep
        elif unit_from is MoveType.angle and unit_to is MoveType.microstep:
            try:
                conversion_step_angle = self.move_parameters['conversion_step_angle']
                return int(val / conversion_step_angle * self.move_parameters['microsteps'])
            except KeyError as e:
                return False, error_text + str(e)
        # step to angle
        elif unit_from is MoveType.step and unit_to is MoveType.angle:
            try:
                conversion_step_angle = self.move_parameters['conversion_step_angle']
                return val * conversion_step_angle
            except KeyError as e:
                return False, error_text + str(e)
        # microstep to mm
        elif unit_from is MoveType.microstep and unit_to is MoveType.mm:
            try:
                conversion_step_mm = self.move_parameters['conversion_step_mm']
                return val * conversion_step_mm / self.move_parameters['microsteps']
            except KeyError as e:
                return False, error_text + str(e)
        # mm to microstep
        elif unit_from is MoveType.mm and unit_to is MoveType.microstep:
            try:
                conversion_step_mm = self.move_parameters['conversion_step_mm']
                return int(val / conversion_step_mm * self.move_parameters['microsteps'])
            except KeyError as e:
                return False, error_text + str(e)
        # mm to step
        elif unit_from is MoveType.mm and unit_to is MoveType.step:
            try:
                conversion_step_mm = self.move_parameters['conversion_step_mm']
                return val / conversion_step_mm
            except KeyError as e:
                return False, error_text + str(e)
        # step to mm
        elif unit_from is MoveType.step and unit_to is MoveType.mm:
            conversion_step_mm = self.move_parameters['conversion_step_mm']
            try:
                return val * conversion_step_mm
            except KeyError as e:
                return False, error_text + str(e)
        else:
            return False, f'Axis axis_id={self.id} cannot convert {unit_from} to {unit_to}.'


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
    axes: Dict[int, AxisStpMtr]
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
    how: Union[relative, absolute]  # TODO: replace with enum class
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
