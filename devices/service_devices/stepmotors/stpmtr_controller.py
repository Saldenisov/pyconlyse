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
    GET_POS = CmdStruct(FuncGetPosInput, FuncGetPosOutput)
    SET_POS = CmdStruct(FuncSetPosInput, FuncSetPosOutput)
    MOVE_AXIS_TO = CmdStruct(FuncMoveAxisToInput, FuncMoveAxisToOutput)
    STOP_AXIS = CmdStruct(FuncStopAxisInput, FuncStopAxisOutput)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['stpmtr_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, AxisStpMtr] = HardwareDeviceDict()

    def available_public_functions(self) -> List[CmdStruct]:
        return [*super().available_public_functions(), StpMtrController.ACTIVATE_AXIS, StpMtrController.GET_POS,
                                                       StpMtrController.MOVE_AXIS_TO, StpMtrController.SET_POS,
                                                       StpMtrController.STOP_AXIS]

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:  # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters()  # This must be realized for all controllers
                    if res:
                        self.device_status.active = True
            else:
                results, comments_l = ([], [])

                for axis_id, axis in self.axes.items():
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
            res, comments = self._check_controller_activity()
        if res:
            res, comments = self._change_axis_status(axis_id, flag)
        essentials = self.axes_essentials
        status = []
        for key, axis in essentials.items():
            status.append(essentials[key].status)
        info = f'Axes status: {status}. {comments}'
        info_msg(self, 'INFO', info)
        return FuncActivateAxisOutput(axes=self.axes_essentials, comments=info, func_success=res)

    @property
    def axes(self):
        return self._hardware_devices

    @property
    def axes_essentials(self):
        essentials = {}
        for axis_id, axis in self.axes.items():
            essentials[axis_id] = axis.short()
        return essentials

    @abstractmethod
    def _connect(self, flag: bool) -> Tuple[bool, str]:
        """
        Connect/Disconnect to hardware controller
        :param flag: True/False
        :return: res, comments='' if True, else error_message
        """
        if self.device_status.power:
            self.device_status.connected = flag
            return True, ""
        else:
            return False, f'Power is off, connect to controller function cannot be called with flag {flag}'

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

    def _check_axis_active(self, axis_id: int) -> Tuple[bool, str]:
        if self.axes[axis_id].status:
            return True, ''
        else:
            return False, f'Axis id={axis_id}, name={self.axes[axis_id].name} is not active.'

    def _check_axis_range(self, axis_id: int) -> Tuple[bool, str]:
        if axis_id in self.axes.keys():
            return True, ''
        else:
            return False, f'Axis id={axis_id} is out of range={self.axes.keys()}.'

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

    def _check_axis_flag(self, flag: int):
        flags = [0, 1, 2]
        if flag not in flags:
            return False, f'Wrong flag {flag} was passed. FLAGS={flags}.'
        else:
            return True, ''

    def _check_move_type(self, axis_id: int, type_move: MoveType) -> Tuple[bool, str]:
        if type_move in self.axes[axis_id].type_move:
            return True, ''
        else:
            return False, f'Axis axis_id={axis_id} does not have type_move {type_move}. ' \
                          f'It has {self.axes[axis_id].type_move}'

    def get_controller_state(self, func_input: FuncGetStpMtrControllerStateInput) -> FuncGetStpMtrControllerStateOutput:
        """
        State of controller is returned
        :return:  FuncOutput
        """
        comments = f'Controller is {self.device_status.active}. Power is {self.device_status.power}. ' \
                   f'Axes are {self._axes_status}'
        try:
            return FuncGetStpMtrControllerStateOutput(axes=self.axes, device_status=self.device_status,
                                                      comments=comments, func_success=True)
        except KeyError:
            return FuncGetStpMtrControllerStateOutput(axes=self.axes, device_status=self.device_status,
                                                      comments=comments, func_success=True)

    def get_pos(self, func_input: FuncGetPosInput) -> FuncGetPosOutput:
        return FuncGetPosOutput(axes=self.axes_essentials, comments='', func_success=True)

    def move_axis_to(self, func_input: FuncMoveAxisToInput) -> FuncMoveAxisToOutput:
        axis_id = func_input.axis_id
        how = func_input.how
        pos = func_input.pos
        move_type = func_input.move_type
        if not move_type:
            move_type = self.axes[axis_id].basic_unit
        res, comments = self._check_axis(axis_id)
        if res:
            res, comments = self._check_move_type(axis_id, move_type)
        if res:
            res, comments = self._check_controller_activity()
        if res:
            if move_type != self.axes[axis_id].basic_unit:
                pos = self.axes[axis_id].convert_to_basic_unit(move_type, pos)
                if isinstance(pos, tuple):
                    res, comments = pos
                    return FuncMoveAxisToOutput(axes=self.axes_essentials, comments=comments, func_success=res)
            if how == 'relative':
                pos = self.axes[axis_id].position + pos
            res, comments = self._is_within_limits(axis_id, pos)  # if not relative just set pos
        if res:
            if self.axes[axis_id].status == 1:
                res, comments = self._move_axis_to(axis_id, pos)
            elif self.axes[axis_id].status == 2:
                res, comments = False, f'Axis id={axis_id}, name={self.axes[axis_id].name} is running. ' \
                                       f'Please, stop it before new request.'
        return FuncMoveAxisToOutput(axes=self.axes_essentials, comments=comments, func_success=res)

    @abstractmethod
    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int], how: Union[absolute, relative]) -> Tuple[bool, str]:
        pass

    @abstractmethod
    def _get_positions(self) -> List[Union[int, float]]:
        pass

    def _get_positions_db(self) -> Dict[int, Union[int, float]]:
        """Return Dictionary[Axis.name: Axis.position] if error (file is empty, number of positions is less than self._axes_number"""
        with open(self._file_pos, 'r') as file_pos:
            pos_s = file_pos.readline()
        pos = eval(pos_s)
        if not isinstance(pos, dict):
            error_logger(self, self._get_positions_db, StpMtrError(self, 'is not a dict'))
            info_msg(self, 'INFO', f'Forming axes positions dict. Setting everything to zero')
            pos = {axis.device_id: 0 for axis in self.axes.values()}
        else:
            if list(pos.keys()) != self._axes_ids:
                error_logger(self, self._get_positions_db, StpMtrError(self, f"Axes ids {list(pos.keys())} in file, "
                                                                         f"are different to those read from DB "
                                                                         f"{self._axes_ids}"))
                info_msg(self, 'INFO', f'Setting position according DB names')
                for axis in self.axes.values():
                    if axis.device_id not in pos:
                        pos[axis.device_id] = 0
            else:
                for key, val in pos.items():
                    res, _ = self._is_within_limits(key, val)
                    if not res:
                        pos[key] = 0
                    if not (isinstance(val, int) or isinstance(val, float)):
                        raise StpMtrError(self, f"val {val} is not a number")
        return pos

    @abstractmethod
    def _get_preset_values(self) -> List[Set[Union[Union[int, float], MoveType]]]:
        pass

    def _is_within_limits(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        min_v, max_v = self.axes[axis_id].limits[0]
        move_type = self.axes[axis_id].limits[1]
        axis = self.axes[axis_id]
        min_v = axis.convert_to_basic_unit(move_type, min_v)
        max_v = axis.convert_to_basic_unit(move_type, max_v)
        if min_v <= pos <= max_v:
            return True, ''
        else:
            comments = f'Desired pos: {pos} for axis id={axis_id}, name={self.axes[axis_id].name} is not ' \
                       f'in the range {self.axes[axis_id].limits}'
            return False, comments

    def _set_controller_positions(self, positions: Dict[str, Union[int, float]]) -> Tuple[bool, str]:
        """
        This function sets user-defined positions into hardware controller.
        :param positions: list of positions passed to hardware controller
        :return:
        """
        results = []
        commentss = []
        for axis_id, pos in positions.items():
            try:
                res, _ = self._check_axis_range(int(axis_id))
                if res:
                    res, comments = self._set_pos(axis_id, pos)
                    results.append(res)
                    commentss.append(comments)
            except ValueError:
                error_logger(self, self._set_positions_axes, f'Error: Axis_id {axis_id} cannot be converted to number.')

        return all(results), '. '.join(commentss)

    def _set_positions_axes(self):
        controller_pos: Dict[int, Union[int, float]] = {}
        if self.device_status.connected:
            controller_pos = self._get_positions()
        file_pos: Dict[int, Union[int, float]] = self._get_positions_db()
        if len(controller_pos) == 0 and len(file_pos) == 0:
            self.logger.error("Axes positions could not be set, setting everything to 0")
        elif not controller_pos:
            positions = file_pos
        elif controller_pos != file_pos:
            error_logger(self, self._set_positions_axes, "Last files positions do not correspond to controller ones.")
            if not int(self.get_settings('Parameters')['controller_priority']):
                res, comments = self._set_controller_positions(positions=file_pos)
                if res:
                    positions = file_pos
                else:
                    positions = controller_pos
                    error_logger(self, self._set_positions_axes, f'_set_positions_axes: {comments}')
            else:
                positions = controller_pos
        else:
            positions = controller_pos

        for id, pos in positions.items():
            self.axes[id].position = pos
        StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)

    @abstractmethod
    def _set_pos(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        pass

    def set_pos(self, func_input: FuncSetPosInput) -> FuncSetPosOutput:
        res, comments = self._check_axis_range(func_input.axis_id)
        if res:
            axis: AxisStpMtr = self.axes[func_input.axis_id]
            if isinstance(func_input.pos_unit, MoveType):
                pos = axis.convert_to_basic_unit(func_input.pos_unit, func_input.axis_pos)
            else:
                return FuncSetPosOutput(comments=f'Pos_unit {func_input.pos_unit} is not MoveType.', func_success=False,
                                        axes=self.axes_essentials)
            res, comments = self._set_pos(func_input.axis_id, pos)
            if res:
                StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)
        return FuncSetPosOutput(comments=comments, func_success=res, axes=self.axes_essentials)

    def stop_axis(self, func_input: FuncStopAxisInput) -> FuncStopAxisOutput:
        axis_id = func_input.axis_id
        res, comments = self._check_axis(axis_id)
        if res:
            if self.axes[axis_id].status == 2:
                res, comments = self._change_axis_status(axis_id, 1, force=True)
                if res:
                    comments = f'Axis id={axis_id}, name={self.axes[axis_id].name} was stopped by user.'
            elif self.axes[axis_id].status == 1:
                comments = f'Axis id={axis_id}, name={self.axes[axis_id].name} was already stopped.'
            elif self.axes[axis_id].status == 0:
                comments = f'Axis id={axis_id}, name={self.axes[axis_id].name} is not even active.'
        return FuncStopAxisOutput(axes=self.axes_essentials, comments=comments, func_success=res)

    @staticmethod
    def _write_to_file(text: str, file: Path):
        with open(file, 'w') as opened_file:
            opened_file.write(text)


class StpMtrError(BaseException):
    def __init__(self, controller: StpMtrController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
