from abc import abstractmethod
from os import path
from devices.devices import Service
from typing import Union, Dict, Iterable, List, Tuple, Any, ClassVar
import logging

module_logger = logging.getLogger(__name__)


class StpMtrController(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._axes_number = 1
        self._pos: List[float] = []  # Keeps actual position for axes for controller
        self._axes_status: List[bool] = []  # Keeps axes status, active or not
        self._limits: List[Tuple[int, int]] = []  # Limits for each axis
        self._file_pos = f"{self.name}:positions"
        if not path.exists(self._file_pos):
            file = open(self._file_pos, "w+")
            file.close()
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
        """To be realized in real controllers"""
        pass

    def _set_number_axes(self):
        try:
            axes_number = int(self.config.config_to_dict(self.name)['Parameters']['axes_number'])
            self._axes_number = axes_number
        except KeyError:
            raise stpmtr_error(self, text="Axes_number could not be set, axes_number field is absent in the DB")
        except ValueError:
            raise stpmtr_error(self, text="Check axes number in DB, must be axex_number = 1 or any number")

    def _set_limits(self):
        try:
            limits: List[Tuple[Union[float, int]]] = []
            limits_s: List[str] = self.config.config_to_dict(self.name)['Parameters']['limits'].replace(" ", "").split('),(')
            for exp in limits_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                limits.append(val)
            self._limits = limits
        except KeyError:
            raise stpmtr_error(self, text="Limits could not be set, limits field is absent in the DB")
        except (TypeError, SyntaxError):
            raise stpmtr_error(self, text="Check limits field in DB, must be limits = (x1, x2), (x3, x4),...")


    @abstractmethod
    def _get_pos(self) -> List[Union[int, float]]:
        """Returns [] if controller not available"""
        return []

    def _get_pos_from_file(self) -> List[Union[int, float]]:
        # TODO: to be realized, check if there is n values, where n = self._axes_number
        with open(self._file_pos) as f:
            content = f.readlines()
        if len(content) != 0:
            values: List[str] = content[0].split(',')
            pos: List[Union[float, int]] = []
            for val in values:
                pos.append(xxxx)
            if len(pos) < self._axes_number:
                self.logger.error(f"There is less positions {len(pos)} in log file, that axes_number {self._axes_number} in DB")
                return []
            else:
                return pos
        else:
            return []

    def _set_pos(self):
        controller_pos: List[Union[int, float]] = self._get_pos()
        file_pos: List[Union[int, float]] = self._get_pos_from_file()
        if len(controller_pos) == 0 and len(file_pos):
            self.logger.error("Axes positions could not be set, setting everything to 0")
            self._pos = [0.0] * self._axes_number
            if controller_pos != file_pos:
                self.logger.error("Last log positions do not correspond to controller ones. CHECK REAL POSITIONS")
        elif len(controller_pos) == 0:
            self._pos = file_pos
        else:
            self._pos = controller_pos


    def _set_preset_values(self):
        try:
            preset_values: List[Tuple[Union[float, int]]] = []
            preset_values_s: List[str] = self.config.config_to_dict(self.name)['Parameters']['preset_values'].replace(" ", "").split('),(')
            for exp in preset_values_s:
                val = eval(exp)
                if not isinstance(val, tuple):
                    raise TypeError()
                preset_values.append(val)
            self._limits = preset_values
        except KeyError:
            raise stpmtr_error(self, text="Preset values could not be set, preset_values field is absent in the DB")
        except (TypeError, SyntaxError):
            raise stpmtr_error(self, text="Check preset_values field in DB, must be Preset values = (x1, x2), (x3, x4, x1, x5),...")

    def _set_parameters(self) -> Tuple[bool, str]:
        try:
            self._set_number_axes()
            self._set_axes_status()
            self._set_limits()
            self._set_pos()
            self._set_preset_values()
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


