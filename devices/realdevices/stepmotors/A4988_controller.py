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
import logging
from time import sleep
from utilities.tools.decorators import development_mode
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = False

class StpMtrCtrl_a4988_4axes(StpMtrController):
    ON = 0
    OFF = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ttl = None  # to make controller work when dev_mode is ON
        self._pins = []

    def activate(self, flag: bool) -> Tuple[Union[Dict[str, Any], str]]:
        super().activate()
        if flag:
            res, comments = self._setup()
        else:
            res, comments = self._pins_off()
        if res:
            self.device_status.active = flag
            return {'flag': flag, 'func_success': True}, f'{self.id}:{self.name} active state is {flag}'
        else:
            self.device_status.active = False
            return {'flag': False, 'func_success': False}, f'{self.id}:{self.name} active state is {False}; {comments}'


    def _set_controller_activity(self):
        self.device_status.active = False
        self.device_status.sdfpower = True
        self.logger.info(self.device_status)

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
        comments = ''
        if self.device_status.active:
            chk_axis, comments = self._check_axis_range(axis)
            if chk_axis:
                if 2 in self._axes_status:
                    return False, f'Cannot deactivate other axis while it is running'
                else:
                    try:
                        idx = self._axes_status.index(1)
                        self._axes_status[idx] = 0  # Deactivate another axis
                        self._deactivate_relay(idx)
                        comments = f'axis {axis} state is {flag}, axis {idx} is deactivated'
                    except ValueError:
                        pass
                    self._axes_status[axis] = flag
                    self._activate_relay(axis)
                    if not comments:
                        comments = f'axis {axis} state is {flag}'
                    return {'axis': axis, 'flag': flag}, comments
        else:
            return False, f'Device {self.name} is not active, first activate'

    def move_axis_to(self, axis: int, pos: Union[int, float], how='absolute') -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
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

                    width = self._TTL_width[axis] / self._microsteps
                    delay = self._delay_TTL[axis] / self._microsteps

                    for _ in range(steps):
                        if self._axes_status[axis] == 2:
                            for _ in range(self._microsteps):
                                self._set_led(self._ttl, 1)
                                sleep(width)
                                self._set_led(self._ttl, 0)
                                sleep(delay)
                            self._pos[axis] = self._pos[axis] + dir
                        else:
                            comments = 'movement was interrupted'
                            break
                    StpMtrController._write_to_file(str(self._pos), self._file_pos)
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
            self._deactivate_relay[axis]
            self._disable_controller()
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
        #TODO: to be realized in metal someday
        return {'flag': True, 'func_success': True}, f'User switch power manully...this func always return True'

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

    def _is_within_limits(self, axis: int, pos) -> Tuple[Union[bool, str]]:
        comments = ''
        return True, comments

    def _check_axis(self, axis: int) -> Tuple[Union[bool, str]]:
        if self.device_status.active:
            res, comments = self._check_axis_range(axis)
            if res:
                return self._check_axis_active(axis)
            else:
                return res, comments
        else:
            result, comments = (False, 'Device is not active. Activate')

    def _check_axis_range(self, axis: int) -> Tuple[Union[bool, str]]:
        comments = ''
        if axis in range(self._axes_number):
            return True, comments
        else:
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'

    def _check_axis_active(self, axis: int) -> Tuple[Union[bool, str]]:
        comments = ''
        if self._axes_status[axis] > 0:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _setup(self) -> Tuple[Union[bool, str]]:
        res, comments = self._set_move_parameters()
        if res:
            return self._setup_pins()
        else:
            return res, comments

    def _set_move_parameters(self, com='full') -> Tuple[Union[bool, str]]:
        try:
            parameters = self.get_settings('Parameters')
            com = parameters['com']
            self._TTL_width = eval(parameters['ttl_width'])
            self._delay_TTL = eval(parameters['delay_ttl'])
            self._microsteps = eval(parameters['microstep_settings'])[com][1]
            return True, ''
        except (KeyError, SyntaxError, Exception) as e:
            self.logger.error(e)
            return False, f'_set_move_parameters() did not work, DB cannot be read {str(e)}'

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _setup_pins(self) -> Tuple[Union[bool, str]]:
        try:
            self.logger.info('setting up pins')
            parameters = self.get_settings('Parameters')
            com = parameters['com']
            self._ttl = LED(parameters['ttl_pin'])
            self._pins.append(self._ttl)
            self._dir = LED(parameters['dir_pin'])
            self._pins.append(self._dir)
            self._enable = LED(parameters['enable_pin'])
            self._pins.append(self._enable)
            self._ms1 = LED(parameters['ms1'])
            self._pins.append(self._ms1)
            self._ms2 = LED(parameters['ms2'])
            self._pins.append(self._ms2)
            self._ms3 = LED(parameters['ms3'])
            self._pins.append(self._ms3)
            self._relayIa = LED(parameters['relayia'], initial_value=True)
            self._pins.append(self._relayIa)
            self._relayIb = LED(parameters['relayib'], initial_value=True)
            self._pins.append(self._relayIb)
            self._relayIIa = LED(parameters['relayiia'], initial_value=True)
            self._pins.append(self._relayIIa)
            self._relayIIb = LED(parameters['relayiib'], initial_value=True)
            self._pins.append(self._relayIIb)
            self._relayIIIa = LED(parameters['relayiiia'], initial_value=True)
            self._pins.append(self._relayIIIa)
            self._relayIIIb = LED(parameters['relayiiib'], initial_value=True)
            self._pins.append(self._relayIIIb)
            self._relayIVa = LED(parameters['relayiva'], initial_value=True)
            self._pins.append(self._relayIVa)
            self._relayIVb = LED(parameters['relayivb'], initial_value=True)
            self._pins.append(self._relayIVb)
            pins_microstep = eval(parameters['microstep_settings'])
            self._set_led(self._ms1, pins_microstep[com][0][0])
            self._set_led(self._ms2, pins_microstep[com][0][1])
            self._set_led(self._ms3, pins_microstep[com][0][2])
            return True, ''
        except (KeyError, ValueError, SyntaxError, Exception) as e:
            self.logger.error(e)
            return False, f'_setup_pins() did not work, DB cannot be read {str(e)}'

    def _pins_off(self) -> Tuple[Union[bool, str]]:
        if len(self._pins) == 0:
            return True, 'No pins to close()'
        else:
            error = []
            for pin in self._pins:
                try:
                    pin.close()
                except Exception as e:
                    error.append(str(e))
            self._pins = []
            return True, '' if len(error)== 0 else str(error)

    @development_mode(dev=dev_mode, with_return=None)
    def _set_led(self, led: LED, value: Union[bool, int]):
        if value == 1:
            led.on()
        elif value == 0:
            led.off()
        else:
            self.logger.info(f'func _set_led value {value} is not known')

    @development_mode(dev=dev_mode, with_return=None)
    def _enable_controller(self):
        self._set_led(self._enable, 0)
        sleep(0.05)

    @development_mode(dev=dev_mode, with_return=None)
    def _disable_controller(self):
        self._set_led(self._enable, 1)
        sleep(0.05)

    @development_mode(dev=dev_mode, with_return=None)
    def _direction(self, orientation='top'):
        if orientation == 'top':
            self._set_led(self._dir, 1)
        elif orientation == 'bottom':
            self._set_led(self._dir, 0)
        sleep(0.05)

    @development_mode(dev=dev_mode, with_return=None)
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

    @development_mode(dev=dev_mode, with_return=None)
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

    @development_mode(dev=dev_mode, with_return=None)
    def _deactivate_all_relay(self):
        for axis in range(4):
            self._deactivate_relay(axis)
        sleep(0.1)
