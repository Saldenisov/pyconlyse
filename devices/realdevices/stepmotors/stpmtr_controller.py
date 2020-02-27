from abc import abstractmethod
from os import path
from collections import OrderedDict as od
from pathlib import Path
from devices import CmdStruct
from errors.myexceptions import DeviceError
from devices.devices import Service
from typing import Union, Dict, Iterable, List, Tuple, Any, ClassVar, Callable
import logging

module_logger = logging.getLogger(__name__)


class StpMtrController(Service):
    ACTIVATE = CmdStruct('activate', {'flag': True})
    ACTIVATE_AXIS = CmdStruct('activate_axis', {'axis': 0, 'flag': True})
    GET_POS = CmdStruct('get_pos', {'axis': 0})
    GET_CONTROLLER_STATE = CmdStruct('get_controller_state', {})
    MOVE_AXIS_TO = CmdStruct('move_axis_to', {'axis': 0, 'pos': 0.0, 'how': 'absolute/relative'})
    STOP_AXIS = CmdStruct('stop_axis', {'axis': 0})
    POWER = CmdStruct('power', {'flag': True})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._axes_number = 1
        self._axes_names: List[str] = []  # TODO: read from DB
        self._axes_id: List[int] = []  # TODO: read from DB
        self._axes_status: List[bool] = []  # Keeps axes status, active or not
        self._file_pos = Path(__file__).resolve().parents[0] / f"{self.name}:positions.stpmtr".replace(":","_")
        self._limits: List[Tuple[int, int]] = []  # Limits for each axis
        self._parameters_set_hardware = False
        self._pos: List[float] = []  # Keeps actual position for axes for controller
        self._preset_values: List[Tuple[int, int]] = []  # Preset values for each axis
        if not path.exists(self._file_pos):
            try:
                file = open(self._file_pos, "w+")
                file.close()
            except Exception as e:
                self.logger.error(e)

        res, comments = self._set_parameters()  # Set parameters from DB first and after connection is done update
                                                # from hardware controller if possible
        if not res:
            raise StpmtrError(comments)

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        # These functions are default for any stpmtr controller, e.g.: A4098, OWIS
        return {'activate': {'flag': True},
                'activate_axis': {'axis': 0, 'flag': True},
                'move_axis_to': {'axis': 0, 'pos': 0.0, 'how': 'absolute/relative'},
                'stop_axis': {'axis': 0},
                'get_pos': {'axis': 0},
                'get_controller_state': {},
                'power': {'flag': True}
                }

    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        res, comments = self._connect(flag)  # gurantees that parameters could be read from controller
        if res and not self._parameters_set_hardware:  # parameters should be set from hardware controller if possible
            res, comments = self._set_parameters()  # This must be realized for all controllers
        if res:
            if not flag:
                self._move_all_home()
                self._parameters_set_hardware = False
            self.device_status.active = flag
        info = f'{self.id}:{self.name} active state is {self.device_status.active}.{comments}'
        self.logger.info(info)
        return {'flag': self.device_status.active, 'func_success': res}, info

    def activate_axis(self, axis: int, flag: int) -> Tuple[Dict[str, Union[int, bool]], str]:
        """
        :param axis: 0-n
        :param flag: 0=non-active, 1=ready to work, 2=running
        :return: res, comments='' if True, else error_message
        """
        res, comments = self._check_axis_range(axis)
        if res:
            res, comments = self._check_controller_activity()
        if res:
            res, comments = self._change_axis_status(axis, flag)
            return {'axis': axis, 'flag': self._axes_status[axis], 'func_success': res}, comments
        else:
            return {'axis': axis, 'flag': flag, 'func_success': res}, comments

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

    def _check_axis(self, axis: int) -> Tuple[bool, str]:
        """
        Checks if axis n is a valid axis for this controller and if it is active
        :param axis:
        :return: res, comments='' if True, else error_message
        """
        res, comments = self._check_axis_range(axis)
        if res:
            return self._check_axis_active(axis)
        else:
            return res, comments

    def _check_axis_active(self, axis: int) -> Tuple[bool, str]:
        if self._axes_status[axis]:
            return True, ''
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _check_axis_range(self, axis: int) -> Tuple[bool, str]:
        if axis in range(self._axes_number):
            return True, ''
        else:
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'

    @abstractmethod
    def _change_axis_status(self, axis: int, flag: int, force=False) -> Tuple[bool, str]:
        """
        Changes axis status on software/hardware level.
        :param axis: 0-n
        :param flag: 0, 1, 2
        :param force: True/False is required to force axis status to be changed from 2 to 1 or 0 for controllers, which
        do not support parallel axis moving
        :return: res, comments='' if True, else error_message
        """

    def _check_axis_flag(self, flag: int):
        FLAGS = [0, 1, 2]
        if flag not in FLAGS:
            return False, f'Wrong flag {flag} was passed. Must be in range {FLAGS}'
        else:
            return True, ''

    def _check_controller_activity(self):
        if self.device_status.active:
            return True, ''
        else:
            return False, f'Controller is not active. Power is {self.device_status.power}'

    def description(self) -> Dict[str, Any]:
        """
        Description with important parameters
        :return: Dict with parameters essential for understanding what this device is used for
        """
        try:
            parameters = self.get_settings('Parameters')
            desc = od()
            desc['GUI_title'] = parameters['title']
            desc['info'] = parameters['info']
            desc['axes_names'] = self._get_list_db('Parameters', 'axes_names', type_value=str)
            desc['axes_id'] = self._get_list_db('Parameters', 'axes_id', int)
            desc['limits'] = self._get_list_db('Parameters', 'limits', tuple)
            desc['preset_values'] = self._get_list_db('Parameters', 'preset_values', tuple)
            return desc
        except (KeyError, DeviceError) as e:
            return StpmtrError(self, f'Could not set description of controller from DB: {e}')

    @abstractmethod
    def GUI_bounds(self) -> Dict[str, Any]:
        """
        ????
        :return:
        """
        pass

    @abstractmethod
    def _get_axes_status(self) -> List[int]:
        pass

    def _get_axes_status_db(self) -> List[int]:
        return [0] * self._axes_number

    def get_controller_state(self) -> Tuple[Dict[str, Union[int, str]], str]:
        """
        State of cotroller is returned
        :return:  {'device_status': self.device_status, 'axes_status': self._axes_status,
                   'positions': self._pos, 'func_success': True}, f'Controller is {self.device_status.active}. ' \
                                                               f'Power is {self.device_status.power}. ' \
                                                               f'Axes are {self._axes_status}'
        """
        return {'device_status': self.device_status, 'axes_status': self._axes_status,
                'positions': self._pos, 'func_success': True}, f'Controller is {self.device_status.active}. ' \
                                                               f'Power is {self.device_status.power}. ' \
                                                               f'Axes are {self._axes_status}'

    @abstractmethod
    def _get_number_axes(self) -> int:
        pass

    def _get_number_axes_db(self) -> int:
        try:
            return self.get_settings('Parameters')['axes_number']
        except KeyError:
            raise StpmtrError(self, text="Axes_number could not be set, axes_number field is absent in the DB")
        except ValueError:
            raise StpmtrError(self, text="Check axes number in DB, must be axex_number = 1 or any number")

    def get_pos(self, axis: int) -> Tuple[Dict[str, Union[int, float, str]], str]:
        res, comments = self._check_axis(axis)
        if res:
            pos = self._pos[axis]
        return {'axis': axis, 'pos': pos, 'func_success': res}, comments

    def move_axis_to(self, axis: int, pos: Union[float, int], how='absolute') -> \
            Tuple[Dict[str, Union[int, float, str]], str]:
        res, comments = self._check_axis(axis)
        chk_axis = res
        if res:
            res, comments = self._check_controller_activity()
        if res:
            if how == 'relative':
                pos = self._pos[axis] + pos
            res, comments = self._is_within_limits(axis, pos)
        if res:
            if self._axes_status[axis] == 1:
                res, comments = self._move_axis_to(axis, pos, how)
            elif self._axes_status[axis] == 2:
                res, comments = False, f'Axis {axis} is running. Please, stop it before new request.'
        if chk_axis:
            pos = self._pos[axis]
        else:
            pos = None
        return {'axis': axis, 'pos': pos, 'how': how, 'func_success': res}, comments

    @abstractmethod
    def _move_axis_to(self, axis: int, pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        pass

    def _move_all_home(self) -> Tuple[bool, str]:
        """
        move all lines to zero
        :return: res, comments
        """
        for axis in range(self._axes_number):
            self.logger.info(f'Moving {axis} back to 0')
            _, _ = self._change_axis_status(axis, 1)
            _, _ = self.move_axis_to(axis, 0)
            _, _ = self._change_axis_status(axis, 0, force=True)

    @abstractmethod
    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        pass

    def _get_limits_db(self) -> List[Tuple[Union[float, int]]]:
        try:
            limits: List[Tuple[Union[float, int]]] = []
            limits_s: List[str] = self.config.config_to_dict(self.name)['Parameters']['limits'].replace(" ", "").split(';')
            for exp in limits_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                limits.append(val)
            return limits
        except KeyError:
            raise StpmtrError(self, text="Limits could not be set, limits field is absent in the DB")
        except (TypeError, SyntaxError):
            raise StpmtrError(self, text="Check limits field in DB, must be limits = (x1, x2), (x3, x4),...")

    def _set_limits(self):
        if self.device_status.connected:
            limits = self._get_limits()
        else:
            limits = self._get_limits_db()
        self._limits = limits

    @abstractmethod
    def _get_pos(self) -> List[Union[int, float]]:
        pass

    def _get_pos_file(self) -> List[Union[int, float]]:
        """Return [] if error (file is empty, number of positions is less than self._axes_number"""
        try:
            with open(self._file_pos, 'r') as file_pos:
                pos_s = file_pos.readline()
            if not pos_s:
                raise StpmtrError('file with pos is empty')
            pos = eval(pos_s)
            if not isinstance(pos, list):
                raise StpmtrError('is not a list')
            else:
                if len(pos) != self._axes_number:
                    raise StpmtrError(f"There is {len(pos)} positions in file, instead of {self._axes_number}")
                else:
                    for val in pos:
                        if not (isinstance(val, int) or isinstance(val, float)):
                            raise StpmtrError(f"val {val} is not a number")
                    return pos
        except (StpmtrError, FileNotFoundError, SyntaxError) as e:
            self.logger.error(f'in _get_pos_file error: {e}')
            return []

    @abstractmethod
    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        pass

    def _get_preset_values_db(self) -> List[Tuple[Union[int, float]]]:
        try:
            preset_values: List[Tuple[Union[float, int]]] = []
            preset_values_s: List[str] = self.config.config_to_dict(self.name)['Parameters']['preset_values'].replace(" ", "").split(';')
            for exp in preset_values_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                preset_values.append(val)
            return preset_values
        except KeyError:
            raise StpmtrError(self, text="Preset values could not be set, preset_values field is absent in the DB")
        except (TypeError, SyntaxError):
            raise StpmtrError(self, text="Check preset_values field in DB, must be Preset values = (x1, x2), (x3, x4, x1, x5),...")

    def _is_within_limits(self, axis: int, pos: Union[int, float]) -> Tuple[bool, str]:
        if self._limits[axis][0] <= pos <= self._limits[axis][1]:
            return True, ''
        else:
            comments = f'pos: {pos} for axis {axis} is not in the range {self._limits[axis]}'
            return False, comments

    def _set_axes_status(self):
        if self.device_status.connected:
            status = self._get_axes_status()
        else:
            status = self._get_axes_status_db()

        self._axes_status = status

    def _set_number_axes(self):
        if self.device_status.connected:
            axes_number = self._get_number_axes()
        else:
            axes_number = self._get_number_axes_db()
        self._axes_number = axes_number

    def _set_pos(self):
        controller_pos: List[Union[int, float]] = []
        if self.device_status.connected:
             controller_pos = self._get_pos()
        file_pos: List[Union[int, float]] = self._get_pos_file()
        if len(controller_pos) == 0 and len(file_pos) == 0:
            self.logger.error("Axes positions could not be set, setting everything to 0")
            self._pos = [0.0] * self._axes_number
        elif not controller_pos:
            self._pos = file_pos
        elif controller_pos != file_pos:
            self.logger.error("Last log positions do not correspond to controller ones. CHECK REAL POSITIONS")
            raise StpmtrError("Last log positions do not correspond to controller ones. CHECK REAL POSITIONS")
        else:
            self._pos = controller_pos

    def set_default(self):
        self._pos: List[float] = [0] * self._axes_number
        self._axes_status: List[bool] = [0] * self._axes_number  # Keeps axes status, active or not
        self._limits: List[Tuple[int, int]] = [(0, 0)] * self._axes_number  # Limits for each axis
        self._preset_values: List[Tuple[int, int]] = [(0, 0)] * self._axes_number  # Preset values for each axis

    def _set_preset_values(self):
        if self.device_status.connected:
            preset_values = self._get_preset_values()
        else:
            preset_values = self._get_preset_values_db()
        self._preset_values = preset_values

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        try:
            self._set_number_axes()
            self._set_axes_status()
            self._set_limits()
            self._set_preset_values()
            self._set_pos()
            res = []
            if extra_func:
                comments = ''
                for func in extra_func:
                    r, com = func()
                    res.append(r)
                    comments = comments + com

            if self.device_status.connected:
                self._parameters_set_hardware = True
            if all(res):
                return True, ''
            else:
                raise StpmtrError(self, comments)
        except StpmtrError as e:
            self.logger.error(e)
            return False, str(e)

    def stop_axis(self, axis: int) -> Tuple[Dict[str, Union[int, float, str]], str]:
        res, comments = self._check_axis(axis)
        if res:
            if self._axes_status[axis] == 2:
                res, comments = self._change_axis_status(axis, 1, force=True)
                if res:
                    comments = f'Axis {axis} was stopped by user'
            elif self._axes_status[axis] == 1:
                comments = f'Axis {axis} was already stopped'
        return {'axis': axis, 'func_success': res}, comments


    @staticmethod
    def _write_to_file(text: str, file: Path):
        with open(file, 'w') as opened_file:
            opened_file.write(text)


class StpmtrError(BaseException):
    def __init__(self, controller: StpMtrController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
