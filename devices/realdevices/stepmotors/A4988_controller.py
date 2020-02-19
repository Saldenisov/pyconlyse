"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""
from typing import List, Tuple, Union, Iterable, Dict, Any, Callable

from gpiozero import LED
import logging
from time import sleep
from utilities.tools.decorators import development_mode
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = True

class StpMtrCtrl_a4988_4axes(StpMtrController):
    ON = 0
    OFF = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ttl = None  # to make controller work when dev_mode is ON
        self._pins = []

    def _activate_axis(self, axis: int, flag: int) -> Tuple[bool, str]:
        if 2 in self._axes_status:
            idx = self._axes_status.index(2)
            res, comments = False, f'Stop axis {idx} to be able activate axis {axis}'
        else:
            try:
                idx = self._axes_status.index(1)
                self._deactivate_relay(idx)
                _, _ = self._change_axis_status(idx, 0)  # Deactivate another active axis
                comments = f'Axis {idx} is deactivated'
            except ValueError as e:
                res, comments = False, ' Nothing to deactivate.'
            _, _ = self._change_axis_status(axis, flag)
            self._activate_relay(axis)
            res, comments = True, f'axis {axis} state is {flag}.{comments}'
        return res, comments

    def _activate(self, flag: bool) -> Tuple[bool, str]:
        return super()._activate(flag)

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect(flag)

    def _change_axis_status(self, axis: int, flag: int, force=False) -> Tuple[bool, str]:
        return super()._change_axis_status(axis, flag, force)

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

    def _move_axis_to(self, axis: int, pos: int, how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis, 2)
        if res:
            if pos - self._pos[axis] > 0:
                dir = 1
                self._direction('top')
            else:
                dir = -1
                self._direction('bottom')
            steps = int(abs(pos - self._pos[axis]))
            self._enable_controller()
            width = self._TTL_width[axis] / self._microsteps
            delay = self._delay_TTL[axis] / self._microsteps
            for i in range(steps):
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
            _, _ = self._change_axis_status(axis, 1, force=True)
            self._disable_controller()
            StpMtrController._write_to_file(str(self._pos), self._file_pos)
            return True, comments
        else:
            return False, comments

    def _stop_axis(self, axis) -> Tuple[bool, str]:
        return self._change_axis_status(axis, 1, force=True)

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        return super()._set_parameters(extra_func=[self._setup])

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
        except (KeyError, SyntaxError) as e:
            self.logger.error(e)
            return False, f'_set_move_parameters() did not work, DB cannot be read {str(e)}'

    #Contoller hardware functions
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
    def _enable_controller(self):
        self._set_led(self._enable, 0)
        sleep(0.05)

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

    @development_mode(dev=dev_mode, with_return=None)
    def _set_led(self, led: LED, value: Union[bool, int]):
        if value == 1:
            led.on()
        elif value == 0:
            led.off()
        else:
            self.logger.info(f'func _set_led value {value} is not known')

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
