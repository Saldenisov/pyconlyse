import logging
from abc import abstractmethod
from os import path
from pathlib import Path
from typing import Any, Callable

from devices.devices import Service
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.stpmtr_dataclass import *
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import error_logger, info_msg

module_logger = logging.getLogger(__name__)


class StpMtrController(Service):
    """
    See Service for more functions
    These functions are default for any step motor controller, e.g.: A4098, OWIS, Standa
    """
    ACTIVATE_AXIS = CmdStruct(FuncActivateAxisInput, FuncActivateAxisOutput)
    GET_POS_AXIS = CmdStruct(FuncGetPosInput, FuncGetPosOutput)
    SET_POS_AXIS = CmdStruct(FuncSetPosInput, FuncSetPosOutput)
    MOVE_AXIS_TO = CmdStruct(FuncMoveAxisToInput, FuncMoveAxisToOutput)
    STOP_AXIS = CmdStruct(FuncStopAxisInput, FuncStopAxisOutput)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['stpmtr_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, AxisStpMtr] = HardwareDeviceDict()
        self._file_pos = Path(__file__).resolve().parents[0] / f"{self.name}:positions.stpmtr".replace(":","_")
        self._parameters_set_hardware = False
        if not path.exists(self._file_pos):
            file = open(self._file_pos, "w+")
            file.close()

    def available_public_functions(self) -> List[CmdStruct]:
        return [*super().available_public_functions(), StpMtrController.ACTIVATE_AXIS, StpMtrController.GET_POS_AXIS,
                                                       StpMtrController.MOVE_AXIS_TO, StpMtrController.SET_POS_AXIS,
                                                       StpMtrController.STOP_AXIS]

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:
                    # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters_main_devices(extra_func=[self._read_set_positions])
                    if res:
                        self.device_status.active = True
            else:
                results, comments_l = ([], [])

                for axis_id, axis in self.axes_stpmtr.items():
                    res, comments = self._change_axis_status(axis_id, 0)
                    results.append(res)
                    comments_l.append(comments)

                if all(results):  # if all axis can be set to 0
                    res, comments = self._connect(False)
                else:
                    res = False
                    info = 'Cannot deactivate. '
                    comments = ' '.join(comments_l)
                    comments = info + comments
                if res:
                    self.device_status.active = flag
        info = f'{self.id}:{self.name} active state is {self.device_status.active}. {comments}'
        info_msg(self, 'INFO', info)
        return FuncActivateOutput(comments=info, device_status=self.device_status, func_success=res)

    def activate_axis(self, func_input: FuncActivateAxisInput) -> FuncActivateAxisOutput:
        axis_id = func_input.axis_id
        flag = func_input.flag
        res, comments = self._check_axis_range(axis_id)
        if res:
            res, comments = self._change_axis_status(axis_id, flag)
        essentials = self.axes_stpmtr_essentials
        status = []
        for key, axis in essentials.items():
            status.append(essentials[key].status)
        info = f'Axes status: {status}. {comments}'
        return FuncActivateAxisOutput(axes=self.axes_stpmtr_essentials, comments=info, func_success=res)

    @property
    def axes_stpmtr(self) -> Dict[int, AxisStpMtr]:
        return self._hardware_devices

    @axes_stpmtr.setter
    def axes_stpmtr(self, value):
        self._hardware_devices = value

    @property
    def axes_stpmtr_essentials(self):
        return {axis_id: axis.short() for axis_id, axis in self.axes_stpmtr.items()}

    @abstractmethod
    def _connect(self, flag: bool) -> Tuple[bool, str]:
        pass

    def _check_axis(self, axis_id: int) -> Tuple[bool, str]:
        """
        Checks if axis n is a valid axis for this controller and if it is active
        :param axis_id:
        :return: res, comments='' if True, else error_message
        """
        res, comments = self._check_axis_range(axis_id)
        if res:
            return self._check_axis_active(axis_id)
        else:
            return res, comments

    def _check_axis_active(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        if self.axes_stpmtr[device_id].status:
            return True, ''
        else:
            return False, f'Axis id={device_id}, name={self.axes_stpmtr[device_id].name} is not active.'

    def _check_axis_range(self, axis_id: int) -> Tuple[bool, str]:
        if axis_id in self.axes_stpmtr:
            return True, ''
        else:
            return False, f'Axis id={axis_id} is out of range={self.axes_stpmtr.keys()}.'

    @abstractmethod
    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        """
        Changes axis status on software/hardware level.
        :param axis_id: 0-n
        :param flag: 0, 1, 2
        :param force: True/False is required to force axis status to be changed from 2 to 1 or 0 for controllers, which
        do not support parallel axis moving
        :return: res, comments='' if True, else error_message
        """
        pass

    @staticmethod
    def _check_status_flag(flag: int):
        flags = [0, 1, 2]
        if flag not in flags:
            return False, f'Wrong flag {flag} was passed. FLAGS={flags}.'
        else:
            return True, ''

    def _check_move_type(self, device_id: Union[int, str], type_move: MoveType) -> Tuple[bool, str]:
        if type_move in self.axes_stpmtr[device_id].type_move:
            return True, ''
        else:
            return False, f'Axis axis_id={device_id} does not have type_move {type_move}. ' \
                          f'It has {self.axes_stpmtr[device_id].type_move}'

    def get_pos_axis(self, func_input: FuncGetPosInput) -> FuncGetPosOutput:
        res, comments = self._check_axis(func_input.axis_id)
        if res:
            res, comments = self._get_position_axis(func_input.axis_id)
        position = self.axes_stpmtr[func_input.axis_id].position
        return FuncGetPosOutput(axis_id=func_input.axis_id, position=position, comments=comments, func_success=res)

    @abstractmethod
    def _get_position_axis(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        pass

    def _form_axes_positions(self) -> Dict[Union[int, str], float]:
        return {axis.device_id: axis.position for axis in self.axes_stpmtr.values()}

    def move_axis_to(self, func_input: FuncMoveAxisToInput) -> FuncMoveAxisToOutput:
        axis_id = func_input.axis_id
        how = func_input.how
        pos = func_input.pos
        move_type = func_input.move_type
        if not move_type:
            move_type = self.axes_stpmtr[axis_id].basic_unit
        res, comments = self._check_axis(axis_id)
        if res:
            res, comments = self._check_move_type(axis_id, move_type)
        if res:
            if move_type != self.axes_stpmtr[axis_id].basic_unit:
                pos = self.axes_stpmtr[axis_id].convert_to_basic_unit(move_type, pos)
                if isinstance(pos, tuple):
                    res, comments = pos
                    return FuncMoveAxisToOutput(axes=self.axes_stpmtr_essentials, comments=comments, func_success=res)
            if how == 'relative':
                pos = self.axes_stpmtr[axis_id].position + pos
            res, comments = self._is_within_limits(axis_id, pos)  # if not relative just set pos
        if res:
            if self.axes_stpmtr[axis_id].status == 1:
                res, comments = self._move_axis_to(axis_id, pos)
            elif self.axes_stpmtr[axis_id].status == 2:
                res, comments = False, f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].name} is running. ' \
                                       f'Please, stop it before new request.'
        return FuncMoveAxisToOutput(axis_id=axis_id, position=self.axes_stpmtr[axis_id].position, comments=comments,
                                    func_success=res)

    @abstractmethod
    def _move_axis_to(self, device_id: Union[int, str], go_pos: Union[float, int],
                      how: Union[absolute, relative]) -> Tuple[bool, str]:
        pass

    @property
    def hardware_devices(self):
        return self.axes_stpmtr

    def _is_within_limits(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        min_v, max_v = self.axes_stpmtr[axis_id].limits
        move_type = self.axes_stpmtr[axis_id].basic_unit
        axis = self.axes_stpmtr[axis_id]
        min_v = axis.convert_to_basic_unit(move_type, min_v)
        max_v = axis.convert_to_basic_unit(move_type, max_v)
        if min_v <= pos <= max_v:
            return True, ''
        else:
            comments = f'Desired pos: {pos} for axis id={axis_id}, name={self.axes_stpmtr[axis_id].name} is not ' \
                       f'in the range {self.axes_stpmtr[axis_id].limits}'
            return False, comments

    def _read_set_positions(self):
        res, comments = [], ''
        for axis in self.axes_stpmtr.values():
            r, c = self._get_position_axis(axis.device_id)
            res.append(r)
            if c:
                comments = f'{c}. {comments}'
        return all(res), comments


    @abstractmethod
    def _set_move_parameters_axes(self, must_have_param: Dict[int, Set[str]] = None):
        try:
            move_parameters = self.get_main_device_parameters['move_parameters']
            move_parameters: dict = eval(move_parameters)
            for device_id, value in move_parameters.items():
                if device_id in self.axes_stpmtr and device_id in must_have_param:
                        if set(must_have_param[device_id]).intersection(value.keys()) != set(must_have_param[device_id]):
                            raise StpMtrError(self,
                                              text=f'Not all must have parameters "{must_have_param}" for device_id '
                                                   f'{device_id} are present in DB.')
                        if 'microsteps' not in value and MoveType.microstep in self.axes_stpmtr[device_id].type_move:
                            self.axes_stpmtr[device_id].type_move.remove(MoveType.microstep)
                            self.axes_stpmtr[device_id].type_move.remove(MoveType.step)
                        if 'conversion_step_mm' not in value and MoveType.mm in self.axes_stpmtr[device_id].type_move:
                            self.axes_stpmtr[device_id].type_move.remove(MoveType.mm)
                        if 'conversion_step_angle' not in value and MoveType.angle in self.axes_stpmtr[device_id].type_move:
                            self.axes_stpmtr[device_id].type_move.remove(MoveType.angle)
                        if not self.axes_stpmtr[device_id].type_move:
                            raise StpMtrError(self,
                                              text=f'move_parameters must have "microsteps" or  "conversion_step_mm" or'
                                                   f'"conversion_step_angle" for axis_id {device_id}.')
                        if MoveType.mm in self.axes_stpmtr[device_id].type_move and MoveType.angle in self.axes_stpmtr[
                            device_id].type_move:
                            raise StpMtrError(self, text=f'move parameters could have either "conversion_step_mm" or '
                                                         f'"conversion_step_angle", not both for axis_id {device_id}')
                        try:
                            basic_unit = MoveType(move_parameters[device_id]['basic_unit'])
                            if basic_unit in [MoveType.step, MoveType.microstep]:
                                self.axes_stpmtr[device_id].basic_unit = MoveType.step
                                if MoveType.microstep not in self.axes_stpmtr[device_id].type_move:
                                    raise StpMtrError(self, text=f'Basic_unit cannot be microstep or step, when Axis '
                                                                 f'axis_id={device_id} does not have "microstep" parameter.')
                            self.axes_stpmtr[device_id].basic_unit = basic_unit
                        except (KeyError, ValueError) as e:
                            raise StpMtrError(self,
                                              text=f'Cannot set "basic_unit" for axis axis_id={device_id}. Error = {e}')
                        finally:
                            self.axes_stpmtr[device_id].move_parameters = value
            return True, ''
        except KeyError:
            raise StpMtrError(self, text=f'move_parameters are absent in DB for {self.name}.')
        except SyntaxError as e:
            raise StpMtrError(self, text=f'move_parameters error during eval: {e}.')

    def set_pos_axis(self, func_input: FuncSetPosInput) -> FuncSetPosOutput:
        res, comments = self._check_axis_range(func_input.axis_id)
        if res:
            axis: AxisStpMtr = self.axes_stpmtr[func_input.axis_id]
            if isinstance(func_input.pos_unit, MoveType):
                pos = axis.convert_to_basic_unit(func_input.pos_unit, func_input.axis_pos)
            else:
                return FuncSetPosOutput(comments=f'Pos_unit {func_input.pos_unit} is not MoveType.', func_success=False,
                                        axes=self.axes_stpmtr_essentials)
            res, comments = self._set_pos_axis(func_input.axis_id, pos)
            if res:
                self._write_positions_to_db(self._form_axes_positions())
        return FuncSetPosOutput(comments=comments, func_success=res, axis_id=func_input.axis_id,
                                position=axis.position)

    @abstractmethod
    def _set_pos_axis(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        pass

    def stop_axis(self, func_input: FuncStopAxisInput) -> FuncStopAxisOutput:
        axis_id = func_input.axis_id
        res, comments = self._check_axis(axis_id)
        if res:
            if self.axes_stpmtr[axis_id].status == 2:
                res, comments = self._change_axis_status(axis_id, 1, force=True)
                if res:
                    comments = f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].friendly_name} was stopped by user.'
            elif self.axes_stpmtr[axis_id].status == 1:
                comments = f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].friendly_name} was already stopped.'
            elif self.axes_stpmtr[axis_id].status == 0:
                comments = f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].friendly_name} is not even active.'
        return FuncStopAxisOutput(axes=self.axes_stpmtr_essentials, comments=comments, func_success=res)

    def _write_positions_to_db(self, positions):
        # TODO: make it work
        pass


class StpMtrError(BaseException):
    def __init__(self, controller: StpMtrController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
