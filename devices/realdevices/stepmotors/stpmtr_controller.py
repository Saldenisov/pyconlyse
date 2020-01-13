from devices.devices import Service
from abc import abstractmethod
from typing import Union, Dict, Iterable, List, Tuple, Any
import logging
from inspect import signature
module_logger = logging.getLogger(__name__)

class StpMtrController(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Number of axis controller can support
        self._axis_number = 4
        self._pos: List[float] = []
        self._axes_status: List[bool] = []
        self._limits: List[Tuple[int, int]] = []

        self._set_axes_status()
        self._set_limits()
        self._set_pos()

    @abstractmethod
    def available_public_functions(self) -> Dict[str, Dict[str, Any]]:
        pass

    @abstractmethod
    def description(self) -> Dict[str, Union[str, Any, Iterable[Any]]]:
        pass

    @abstractmethod
    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def activate_axis(self, axis: int, flag: bool) -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
        chk_axis, comments = self._check_axis_range(axis)
        if chk_axis:
            self._axes_status[axis] = flag
            return {'axis': axis, 'flag': flag}, comments
        else:
            return False, comments

    @abstractmethod
    def move_to(self, axis: int, pos: float, how='absolute') -> Tuple[Union[bool,
                                                                            Dict[str, Union[int, float, str]]], str]:
        pass

    @abstractmethod
    def get_pos(self, axis: int) -> Tuple[Union[Dict[str, Union[int, float, str]], str]]:
        pass

    @abstractmethod
    def get_controller_state(self) -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        pass

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

    def _set_axes_status(self):
        pass

    def _set_limits(self) -> Dict:
        # TODO: realize logic. must be read from DB
        return 0

    def _set_pos(self) -> Iterable[bool, str]:
        # Read from hardware controller if possible
        pass

    def _within_limits(self, axis: int, pos) -> bool:
        comments = ''
        return True, comments

