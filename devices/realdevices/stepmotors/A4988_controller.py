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

from gpiozero import LED
from devices.devices import Service
import logging
from time import sleep
from deprecated import deprecated
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)



class StpMtrCtrl_a4988_4axes(StpMtrController):
    ON = 0
    OFF = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        res, comments = self._setup_pins()
        if res:
            self.device_status.active = flag
            return True, f'{self.id}:{self.name} active state is {flag}'
        else:
            self.device_status.active = False
            return True, f'{self.id}:{self.name} active state is {False}; {comments}'

    def _set_controller_activity(self):
        self.device_status.active = True

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
            if 2 in self._axes_status:
                return False, f'Cannot deactivate other axis while it is running'
            else:
                try:
                    idx = self._axes_status.index(1)
                    self._axes_status[idx] = 0  #Deactivate another axis
                    self._deactivate_relay(idx)
                except ValueError:
                    pass
                finally:
                    self._axes_status[axis] = flag
                    self._activate_relay(axis)
                    return {'axis': axis, 'flag': flag}, f'axis {axis} state is {flag}, axis {idx} is deactivated'
        else:
            return False, comments

    def move_axis_to(self, axis: int, pos: float, how='absolute') -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
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
                    if pos - self._pos[axis] >= 0:
                        dir = 1
                        self._direction('top')
                    else:
                        dir = -1
                        self._direction('bottom')
                    steps = int(abs(pos - self._pos[axis]))
                    print(f'steps{steps} axis{axis} dir {dir} {self._pos}')

                    self._enable_controller()
                    self._activate_relay(axis)

                    width = self._TTL_width[axis] / self._microsteps[axis]
                    delay = self._delay_TTL[axis] / self._microsteps[axis]

                    for _ in range(steps):
                        if self._axes_status[axis] == 2:
                            for _ in range(self._microsteps[axis]):
                                self._set_led(self._ttl, 1)
                                sleep(width)
                                self._set_led(self._ttl, 0)
                                sleep(delay)
                            self._pos[axis] = self._pos[axis] + dir
                        else:
                            comments = 'movement was interrupted'
                            break
                    self._disable_controller()
                    self._deactivate_all_relay()
                    self._axes_status[axis] = 1
                    sleep(0.3)
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
        comments = 'Controller state is obtained.'
        return {'device_status': self.device_status, 'axes_status': self._axes_status, 'positions': self._pos}, comments

    def description(self):
        # TODO: read from DB
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
        # TODO: to be done something with this
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
        return self._get_number_axes_db()

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._get_limits_db()

    def _get_pos(self) -> List[Union[int, float]]:
        if self._pos:
            return self._pos
        else:
            return [0] * self._axes_number

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._get_preset_values_db()

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
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'

    def _check_axis_active(self, axis: int) -> bool:
        comments = ''
        if self._axes_status[axis] > 0:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _setup_pins(self):
        parameters = self.get_settings('Parameters')
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

        self._ttl = LED(TTL_pin,)
        self._dir = LED(DIR_pin)
        self._enable = LED(enable_pin)
        self._ms1 = LED(ms1)
        self._ms2 = LED(ms2)
        self._ms3 = LED(ms3)
        self._relayIa = LED(relayIa, initial_value=True)
        self._relayIb = LED(relayIb, initial_value=True)
        self._relayIIa = LED(relayIIa, initial_value=True)
        self._relayIIb = LED(relayIIb, initial_value=True)
        self._relayIIIa = LED(relayIIIa, initial_value=True)
        self._relayIIIb = LED(relayIIIb, initial_value=True)
        self._relayIVa = LED(relayIVa, initial_value=True)
        self._relayIVb = LED(relayIVb, initial_value=True)

    def _setup_led_parameters(self, com='Full'):
        steps = [(90, 0), (90, 0), (90, 0), (90, 0)],
        self._TTL_width = {1: 30. / 1000,
                           2: 3. / 1000,
                           3: 5. / 1000,
                           4: 5. / 1000}  # s
        self._delay_TTL = {1: 5. / 1000,
                           2: 1. / 1000,
                           3: 5. / 1000,
                           4: 5. / 1000}  # s
        microstep_settings = {'Full': [[0, 0, 0], 1],
                              'Half': [[1, 0, 0], 2],
                              'Quarter': [[0, 1, 0], 4],
                              'Eight': [[1, 1, 0], 8],
                              'Sixteen': [[1, 1, 1], 16]}
        self._set_led(self._ms1, microstep_settings[com][0][0])
        self._set_led(self._ms2, microstep_settings[com][0][1])
        self._set_led(self._ms3, microstep_settings[com][0][2])
        self._microsteps = microstep_settings[com][1]


    def _set_led(self, led: LED, value: Union[bool, int]):
        if value == 1:
            led.on()
        elif value == 0:
            led.off()
        else:
            self.logger.info(f'func _set_led value {value} is not known')

    def _enable_controller(self):
        self._set_led(self._enable, 0)
        sleep(0.05)

    def _disable_controller(self):
        self._set_led(self._enable, 1)
        sleep(0.05)

    def _direction(self, orientation='top'):
        if orientation == 'top':
            self._set_led(self._dir, 1)
        elif orientation == 'bottom':
            self._set_led(self._dir, 0)
        sleep(0.05)

    def _activate_relay(self, n: int):
        # TODO: better to remove _deactivate_all_relay and use _deactivate_relay
        self._deactivate_all_relay()
        if n == 0:
            self._set_led(self._relayIa, StpMtrCtrl_a4988_4axes.ON)
            self._set_led(self._relayIb, StpMtrCtrl_a4988_4axes.ON)
        elif n == 1:
            self._set_led(self._relayIIa, StpMtrCtrl_a4988_4axes.ON)
            self._set_led(self._relayIIb, StpMtrCtrl_a4988_4axes.ON)
        elif n == 2:
            self._set_led(self._relayIIIa, StpMtrCtrl_a4988_4axes.ON)
            self._set_led(self._relayIIIb, StpMtrCtrl_a4988_4axes.ON)
        elif n == 3:
            self._set_led(self._relayIVa, StpMtrCtrl_a4988_4axes.ON)
            self._set_led(self._relayIVb, StpMtrCtrl_a4988_4axes.ON)
        sleep(0.1)

    def _deactivate_relay(self, n: int):
        if n == 0:
            self._set_led(self._relayIa, StpMtrCtrl_a4988_4axes.OFF)
            self._set_led(self._relayIb, StpMtrCtrl_a4988_4axes.OFF)
        elif n == 1:
            self._set_led(self._relayIIa, StpMtrCtrl_a4988_4axes.OFF)
            self._set_led(self._relayIIb, StpMtrCtrl_a4988_4axes.OFF)
        elif n == 2:
            self._set_led(self._relayIIIa, StpMtrCtrl_a4988_4axes.OFF)
            self._set_led(self._relayIIIb, StpMtrCtrl_a4988_4axes.OFF)
        elif n == 3:
            self._set_led(self._relayIVa, StpMtrCtrl_a4988_4axes.OFF)
            self._set_led(self._relayIVb, StpMtrCtrl_a4988_4axes.OFF)
        sleep(0.1)

    def _deactivate_all_relay(self):
        for axis in range(4):
            self._deactivate_relay(axis)
        sleep(0.1)
