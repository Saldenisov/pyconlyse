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
        self._limits: List[Tuple[int]] = []
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

    def execute_com(self, com: str, parameters: dict) -> Iterable[Union[Dict, bool]]:
        if com in self.available_public_functions():
            f = getattr(self, com)
            if parameters.keys() == signature(f).parameters.keys():
                return f(**parameters)
            else:
                return False, f'Incorrect {parameters} were send. Should be {signature(f).parameters.keys()}'

        else:
            return False, f'com: {com} is not available for Service {self.id}. See {self.available_public_functions()}'

    def _set_limits(self) -> Dict:
        # TODO: realize logic. must be read from DB
        return 0

    def _set_pos(self):
        # Read from hardware controller if possible
        pass

    def _set_axes_status(self):
        pass

    def _within_limits(self, axis:int, pos) -> bool:
        comments = ''
        return True, comments

    def _check_axis(self, axis: int) -> bool:
        res, comments = self._check_axis_range(axis)
        if res:
            return self._check_axis_active(axis)
        else:
            return res, comments

    def _check_axis_range(self, axis: int) -> bool:
        comments = ''
        if axis in range(self._axis_number):
            return True, comments
        else:
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'\

    def _check_axis_active(self, axis: int) -> bool:
        comments = ''
        if self._axes_status[axis]:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def activate_axis(self, axis: int, flag: bool):
        chk_axis, comments = self._check_axis_range(axis)
        if chk_axis:
            self._axes_status[axis] = flag
            return {'axis': axis, 'flag': flag}, comments
        else:
            return False, comments

    @abstractmethod
    def move_to(self, axis: int, pos: float, how='absolute')  -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        pass

    @abstractmethod
    def get_pos(self, axis: int) -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        #{'axis': axis, 'pos': self._pos[axis], 'how': how}, comments:
        pass

    @abstractmethod
    def get_controller_state(self)  -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        pass
