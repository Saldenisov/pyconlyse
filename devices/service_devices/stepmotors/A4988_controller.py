"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""
import logging
from time import sleep

from gpiozero import LED

from devices.devices_dataclass import FuncActivateDeviceInput, FuncActivateDeviceOutput
from devices.service_devices.stepmotors.stpmtr_dataclass import *
from devices.devices_dataclass import HardwareDeviceDict
from utilities.myfunc import error_logger, info_msg
from utilities.tools.decorators import development_mode
from .stpmtr_controller import StpMtrController, StpMtrError

module_logger = logging.getLogger(__name__)


dev_mode = True


class StpMtrCtrl_a4988_4axes(StpMtrController):
    ON = 0
    OFF = 1

    def __init__(self, **kwargs):
        kwargs['stpmtr_dataclass'] = A4988AxisStpMtr
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, StandaAxisStpMtr] = HardwareDeviceDict()
        self._pins = []
        self._ttl = None  # to make controller work when dev_mode is ON
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('friendly_name', 'friendly_names', str),
                                                                      ('move_parameters', 'move_parameters', dict),
                                                                      ('limits', 'limits', tuple),
                                                                      ('preset_values', 'preset_values', tuple)],
                                                          extra_func=[self._get_positions_file,
                                                                      self._set_move_parameters_axes,
                                                                      self._set_move_parameters_controller])
        if not res:
            raise StpMtrError(self, comments)

    def activate_device(self, func_input: FuncActivateDeviceInput) -> FuncActivateDeviceOutput:
        device_id = func_input.device_id
        flag = func_input.flag
        res, comments = self._check_device_range(device_id)
        info_msg(self, 'INFO', f'Func "activate_device" is called: {func_input}.')
        if res:
            device = self.hardware_devices[device_id]
            res, comments = self.change_device_status(device_id, flag)
        comments = f'Func "activate_device" is accomplished with success: {res}. {comments}'
        info_msg(self, 'INFO', comments)
        return FuncActivateDeviceOutput(device=self.axes_stpmtr, comments=comments, func_success=res)

    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        def search(axes, status):
            for axis_id_local, axis in axes.items():
                if axis.status == status:
                    return axis_id_local
            return None

        res, comments = False, 'Did not work.'
        axis_id = device.device_id_seq
        if self.axes_stpmtr[axis_id].status != flag:
            info = ''
            idx = search(self.axes_stpmtr, 1)
            if not idx:
                idx = search(self.axes_stpmtr, 2)
                if force and idx:
                    self.axes_stpmtr[idx].status = 1
                    info = f' Axis id={idx}, name={self.axes_stpmtr[idx].name} was stopped.'
                elif idx:
                    res, comments = False, f'Stop axis id={idx} to be able activate axis id={axis_id}. ' \
                                           f'Use force, or wait movement to complete.'
            if idx != axis_id and idx:
                self.axes_stpmtr[idx].status = 0
                self._change_relay_state(idx, 0)
                info = f'Axis id={idx}, name={self.axes_stpmtr[idx].name} is set 0.'

            if not (self.axes_stpmtr[axis_id].status > 0 and flag > 0):  # only works for 0->1, 1->0, 2->0
                self._change_relay_state(axis_id, flag)
            self.axes_stpmtr[axis_id].status = flag
            res, comments = True, f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].name} is set to {flag}.' + info
        else:
            res, comments = True, f'Axis id={axis_id}, name={self.axes_stpmtr[axis_id].name} is already set to {flag}'
        return res, comments

    def _form_devices_list(self) -> Tuple[bool, str]:
        # A4988 chip does not have any means to communicate. Only pins of RPi3 or Rpi4 can be activated.
        for axis_id, axis in self.axes_stpmtr.items():
            axis.device_id_seq = axis_id
        return self._setup_pins()

    def _get_number_hardware_devices(self):
        return 4

    def _get_position_axis(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        # Nothing is necessary, A4988 chip does not have any microstep counter.
        self._write_positions_to_file(positions=self._form_axes_positions())
        return True, ''

    def _move_axis_to(self, device_id: Union[int, str], go_pos: Union[int, float], how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(device_id, 2)
        if res:
            self._set_microsteps_parameters(device_id)  # Different axes could have different microsteps
            axis: A4988AxisStpMtr = self.axes_stpmtr[device_id]
            if go_pos - axis.position > 0:
                pas = 1
                self._direction('top')
            else:
                pas = -1
                self._direction('bottom')
            microsteps = abs(axis.convert_from_to_unit(go_pos - axis.position, axis.basic_unit, MoveType.microstep))
            pos_microsteps = axis.convert_pos_to_unit(MoveType.microstep)
            microsteps_axis = axis.move_parameters['microsteps']
            width = self._microstep_settings[microsteps_axis][1] * axis.move_parameters['TTL_width_correction'] / 1000000. # must be in ms
            delay = self._microstep_settings[microsteps_axis][2] * axis.move_parameters['TTL_delay_correction'] / 1000000.
            interrupted = False
            self._enable_controller()
            for i in range(microsteps):
                if axis.status == 2:
                    self._set_led(self._ttl, 1)
                    sleep(width)
                    self._set_led(self._ttl, 0)
                    sleep(delay)
                    pos_microsteps += pas
                else:
                    res = False
                    comments = f'Movement of Axis with id={device_id} was interrupted'
                    interrupted = True
                    break
            axis.position = axis.convert_to_basic_unit(MoveType.microstep, pos_microsteps)
            self._disable_controller()
            _, _ = self._change_axis_status(device_id, 1, force=True)
            _, _ = self._get_position_axis(device_id)
            if not interrupted:
                res, comments = True, f'Movement of Axis with id={device_id}, name={axis.friendly_name} ' \
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

    def _set_move_parameters_axes(self, must_have_param: Set[str] = None):
        must_have_param = {'Iflip_flop': set(['microsteps', 'conversion_step_angle', 'basic_unit',
                                              'TTL_width_correction', 'TTL_delay_correction']),
                           'IIiris': set(['microsteps', 'basic_unit', 'TTL_width_correction', 'TTL_delay_correction']),
                           'IIIfilter1': set(['microsteps', 'conversion_step_angle', 'basic_unit',
                                              'TTL_width_correction', 'TTL_delay_correction']),
                           'IVfilter2': set(['microsteps', 'conversion_step_angle', 'basic_unit',
                                              'TTL_width_correction', 'TTL_delay_correction'])}
        return super()._set_move_parameters_axes(must_have_param)

    def _set_move_parameters_controller(self) -> Tuple[Union[bool, str]]:
        try:
            self._microstep_settings = eval(self.get_parameters['microstep_settings'])
            return True, ''
        except (KeyError, SyntaxError) as e:
            error_logger(self, self._set_move_parameters_controller, e)
            return False, f'_set_move_parameters did not work, DB cannot be read: {e}.'

    def _set_pos_axis(self, device_id: Union[int, str], pos: Union[int, float]) -> Tuple[bool, str]:
        self.axes_stpmtr[device_id].position = pos
        return True, ''

    #Contoller hardware functions
    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _change_relay_state(self, axis_id: int, flag: int) -> Tuple[bool, str]:
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
        return True, ''

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _deactivate_all_relay(self) -> Tuple[bool, str]:
        for axis in range(4):
            self._change_relay_state(axis + 1, 0)
        sleep(0.1)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _disable_controller(self) -> Tuple[bool, str]:
        return self._set_led(self._enable, 1)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _direction(self, orientation='top') -> Tuple[bool, str]:
        if orientation == 'top':
            return self._set_led(self._dir, 1)
        elif orientation == 'bottom':
            return self._set_led(self._dir, 0)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _enable_controller(self) -> Tuple[bool, str]:
        return self._set_led(self._enable, 0)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _setup_pins(self) -> Tuple[bool, str]:
        try:
            info_msg(self, 'INFO', 'setting up the pins')
            parameters = self.get_parameters
            self._ttl = LED(parameters['TTL_pin'])
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
            self._relayIa = LED(parameters['relayIa'], initial_value=True)
            self._pins.append(self._relayIa)
            self._relayIb = LED(parameters['relayIb'], initial_value=True)
            self._pins.append(self._relayIb)
            self._relayIIa = LED(parameters['relayIIa'], initial_value=True)
            self._pins.append(self._relayIIa)
            self._relayIIb = LED(parameters['relayIIb'], initial_value=True)
            self._pins.append(self._relayIIb)
            self._relayIIIa = LED(parameters['relayIIIa'], initial_value=True)
            self._pins.append(self._relayIIIa)
            self._relayIIIb = LED(parameters['relayIIIb'], initial_value=True)
            self._pins.append(self._relayIIIb)
            self._relayIVa = LED(parameters['relayIVa'], initial_value=True)
            self._pins.append(self._relayIVa)
            self._relayIVb = LED(parameters['relayIVb'], initial_value=True)
            self._pins.append(self._relayIVb)
            self.microstep_settings = eval(parameters['microstep_settings'])
            return True, ''
        except (KeyError, ValueError, SyntaxError) as e:
            error_logger(self, self._setup_pins, e)
            return False, f'_setup_pins() did not work, DB cannot be read {str(e)}.'

    @development_mode(dev=dev_mode, with_return=None)
    def _set_led(self, led: LED, value: Union[bool, int]) -> Tuple[bool, str]:
        res, comments = True, ''
        if value == 1:
            led.on()
        elif value == 0:
            led.off()
        else:
            res, comments = False, f'func _set_led value {value} is not known.'
        sleep(0.05)
        return res, comments

    def _pins_off(self) -> Tuple[Union[bool, str]]:
        if len(self._pins) == 0:
            return True, 'No pins to close().'
        else:
            error = []
            for pin in self._pins:
                try:
                    pin.close()
                except Exception as e:
                    error.append(str(e))
            self._pins = []
            return True, '' if len(error) == 0 else str(error)

    @development_mode(dev=dev_mode, with_return=(True, ''))
    def _set_microsteps_parameters(self, device_id: Union[int, str]) -> Tuple[bool, str] :
        try:
            axis = self.axes_stpmtr[device_id]
            self._set_led(self._ms1, axis.move_parameters['microsteps'][0][0])
            self._set_led(self._ms2, axis.move_parameters['microsteps'][0][1])
            self._set_led(self._ms3, axis.move_parameters['microsteps'][0][2])
            return True, ''
        except KeyError as e:
            error_logger(self, self._set_microsteps_parameters, e)
            return False, ''
