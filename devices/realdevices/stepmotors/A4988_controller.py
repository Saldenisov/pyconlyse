"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""
from typing import List, Tuple, Union, Iterable, Dict, Any

import gpiozero
from devices.devices import Service
import logging
from time import sleep
from deprecated import deprecated
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)



class StpMtrCtrl_a4988_4axes(StpMtrController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        self.device_status.active = flag
        return True, f'{self.id}:{self.name} active state is {flag}'

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        # TODO: realized extension of public functions
        pub_func = super().available_public_functions()
        # pub_func = extend(pub_func, thisclass_public_functions())
        return pub_func

    def activate_axis(self, axis: int, flag: int) -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
        """
        :param axis: 0-4
        :param flag: 0, 1, 2
        :return: Tuple[Union[bool, Dict[str, Union[int, bool]]], str]
        """
        chk_axis, comments = self._check_axis_range(axis)
        if chk_axis:
            self._axes_status[axis] = flag
            return {'axis': axis, 'flag': flag}, f'axis {axis} state is {flag}'
        else:
            return False, comments

    def move_axis_to(self, axis: int, pos: float, how='absolute') -> Tuple[
        Union[bool, Dict[str, Union[int, bool]]], str]:
        chk_axis, comments = self._check_axis(axis)
        if chk_axis:
            if how == 'absolute':
                pass
            elif how == 'relative':
                pos = self._pos[axis] + pos
            else:
                return False, f'how {how} is wrong, could be only absolute and relative'
            chk_lmt, comments = self._is_within_limits(axis, pos)
            if chk_lmt:
                if self._axes_status[axis] == 1:
                    self._axes_status[axis] = 2
                    if pos - self._pos[axis] > 0:
                        dir = 1
                    else:
                        dir = -1
                    steps = int(abs(pos - self._pos[axis]))
                    print(f'steps{steps} axis{axis} dir {dir} {self._pos}')
                    for i in range(steps):
                        if self._axes_status[axis] == 2:
                            self._pos[axis] = self._pos[axis] + dir
                            sleep(0.1)
                        else:
                            comments = 'movement was interrupted'
                            break
                    self._axes_status[axis] = 1
                    return {'axis': axis, 'pos': self._pos[axis], 'how': how}, comments
                else:
                    comments = f'Controller is working on another task. axis:{axis} cannot be moved at this moment'
                    return False, comments
            else:
                return False, comments
        else:
            return False, comments

    def stop_axis(self, axis: int):
        chk_axis, comments = self._check_axis(axis)
        if chk_axis:
            self._axes_status[axis] = 1
            comments = 'stopped by user'
            return {'axis': axis, 'pos': self._pos[axis]}, comments
        else:
            return False, comments

    def get_pos(self, axis=0):
        res, comments = self._check_axis(axis)
        if res:
            return {'axis': axis, 'pos': self._pos[axis]}, comments
        else:
            return False, comments

    def get_controller_state(self):
        comments = ''
        return {'device_status': self.device_status, 'axes_status': self._axes_status, 'positions': self._pos}, comments

    def description(self):
        desc = {'GUI_title': """StpMtrCtrl_A4988_newport, 4 axes""",
                'axes_names': ['0/90 mirror', 'iris', 'filter wheel 1', 'filter wheel 2'],
                'axes_values': [0, 3],
                'ranges': [((0.0, 100.0), (0, 91)),
                           ((-100.0, 100.0), (0, 50)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360))],
                'info': "StpMtrCtrl_A4988_newport, it controls 4 axes"}
        return desc

    def GUI_bounds(self):
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def power(self, flag: bool):
        # TODO: realize
        pass

    def _get_axes_status(self) -> List[int]:
        if self._axes_status:
            return self._axes_status
        else:
            return [0] * self._axes_number

    def _get_number_axes(self) -> int:
        return 4

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return [(0.0, 100.0), (-100.0, 100.0), (0.0, 360), (0.0, 360)]

    def _get_pos(self) -> List[Union[int, float]]:
        if self._pos:
            return self._pos
        else:
            return [0] * self._axes_number

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return [(0, 91),
                (0, 50),
                (0, 45, 90, 135, 180, 225, 270, 315, 360),
                (0, 45, 90, 135, 180, 225, 270, 315, 360)]

    def _is_within_limits(self, axis: int, pos) -> bool:
        comments = ''
        return True, comments

    def _check_axis(self, axis: int) -> bool:
        if self.device_status.active:
            res, comments = self._check_axis_range(axis)
            if res:
                return self._check_axis_active(axis)
            else:
                return res, comments
        else:
            result, comments = (False, 'Device is not active. Activate')

    def _check_axis_range(self, axis: int) -> bool:
        comments = ''
        if axis in range(self._axes_number):
            return True, comments
        else:
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}' \
 \
                    def _check_axis_active(self, axis: int) -> bool:
        comments = ''
        if self._axes_status[axis] > 0:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _setup_pins(self):
        GPIO.setmode(GPIO.BCM)  # choose BCM or BOARD

        TTL_pin = 19
        DIR_pin = 26
        enable_pin = 12
        ms1 = 21
        ms2 = 20
        ms3 = 16
        relayIa = 2  # orange
        relayIb = 3  # red
        relayIIa = 17  # brown hz
        relayIIb = 27  # green
        relayIIIa = 22  # yellow
        relayIIIb = 10  # gray
        relayIVa = 9  # blue
        relayIVb = 11  # green

        GPIO.setup(TTL_pin, GPIO.OUT)
        GPIO.setup(DIR_pin, GPIO.OUT)
        GPIO.setup(enable_pin, GPIO.OUT)
        GPIO.setup(ms1, GPIO.OUT)
        GPIO.setup(ms2, GPIO.OUT)
        GPIO.setup(ms3, GPIO.OUT)
        GPIO.setup(relayIa, GPIO.OUT)
        GPIO.setup(relayIb, GPIO.OUT)
        GPIO.setup(relayIIa, GPIO.OUT)
        GPIO.setup(relayIIb, GPIO.OUT)
        GPIO.setup(relayIIIa, GPIO.OUT)
        GPIO.setup(relayIIIb, GPIO.OUT)
        GPIO.setup(relayIVa, GPIO.OUT)
        GPIO.setup(relayIVb, GPIO.OUT)

        # On/Off for relay normally closed
        On = 0
        Off = 1

        GPIO.output(TTL_pin, 0)
        GPIO.output(DIR_pin, 0)
        GPIO.output(enable_pin, 0)

        GPIO.output(relayIa, Off)
        GPIO.output(relayIb, Off)

        GPIO.output(relayIIa, Off)
        GPIO.output(relayIIb, Off)

        GPIO.output(relayIIIa, Off)
        GPIO.output(relayIIIb, Off)

        GPIO.output(relayIVa, Off)
        GPIO.output(relayIVb, Off)

    def _enable_controller(self):
        GPIO.output(enable_pin, 0)
        sleep(0.05)

    def _disable_controller(self):
        GPIO.output(enable_pin, 1)
        sleep(0.05)

    def _direction(self, orientation='top'):
        if orientation == 'top':
            GPIO.output(DIR_pin, 1)
        elif orientation == 'bottom':
            GPIO.output(DIR_pin, 0)
        sleep(0.05)

    def _activate_relay(self, n):
        """
        activate relay #n
        :return:
        """
        pass

    def _deactivate_all_relay(self):
        pass
        sleep(0.1)

