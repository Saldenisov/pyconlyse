from enum import Enum
from dataclasses import dataclass, field
from typing import NewType, Union, List, Dict, Tuple, Set
from devices.devices_dataclass import (HardwareDevice, DeviceControllerState, FuncGetControllerStateInput,
                                       FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput

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
class AxisStpMtr(HardwareDevice):
    basic_unit: MoveType = MoveType.microstep
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    move_parameters: Dict[str, Union[int, float, str]] = field(default_factory=dict)
    # {'microsteps': 256, 'conversion_step_mm': 0.0025, 'basic_unit': 'angle' or 'step', 'mm'}
    type_move: Set[MoveType] = field(default_factory=lambda: set([MoveType.angle, MoveType.mm,
                                                                  MoveType.step, MoveType.microstep]))
    position: Union[mm, angle, microstep] = 0.0
    preset_values: List[Set[Union[Union[int, float], MoveType]]] = field(default_factory=list)

    def short(self, unit: MoveType = None):
        if unit:
            pos = self.convert_to_basic_unit(unit, self.position)
            if isinstance(pos, tuple):
                return AxisStpMtrEssentials(device_id=self.device_id, position=self.position, status=self.status,
                                            unit=self.basic_unit)
            else:
                return AxisStpMtrEssentials(device_id=self.device_id, device_id_seq=self.device_id_seq, position=pos,
                                            status=self.status, unit=unit)
        else:
            return AxisStpMtrEssentials(device_id=self.device_id, position=self.position, status=self.status,
                                        unit=self.basic_unit, device_id_seq=self.device_id_seq)

    def convert_pos_to_unit(self, unit: MoveType) -> Union[Tuple[bool, str], Union[int, float]]:
        return self.convert_from_to_unit(self.position, self.basic_unit, unit)

    def convert_to_basic_unit(self, unit: MoveType, val: Union[int, float])\
            -> Union[Tuple[bool, str], Union[int, float]]:
        return self.convert_from_to_unit(val, unit, self.basic_unit)

    def convert_from_to_unit(self, val: Union[int, float], unit_from: MoveType, unit_to: MoveType) \
            -> Union[Tuple[bool, str], Union[int, float]]:
        error_text = f'Axis axis_id={self.device_id} cannot convert microstep to angle. Error='
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
            return False, f'Axis axis_id={self.device_id} cannot convert {unit_from} to {unit_to}.'


@dataclass(frozen=False)
class A4988AxisStpMtr(AxisStpMtr):
    pass


@dataclass(frozen=False)
class OwisAxisStpMtr(AxisStpMtr):
    gear_ratio: float = 0.0
    pitch: float = 1.0
    revolution: int = 200
    speed: float = 5.0


@dataclass(frozen=False)
class StandaAxisStpMtr(AxisStpMtr):
    device_id_internal_seq: int = None


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    device_id: Union[int, str]
    device_id_seq: int
    position: Union[mm, angle, microstep]
    unit: MoveType
    status: int


@dataclass
class FuncGetStpMtrControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetStpMtrControllerStateOutput(FuncGetControllerStateOutput):
    pass

@dataclass
class FuncGetPosInput(FuncInput):
    axis_id: int
    com: str = 'get_pos_axis'


@dataclass
class FuncGetPosOutput(FuncOutput):
    axis: AxisStpMtr
    com: str = 'get_pos_axis'


@dataclass
class FuncMoveAxisToInput(FuncInput):
    axis_id: int
    pos: Union[int, float]
    how: Union[relative, absolute]  # TODO: replace with enum class
    move_type: Union[MoveType, None] = None
    com: str = 'move_axis_to'


@dataclass
class FuncMoveAxisToOutput(FuncOutput):
    axis: AxisStpMtr
    com: str = 'move_axis_to'


@dataclass
class FuncSetPosInput(FuncInput):
    axis_id: int
    axis_pos: float
    pos_unit: MoveType
    com: str = 'set_pos_axis'


@dataclass
class FuncSetPosOutput(FuncOutput):
    axis: AxisStpMtr
    com: str = 'set_pos_axis'


@dataclass
class FuncStopAxisInput(FuncInput):
    axis_id: int
    com: str = 'stop_axis'


@dataclass
class FuncStopAxisOutput(FuncOutput):
    axis: AxisStpMtr
    com: str = 'stop_axis'
