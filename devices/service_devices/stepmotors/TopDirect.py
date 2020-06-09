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
from enum import Enum
from gpiozero import LED
import logging
from time import sleep
from utilities.tools.decorators import development_mode
from utilities.myfunc import error_logger, info_msg
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = True


class StpMtrCtrl_TopDirect_1axis(StpMtrController):

    class States(Enum):
        ON = 0
        OFF = 1

    class Direction(Enum):
        FORWARD = 'forward'
        BACKWARD = 'backward'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ttl = None  # to make controller work when dev_mode is ON
        self._pins = []

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect(flag)

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        return super()._check_if_connected()

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        def search(axes, status):
            for axis_id, axis in self.axes.items():
                if axis.status == status:
                    return axis_id
            return None

        res, comments = super()._check_axis_flag(flag)
        if res:
            if self.axes[axis_id].status != flag:
                info = ''
                idx = search(self.axes, 1)
                if not idx:
                    idx = search(self.axes, 2)
                    if force and idx:
                        self.axes[idx].status = 1
                        info = f' Axis id={idx}, name={self.axes[idx].name} was stopped.'
                    elif idx:
                        return False, f'Stop axis id={idx} to be able activate axis id={axis_id}. ' \
                                      f'Use force, or wait movement to complete.'
                if idx != axis_id and idx:
                    self.axes[idx].status = 0
                    self._change_relay_state(idx, 0)
                    info = f'Axis id={idx}, name={self.axes[idx].name} is set 0.'

                if not (self.axes[axis_id].status > 0 and flag > 0):  #only works for 0->1, 1->0, 2->0
                    self._change_relay_state(axis_id, flag)
                self.axes[axis_id].status = flag
                res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is set to {flag}.' + info
            else:
                res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is already set to {flag}'
        return res, comments

    def GUI_bounds(self):
        # TODO: to be done something with this
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _get_axes_names(self):
        return self._get_axes_names_db()

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return len(self.axes)

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> List[Union[int, float]]:
        return self._axes_positions

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _move_axis_to(self, axis_id: int, pos: int, how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            if pos - self.axes[axis_id].position > 0:
                pas = 1
                self._direction('top')
            else:
                pas = -1
                self._direction('bottom')
            steps = int(abs(pos - self.axes[axis_id].position))
            interrupted = False
            self._enable_controller()
            width = self._TTL_width[axis_id] / self._microsteps
            delay = self._delay_TTL[axis_id] / self._microsteps
            for i in range(steps):
                if self.axes[axis_id].status == 2:
                    for _ in range(self._microsteps):
                        self._set_led(self._ttl, 1)
                        sleep(width)
                        self._set_led(self._ttl, 0)
                        sleep(delay)
                    self.axes[axis_id].position += pas
                else:
                    res = False
                    comments = f'Movement of Axis with id={axis_id} was interrupted'
                    interrupted = True
                    break
            self._disable_controller()
            _, _ = self._change_axis_status(axis_id, 1, force=True)
            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)
            if not interrupted:
                res, comments = True, f'Movement of Axis with id={axis_id}, name={self.axes[axis_id].name} ' \
                                      f'was finished.'
        return res, comments

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

    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        return super()._set_controller_positions(positions)

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        return super()._set_parameters(extra_func=[self._setup])

    #Contoller hardware functions
    @development_mode(dev=dev_mode, with_return=None)
    def _disable_controller(self):
        if self.device_status.active:
            self._set_led(self._enable, 1)
            sleep(0.05)
            self._set_led(self._enable, 0)

    @development_mode(dev=dev_mode, with_return=None)
    def _direction(self, orientation: Direction):
        if orientation is StpMtrCtrl_TopDirect_1axis.Direction.FORWARD:
            self._set_led(self._dir, 0)
        elif orientation == StpMtrCtrl_TopDirect_1axis.Direction.BACKWARD:
            self._set_led(self._dir, 1)
        sleep(0.05)

    @development_mode(dev=dev_mode, with_return=None)
    def _enable_controller(self):
        if not self.device_status.active:
            self._set_led(self._enable, 1)
            sleep(0.05)
            self._set_led(self._enable, 0)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _setup_pins(self) -> Tuple[Union[bool, str]]:
        try:
            info_msg(self, 'INFO', 'setting up the pins')
            parameters = self.get_settings('Parameters')
            microstep = parameters['microstep']
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
        except (KeyError, ValueError, SyntaxError) as e:
            error_logger(self, self._setup_pins, e)
            return False, f'_setup_pins() did not work, DB cannot be read {str(e)}'

    @development_mode(dev=dev_mode, with_return=None)
    def _set_led(self, led: LED, value: Union[bool, int]):
        if value >= 1:
            led.on()
        elif value == 0:
            led.off()
        else:
            error_logger(self, self._set_led, f'Value {value} is out of range')

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
            return True, '' if len(error) == 0 else str(error)

