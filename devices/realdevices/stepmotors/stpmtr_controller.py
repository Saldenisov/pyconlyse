from devices.devices import Service
from abc import abstractmethod
from typing import Union, Dict, Iterable, List, Tuple, Any, ClassVar
import logging

module_logger = logging.getLogger(__name__)


class StpMtrController(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pos: List[float] = []  # Keeps actual position for axes for controller
        self._axes_status: List[bool] = []  # Keeps axes status, active or not
        self._limits: List[Tuple[int, int]] = []  # Limits for each axis
        self._set_parameters()  # OBLIGATORY STEP

    @abstractmethod
    def activate(self):
        pass

    @abstractmethod
    def activate_axis(self, axis: int, flag: bool) -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
        pass

    @abstractmethod
    def deactivate(self):
        pass

    @abstractmethod
    def description(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def power(self, flag: bool):
        pass

    @abstractmethod
    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def move_to(self, axis: int, pos: Union[float, int], how='absolute') -> Tuple[Union[bool,
                                                                            Dict[str, Union[int, float, str]]], str]:
        pass

    @abstractmethod
    def get_pos(self, axis: int) -> Tuple[Union[Dict[str, Union[int, float, str]], str]]:
        pass

    @abstractmethod
    def get_controller_state(self) -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        pass

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, value):
        # TODO: when pos is updated, it is saved into the file
        self._pos = value

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        """"These functions are default for any stpmtr controller
        e.g.: A9098, OWIS controller"""
        return {'activate_controller': {'flag': True},
                'activate_axis': {'axis': 0, 'flag': True},
                'move_to': {'axis': 0, 'pos': 0.0, 'how': 'absolute/relative'},
                'get_pos': {'axis': 0},
                'get_controller_state': {}
                }

    def _check_axis(self, axis: int) -> Tuple[bool, str]:
        res, comments = self._check_axis_range(axis)
        if res:
            return self._check_axis_active(axis)
        else:
            return res, comments

    def _check_axis_active(self, axis: int) -> Tuple[bool, str]:
        comments = ''
        if self._axes_status[axis]:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _check_axis_range(self, axis: int) -> Tuple[bool, str]:
        comments = ''
        if axis in range(self._axis_number):
            return True, comments
        else:
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'\

    @abstractmethod
    def _set_axes_status(self):
            pass

    def _set_number_axes(self):
        pass

    def _set_limits(self):
        try:
            limits_s: str = self.config.config_to_dict(self.name)['Parameters']['limits']
            limits: List[Tuple[Union[float, int]]] = limits_s.replace(" ", "").split('),(')
            return limits
        except KeyError:
            raise stpmtr_error(self, text="Limits could not be set, limits filed is absent in the DB")

    @abstractmethod
    def _get_pos(self) -> List[Union[int, float]]:
        # Read from hardware controller if possible and compare it with file
        pass

    def _get_pos_from_file(self) -> List[Union[int, float]]:
        # TODO: to be realized
        return []

    def _set_pos(self):
        pass

    def _set_preset_values(self):
        try:
            preset_values: str = self.config.config_to_dict(self.name)['Controller_parameters']['preset_values']
        except KeyError:
            return ()
        return

    def _set_parameters(self) -> Tuple[bool, str]:
        try:
            self._set_axes_status()
            self._set_number_axes()
            self._set_limits()
            self._set_pos()
        except stpmtr_error as e:
            self.logger.error(e)
            return False, str(e)

    def _within_limits(self, axis: int, pos: Union[int, float]) -> Tuple[bool, str]:
        if pos>=self._limits[axis][0] and pos<=self._limits[axis][1]:
            return True, ''
        else:
            comments = f'pos: {pos} for axis {axis} is in the range {self._limits[axis]}'
            return False, comments


class stpmtr_error(BaseException):
    def __init__(self, controller: StpMtrController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')


