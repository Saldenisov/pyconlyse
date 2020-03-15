from abc import abstractmethod
from os import path
from pathlib import Path
from utilities.data.datastructures.mes_independent import CmdStruct
from errors.myexceptions import DeviceError
from devices.devices import Service
from typing import Union, Dict, List, Tuple, Any, Callable
from utilities.data.datastructures.mes_independent.devices_dataclass import FuncActivateOutput
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import (AxisStpMtr, FuncActivateAxisOutput, FuncGetPosOutput,
                                                                            FuncMoveAxisToOutput, FuncStopAxisOutput,
                                                                            FuncGetStpMtrControllerStateOutput,
                                                                            StpMtrDescription)
import logging

module_logger = logging.getLogger(__name__)


class StpMtrController(Service):
    """
    See Service for more functions
    These functions are default for any step motor controller, e.g.: A4098, OWIS, Standa
    """
    ACTIVATE_AXIS = CmdStruct('activate_axis', {'axis': 0, 'flag': True})
    GET_POS = CmdStruct('get_pos', {'axis': 0})
    MOVE_AXIS_TO = CmdStruct('move_axis_to', {'axis': 0, 'pos': 0.0, 'how': 'absolute/relative'})
    STOP_AXIS = CmdStruct('stop_axis', {'axis': 0})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._axes_number: int = 0
        self.axes: Dict[int, AxisStpMtr] = dict()  # {device_id: AxisStpMtr()}
        self._file_pos = Path(__file__).resolve().parents[0] / f"{self.name}:positions.stpmtr".replace(":","_")
        self._parameters_set_hardware = False
        if not path.exists(self._file_pos):
            try:
                file = open(self._file_pos, "w+")
                file.close()
            except Exception as e:
                self.logger.error(e)

        res, comments = self._set_parameters()  # Set parameters from DB first and after connection is done update
                                                # from hardware controller if possible
        if not res:
            raise StpMtrError(self, comments)

    def available_public_functions(self) -> List[CmdStruct]:
        return super().available_public_functions() + [StpMtrController.ACTIVATE_AXIS, StpMtrController.GET_POS,
                                                       StpMtrController.MOVE_AXIS_TO, StpMtrController.STOP_AXIS]

    def activate(self, flag: bool) -> FuncActivateOutput:
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:  # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters()  # This must be realized for all controllers
                    if res:
                        self.device_status.active = True
            else:
                res, comments = self._connect(False)
                for axis_id, axis in self.axes.items():
                    if axis.status == 2:
                        comments = f'Axis {axis_id} is moving. Cannot set controller active state to {flag}.'
                        flag = True
                self.device_status.active = flag
        info = f'{self.id}:{self.name} active state is {self.device_status.active}.{comments}'
        self.logger.info(info)
        return FuncActivateOutput(comments=info, device=self, func_success=res)

    def activate_axis(self, axis_id: int, flag: int) -> FuncActivateAxisOutput:
        """
        :param axis_id: 0-n
        :param flag: 0=non-active, 1=ready to work, 2=running
        :return: res, comments='' if True, else error_message
        """
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
        self.logger.info(info)
        return FuncActivateAxisOutput(axes=self.axes_essentials, comments=info, device=self, func_success=res)

    @property
    def _axes_names(self) -> List[str]:
        return [axis.name for axis in self.axes.values()]

    @property
    def axes_essentials(self):
        essentials = {}
        for axis_id, axis in self.axes.items():
            essentials[axis_id] = axis.short()
        return essentials

    @property
    def _axes_limits(self) -> List[Tuple[int]]:
        return [axis.limits for axis in self.axes.values()]

    @property
    def _axes_status(self) -> List[int]:
        return [axis.status for axis in self.axes.values()]

    @property
    def _axes_positions(self) -> List[Union[int, float]]:
        return [axis.position for axis in self.axes.values()]

    @property
    def _axes_preset_value(self) -> List[Union[int, float]]:
        return [axis.position for axis in self.axes.values()]

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
            return False, f'Axis id={axis_id}, name={self.axes[axis_id].name} is out of range={self.axes.keys()}.'

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
        FLAGS = [0, 1, 2]
        if flag not in FLAGS:
            return False, f'Wrong flag {flag} was passed. FLAGS={FLAGS}'
        else:
            return True, ''

    def _check_controller_activity(self):
        if self.device_status.active:
            return True, ''
        else:
            return False, f'Controller is not active. Power is {self.device_status.power}'

    def description(self) -> StpMtrDescription:
        """
        Description with important parameters
        :return: StpMtrDescription with parameters essential for understanding what this device is used for
        """
        try:
            parameters = self.get_settings('Parameters')
            return StpMtrDescription(axes=self.axes, info=parameters['info'], GUI_title=parameters['title'])
        except (KeyError, DeviceError) as e:
            return StpMtrError(self, f'Could not set description of controller from DB: {e}')

    @abstractmethod
    def GUI_bounds(self) -> Dict[str, Any]:
        """
        TODO: ????
        :return:
        """
        pass

    @abstractmethod
    def _get_axes_status(self) -> List[int]:
        pass

    def _get_axes_status_db(self) -> List[int]:
        return [0] * self._axes_number

    def get_controller_state(self) -> FuncGetStpMtrControllerStateOutput:
        """
        State of cotroller is returned
        :return:  FuncOutput
        """
        comments = f'Controller is {self.device_status.active}. Power is {self.device_status.power}. ' \
                   f'Axes are {self._axes_status}'
        return FuncGetStpMtrControllerStateOutput(axes=self.axes, device=self, comments=comments, func_success=True)

    @abstractmethod
    def _get_number_axes(self) -> int:
        pass

    def _get_number_axes_db(self) -> int:
        try:
            return int(self.get_settings('Parameters')['axes_number'])
        except KeyError:
            raise StpMtrError(self, text="Axes_number could not be set, axes_number field is absent in the DB")
        except (ValueError, SyntaxError):
            raise StpMtrError(self, text="Check axes number in DB, must be axex_number = 1 or any number")

    def get_pos(self, axis_id: int) -> FuncGetPosOutput:
        res, comments = self._check_axis(axis_id)
        if res:
            pos = self.axes[axis_id].position
        return FuncGetPosOutput(func_success=res, comments=comments, axes=self.axes_essentials)

    def move_axis_to(self, axis_id: int, pos: Union[float, int], how='absolute') -> FuncMoveAxisToOutput:
        res, comments = self._check_axis(axis_id)
        chk_axis = res
        if res:
            res, comments = self._check_controller_activity()
        if res:
            if how == 'relative':
                pos = self.axes[axis_id].position + pos
            res, comments = self._is_within_limits(axis_id, pos)
        if res:
            if self.axes[axis_id].status == 1:
                res, comments = self._move_axis_to(axis_id, pos, how)
            elif self.axes[axis_id].status == 2:
                res, comments = False, f'Axis {axis_id} is running. Please, stop it before new request.'
        if chk_axis:
            pos = self.axes[axis_id].position
        else:
            pos = None
        return FuncMoveAxisToOutput(axes=self.axes_essentials)

    @abstractmethod
    def _move_axis_to(self, axis_id: int, pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        pass

    def _move_all_home(self) -> Tuple[bool, str]:
        """
        move all lines to zero
        :return: res, comments
        """
        for axis_id in self.axes.keys():
            self.logger.info(f'Moving {axis_id} back to 0')
            _, _ = self._change_axis_status(axis_id, 1)
            _, _ = self.move_axis_to(axis_id, 0)
            _, _ = self._change_axis_status(axis_id, 0, force=True)

    def _get_axes_ids_db(self):
        try:
            ids: List[int] = []
            ids_s: List[str] = self.get_settings('Parameters')['axes_ids'].replace(" ", "").split(';')
            for exp in ids_s:
                val = eval(exp)
                if not isinstance(val, int):
                    raise TypeError()
                ids.append(val)
            if len(ids) != self._axes_number:
                raise StpMtrError(self, f'Number of axes_ids {len(ids)} is not equal to '
                                        f'axes_number {self._axes_number}.')
            return ids
        except KeyError:
            raise StpMtrError(self, text="Axes ids could not be set, axes_ids field is absent in the DB.")
        except (TypeError, SyntaxError):
            raise StpMtrError(self, text="Check axes_ids field in DB, must be integer.")

    def _get_axes_names_db(self):
        try:
            names: List[int] = []
            names_s: List[str] = self.get_settings('Parameters')['axes_names'].replace(" ", "").split(';')
            for exp in names_s:
                val = exp
                if not isinstance(val, str):
                    raise TypeError()
                names.append(val)
            if len(names) != self._axes_number:
                raise StpMtrError(self, f'Number of axes_names {len(names)} is not equal to '
                                        f'axes_number {self._axes_number}.')
            return names
        except KeyError:
            raise StpMtrError(self, text="Axes names could not be set, axes_names field is absent in the DB.")
        except (TypeError, SyntaxError):
            raise StpMtrError(self, text="Check axes_names field in DB.")

    @abstractmethod
    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        pass

    def _get_limits_db(self) -> List[Tuple[Union[float, int]]]:
        try:
            limits: List[Tuple[Union[float, int]]] = []
            limits_s: List[str] = self.get_settings('Parameters')['limits'].replace(" ", "").split(';')
            for exp in limits_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                limits.append(val)
            return limits
        except KeyError:
            raise StpMtrError(self, text="Limits could not be set, limits field is absent in the DB")
        except (TypeError, SyntaxError):
            raise StpMtrError(self, text="Check limits field in DB, must be limits = (x1, x2), (x3, x4),...")

    def _set_limits(self):
        if self.device_status.connected:
            limits = self._get_limits()
        else:
            limits = self._get_limits_db()
        for id, limit in zip(self.axes.keys(), limits):
            self.axes[id].limits = limit

    @abstractmethod
    def _get_positions(self) -> List[Union[int, float]]:
        pass

    def _get_positions_file(self) -> List[Union[int, float]]:
        """Return [] if error (file is empty, number of positions is less than self._axes_number"""
        try:
            with open(self._file_pos, 'r') as file_pos:
                pos_s = file_pos.readline()
            if not pos_s:
                raise StpMtrError('file with pos is empty')
            pos = eval(pos_s)
            if not isinstance(pos, list):
                raise StpMtrError('is not a list')
            else:
                if len(pos) != len(self.axes):
                    raise StpMtrError(f"There is {len(pos)} positions in file, instead of {len(self.axes)}")
                else:
                    for val in pos:
                        if not (isinstance(val, int) or isinstance(val, float)):
                            raise StpMtrError(f"val {val} is not a number")
                    return pos
        except (StpMtrError, FileNotFoundError, SyntaxError) as e:
            self.logger.error(f'in _get_pos_file error: {e}')
            return []

    @abstractmethod
    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        pass

    def _get_preset_values_db(self) -> List[Tuple[Union[int, float]]]:
        try:
            preset_values: List[Tuple[Union[float, int]]] = []
            preset_values_s: List[str] = self.get_settings('Parameters')['preset_values'].replace(" ", "").split(';')
            for exp in preset_values_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                preset_values.append(val)
            return preset_values
        except KeyError:
            raise StpMtrError(self, text="Preset values could not be set, preset_values field is absent in the DB")
        except (TypeError, SyntaxError):
            raise StpMtrError(self, text="Check preset_values field in DB, must be Preset values = (x1, x2), (x3, x4, x1, x5),...")

    def _is_within_limits(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        if self.axes[axis_id].limits[0] <= pos <= self.axes[axis_id].limits[1]:
            return True, ''
        else:
            comments = f'Desired pos: {pos} for axis id={axis_id}, name={self.axes[axis_id].name} is not ' \
                       f'in the range {self.axes[axis_id].limits}'
            return False, comments

    def _set_axes_ids(self):
        # Axes ids must be in ascending order
        ids = self._get_axes_ids_db()
        ids_c = ids.copy()
        if ids_c != ids:
            e = StpMtrError(self, text=f'Axes indexes must be ascending order.')
            self.logger.error(e)
            raise e
        for id_a in ids:
            self.axes[id_a] = AxisStpMtr(id=id_a)

    def _set_axes_names(self):
        names = self._get_axes_names_db()
        keys = list(self.axes.keys())
        for id, name in zip(self.axes.keys(), names):
            self.axes[id].name = name

    def _set_axes_status(self):
        if self.device_status.connected:
            statuses = self._get_axes_status()
        else:
            statuses = self._get_axes_status_db()

        for id, status in zip(self.axes.keys(), statuses):
            self.axes[id].status = status

    @abstractmethod
    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        """
        This function sets user-defined positions into hardware controller.
        :param positions: list of positions passed to hardware controller
        :return:
        """
        return True, ''

    def _set_number_axes(self):
        if self.device_status.connected:
            axes_number = self._get_number_axes()
        else:
            axes_number = self._get_number_axes_db()
        self._axes_number = axes_number

    def _set_positions_axes(self):
        controller_pos: List[Union[int, float]] = []
        if self.device_status.connected:
             controller_pos = self._get_positions()
        file_pos: List[Union[int, float]] = self._get_positions_file()
        if len(controller_pos) == 0 and len(file_pos) == 0:
            self.logger.error("Axes positions could not be set, setting everything to 0")
        elif not controller_pos:
            positions = file_pos
        elif controller_pos != file_pos:
            self.logger.error("Last files positions do not correspond to controller ones. "
                              "Controller pos set to file pos.")
            res, comments = self._set_controller_positions(positions=file_pos)
            if res:
                positions = file_pos
            else:
                positions = controller_pos
                self.logger.error(f'_set_positions_axes: {comments}')
        else:
            positions = controller_pos
        for id, pos in zip(self.axes.keys(), positions):
            self.axes[id].position = pos

    def _set_preset_values(self):
        if self.device_status.connected:
            preset_values = self._get_preset_values()
        else:
            preset_values = self._get_preset_values_db()
        for id, value in zip(self.axes.keys(), preset_values):
            self.axes[id].preset_values = value

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        try:
            self._set_number_axes()
            self._set_axes_ids()  # Ids must be set first
            self._set_axes_names()
            self._set_axes_status()
            self._set_limits()
            self._set_positions_axes()
            self._set_preset_values()
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
                raise StpMtrError(self, comments)
        except StpMtrError as e:
            self.logger.error(e)
            return False, str(e)

    def stop_axis(self, axis_id: int) -> FuncStopAxisOutput:
        res, comments = self._check_axis(axis_id)
        if res:
            if self.axes[axis_id].status == 2:
                res, comments = self._change_axis_status(axis_id, 1, force=True)
                if res:
                    comments = f'Axis {axis_id} was stopped by user'
            elif self.axes[axis_id].status == 1:
                comments = f'Axis id={axis_id}, name={self.axes[axis_id].name} was already stopped'
        return FuncStopAxisOutput(func_success=res, comments=comments, axes=self.axes_essentials)

    @staticmethod
    def _write_to_file(text: str, file: Path):
        with open(file, 'w') as opened_file:
            opened_file.write(text)


class StpMtrError(BaseException):
    def __init__(self, controller: StpMtrController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')
