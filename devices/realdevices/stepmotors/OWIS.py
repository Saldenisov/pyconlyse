"""
This controller is dedicated to control OWIS PS90 control unit
"""


from typing import List, Tuple, Union, Iterable, Dict, Any

import logging
import ctypes
from time import sleep
from utilities.tools.decorators import development_mode
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = False

class StpMtrCtrl_OWIS(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._PS90: ctypes.WinDLL = None

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        res, comments = self._setup()
        if res:
            res, comments = self._connect(1, self._interface, self._port, self._baudrate)
            if res:
                self.device_status.active = flag
                return True, f'{self.id}:{self.name} active state is {flag}'
            else:
                return True, f'{self.id}:{self.name} active state is {flag}'
        else:
            self.device_status.active = False
            return True, f'{self.id}:{self.name} active state is {False}; {comments}'

    def activate_axis(self, axis: int, flag: int) -> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
        pass

    def description(self) -> Dict[str, Any]:
        # TODO: change ranges and
        desc = {'GUI_title': """StpMtrCtrl_OWIS service, 3 axes""",
                'axes_names': ['DL_VD2', 'DL_VD_samples', 'DL_VD_pp'],
                'axes_values': [0, 3],
                'ranges': [((-10.0, 100.0), (0, 91)),
                           ((-100.0, 100.0), (0, 50)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360))],
                'info': "StpMtrCtrl_OWIS controller, it controls OWIS controller with 3 axes"}
        return desc

    def power(self, flag: bool):
        pass

    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def move_axis_to(self, axis: int, pos: Union[float, int], how='absolute') -> Tuple[Union[bool,
                                                                                             Dict[str, Union[
                                                                                                 int, float, str]]], str]:
        pass

    def stop_axis(self, axis: int) -> Tuple[Union[bool, Dict[str, Union[int, float, str]]], str]:
        pass

    def get_pos(self, axis: int) -> Tuple[Union[Dict[str, Union[int, float, str]], str]]:
        pass

    def get_controller_state(self) -> Iterable[Union[Dict[str, Union[int, str]], str]]:
        pass

    def _get_axes_status(self) -> List[int]:
        pass

    def _get_number_axes(self) -> int:
        pass

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        pass

    def _get_pos(self) -> List[Union[int, float]]:
        pass

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        pass

    def _set_controller_activity(self):
        pass

    def _setup(self):
        try:
            list_param = ['DLL_path', 'interface', 'baudrate', 'port']
            settings = self.get_general_settings()
            self._DLpath = settings['DLL_path']
            self._PS90 = ctypes.WinDLL(self._DLpath)
            self._interface = int(settings['interface'])
            self._baudrate = int(settings['baudrate'])
            self._port = int(settings['port'])
            self._axes_speeds: List[float] = self._get_list_db("Parameters", 'speeds', float)
            self._axes_gear_ratios: List[int] = self._get_list_db("Parameters", 'gear_ratios', int)
            return True, ''
        except:
            return False, "_setup did not work"

    #TODO add documention to all functionsof PS90, what parameters
    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _connect(self, control_unit: int, interface: int, port: int, baudrate: int,
                 par3=0, par4=0, par5=0, par6=0) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        interface = ctypes.c_int(interface)
        port = ctypes.c_int(port)
        baudrate = ctypes.c_int(baudrate)
        par3 = ctypes.c_int(par3)
        par4 = ctypes.c_int(par4)
        par5 = ctypes.c_int(par5)
        par6 = ctypes.c_int(par6)
        res = self._PS90.PS90_Connect(control_unit, interface, port, baudrate, par3, par4, par5, par6)
        success = True if res else False
        return success, self._error(res, 0), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _disconnect(self, control_unit: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        res = self._PS90.PS90_Disconnect(control_unit)
        success = True if res else False
        return success, self._error(res, 0), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _get_axis_state(self, control_unit: int, axis: int) -> Tuple[Union[bool, str, int]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error(control_unit)
        success = True if error == 0 else False
        return success, self._error(res, 1), res

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _get_position_ex(self, control_unit: int, axis: int) -> Tuple[Union[bool, str, float]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GetPositionEx(control_unit, axis)
        error = self.__get_read_error(control_unit)
        success = True if error == 0 else False
        return success, self._error(res, 1), res

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _go_target(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GoTarget(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def __get_read_error(self, control_unit: int) -> int:
        control_unit = ctypes.c_int(control_unit)
        return self._PS90.PS90_GetReadError(control_unit)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _free_switch(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_FreeSwitch(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_init(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorInit(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_on(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorOn(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_off(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorOff(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_mode(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        return self._PS90.PS90_SetPosMode(control_unit, axis, value)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target_mode(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetTargetMode(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_velocity(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetPosVel(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetTarget(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target_ex(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_double(value)
        res = self._PS90.PS90_SetTargetEx(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_Fex(self, control_unit: int, axis: int, speed: float) -> Tuple[Union[bool, str]]:
        """
        Sets the speed of the axis
        :param control_unit: usually 1 if one controller is available
        :param axis: could be 1-3
        :param speed: in mm/s
        :return:
        """
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        speed = ctypes.c_double(speed)
        res = self._PS90.PS90_SetPosFEx(control_unit, axis, speed)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _error(self, code: int, type: int) -> str:
        """
        :param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors_connections = {0: 'no error', -1: 'function error', -2: 'invalid serial port (port is not found)',
                  -3: 'access denied  (port is busy)', -4: 'access denied  (port is busy)',
                  -5: 'no response from control unit', -7: 'control unit with the specified serial number is not found',
                  -8: 'no connection to modbus/tcp', -9: 'no connection to tcp/ip socket'}
        errors_functions = {0: 'no error', -1: 'function error', -2: 'communication error', -3: 'syntax error',
                            -4: 'axis is in wrong state', -9: 'OWISid chip is not found',
                            -10: 'OWISid parameter is empty (not defined)'}
        if code > 0 or (code not in errors_connections or code not in errors_functions):
            return "Wrong code number"
        elif type not in [0, 1]:
            return "Wrong type of error"
        else:
            return errors_connections[code] if type == 0 else errors_functions[code]