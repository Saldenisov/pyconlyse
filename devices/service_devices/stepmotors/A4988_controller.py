"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""
from typing import List, Tuple, Union, Iterable, Dict, Any, Callable, Set

from gpiozero import LED
import logging
from time import sleep
from utilities.datastructures.mes_independent.stpmtr_dataclass import move_angle, move_mm, move_microsteps
from utilities.tools.decorators import development_mode
from utilities.myfunc import error_logger, info_msg
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = True


class StpMtrCtrl_a4988_4axes(StpMtrController):
    ON = 0
    OFF = 1

    def __init__(self, **kwargs):
        self._pins = []
        self._ttl = None  # to make controller work when dev_mode is ON
        super().__init__(**kwargs)

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
            self._set_microsteps_parameters(axis_id)  # Different axes could have different microsteps
            if pos - self.axes[axis_id].position > 0:
                pas = 1
                self._direction('top')
            else:
                pas = -1
                self._direction('bottom')
            steps = int(abs(pos - self.axes[axis_id].position))
            interrupted = False
            self._enable_controller()
            width = self._microstep_settings[self._microsteps][1] * self._TTL_width_corrections[axis_id] / 1000. # must be in ms
            delay = self._microstep_settings[self._microsteps][2] * self._TTL_delay_corrections[axis_id] / 1000.
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

    def _release_hardware(self) -> Tuple[bool, str]:
        try:
            for pin in self._pins:
                pin.close()
            return True, ''
        except Exception as e:
            error_logger(self, self._release_hardware, e)
            return False, f'{e}'

    def _setup(self) -> Tuple[Union[bool, str]]:
        res, comments = self._set_move_parameters_controller()
        if res:
            return self._setup_pins()
        else:
            return res, comments

    def _set_move_parameters_axes(self, must_have_param: Set[str] = None):
        must_have_param = {1: set(['microsteps', 'conversion_step_angle']),
                           2: set(['microsteps', 'conversion_step_angle']),
                           3: set(['microsteps', 'conversion_step_angle']),
                           4: set(['microsteps', 'conversion_step_angle'])}
        return super()._set_move_parameters_axes(must_have_param)

    def _set_move_parameters_controller(self, step=1) -> Tuple[Union[bool, str]]:
        try:
            parameters = self.get_settings('Parameters')
            self._microstep_settings = eval(parameters['microstep_settings'])
            self._TTL_width_corrections = eval(parameters['ttl_width_corrections'])
            self._TTL_delay_corrections = eval(parameters['ttl_delay_corrections'])
            return True, ''
        except (KeyError, SyntaxError) as e:
            error_logger(self, self._set_move_parameters_controller, e)
            return False, f'_set_move_parameters() did not work, DB cannot be read {e}'

    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        return super()._set_controller_positions(positions)

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        if self.device_status.connected:
            return super()._set_parameters(extra_func=[self._setup])
        else:
            return super()._set_parameters()

    #Contoller hardware functions
    @development_mode(dev=dev_mode, with_return=None)
    def _change_relay_state(self, axis_id: int, flag: int):
        if flag:
            if axis_id == 1:
                self._set_led(self._relayIa, StpMtrCtrl_a4988_4axes.ON)
                self._set_led(self._relayIb, StpMtrCtrl_a4988_4axes.ON)
            elif axis_id == 2:
                self._set_led(self._relayIIa, StpMtrCtrl_a4988_4axes.ON)
                self._set_led(self._relayIIb, StpMtrCtrl_a4988_4axes.ON)
            elif axis_id == 3:
                self._set_led(self._relayIIIa, StpMtrCtrl_a4988_4axes.ON)
                self._set_led(self._relayIIIb, StpMtrCtrl_a4988_4axes.ON)
            elif axis_id == 4:
                self._set_led(self._relayIVa, StpMtrCtrl_a4988_4axes.ON)
                self._set_led(self._relayIVb, StpMtrCtrl_a4988_4axes.ON)
            sleep(0.1)
        elif flag == 0:
            if axis_id == 1:
                self._set_led(self._relayIa, StpMtrCtrl_a4988_4axes.OFF)
                self._set_led(self._relayIb, StpMtrCtrl_a4988_4axes.OFF)
            elif axis_id == 2:
                self._set_led(self._relayIIa, StpMtrCtrl_a4988_4axes.OFF)
                self._set_led(self._relayIIb, StpMtrCtrl_a4988_4axes.OFF)
            elif axis_id == 3:
                self._set_led(self._relayIIIa, StpMtrCtrl_a4988_4axes.OFF)
                self._set_led(self._relayIIIb, StpMtrCtrl_a4988_4axes.OFF)
            elif axis_id == 4:
                self._set_led(self._relayIVa, StpMtrCtrl_a4988_4axes.OFF)
                self._set_led(self._relayIVb, StpMtrCtrl_a4988_4axes.OFF)
            sleep(0.1)

    @development_mode(dev=dev_mode, with_return=None)
    def _deactivate_all_relay(self):
        for axis in range(4):
            self._change_relay_state(axis + 1, 0)
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
            info_msg(self, 'INFO', 'setting up the pins')
            parameters = self.get_settings('Parameters')
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
            self.microstep_settings = eval(parameters['microstep_settings'])
            return True, ''
        except (KeyError, ValueError, SyntaxError) as e:
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

    def _set_microsteps_parameters(self, axis_id: int):
        self._set_led(self._ms1, self.microstep_settings[self.axes[axis_id].move_parameters['microsteps']][0][0])
        self._set_led(self._ms2, self.microstep_settings[self.axes[axis_id].move_parameters['microsteps']][0][1])
        self._set_led(self._ms3, self.microstep_settings[self.axes[axis_id].move_parameters['microsteps']][0][2])
