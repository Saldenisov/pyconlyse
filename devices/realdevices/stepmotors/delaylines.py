from typing import Dict, Union, Any, List, Tuple, Iterable

from .stpmtr_controller import StpMtrController, StpmtrError
import logging
import ctypes
from time import sleep
from deprecated import deprecated
module_logger = logging.getLogger(__name__)

control = 'control'
observe = 'observe'
info = 'info'

@deprecated(version='1.0', reason="Class is not supported, the hardware controller is out of order")
class StpMtrCtrl_2axis(StpMtrController):
    """
    It is not working anymore, no support is available
    Defines class of Delay line
    """

    def __init__(self, settings: dict):
        """
        """
        self.logger = logging.getLogger(__name__)
        self.connected = False
        self.set_parameters(settings)

    def available_public_functions(self):
        # TODO: logic to be updated!!!
        return {}

    def set_parameters(self, Config):
        if not self.connected:
            self.__mconfig = Config['stepmotors']
            self.__LS4dll_path = self.__mconfig['DLL_path']
            self.__port = self.__mconfig['port']
            self.__showport = self.__mconfig['showport']
            self.__interface = self.__mconfig['interface']
            self.__mode = Config['General']['devmode']
        else:
            self.logger.info('Disconnect stepmotors before changing parameters')

    def model_is_changed(self):
        if self.connected:
            self.logger.info('In order to update setting of stepmotors, please disconnect and connect again.')

    def connect(self):
        try:
            self.__LS4 = ctypes.WinDLL(self.__LS4dll_path)
            command = 'config_ligne_a_retard.ls'
            self.__config = self._loadconfig(command)
            self.__connect = self._connectsimple()
            self.__param = self._setcontrolpars()

            if self.__config and self.__connect and self.__param:
                self.logger.info('Initialization of stepmotors is accomplished')
                self.connected = True
                if self.__mode:
                    self._set_settings()
        except OSError as e:
            self.logger.error(e)
            raise
        finally:
            return self.connected

    def disconnect(self):
        self.returntozero()
        return self._disconnect()

    def moveto(self, pos, axis, wait=True, mode='abs'):
        return self._movesingleaxis(axis=axis, pos=pos, wait=wait, mode=mode)

    def returntozero(self):
        self._movesingleaxis(axis=1, pos=0)
        self._movesingleaxis(axis=2, pos=0)

    def _loadconfig(self, command: str) -> bool:
        command = ctypes.c_char_p(command.encode('utf-8'))
        try:
            loadconfres = self.__LS4.LS_LoadConfig(command)
        except:
            loadconfres = 1
        finally:
            return True if loadconfres == 0 else False

    def _setlanguage(self, lang='ENG') -> bool:
        lang = ctypes.c_char_p(lang.encode('utf-8'))
        try:
            language = self.__LS4.LS_SetLanguage(lang)
        except:
            language = 1
        finally:
            return True if language == 0 else False

    def _setcontrolpars(self) -> bool:
        """
        Use when __mconfig file is already loaded
        """
        try:
            setcontrolparsres = self.__LS4.LS_SetControlPars()
        except:
            setcontrolparsres = 1
        finally:
            return True if setcontrolparsres == 0 else False

    def _connectsimple(self) -> bool:
        interface_in = ctypes.c_int(self.__interface)
        port_in = ctypes.c_char_p(self.__port.encode('utf_8'))
        if self.__interface == 1:
            ABR = 9600
        elif self.__interface == 3:
            ABR = 340
        ABR_in = ctypes.c_int(ABR)
        if self.__showport:
            showport_in = 1
        else:
            showport_in = 0
        showprot_in = ctypes.c_int(showport_in)

        try:
            init = self.__LS4.LS_ConnectSimple(interface_in, port_in, ABR_in, showprot_in)
        except:
            init = 1
        finally:
            return True if init == 0 else False

    def _setvel(self, X: float, Y: float, Z=10.0, A=10.0) -> bool:
        """
        set speed velocity
        """
        Xin = ctypes.c_double(X)
        Yin = ctypes.c_double(Y)
        Zin = ctypes.c_double(Z)
        Ain = ctypes.c_double(A)
        try:
            executed = self.__LS4.SetVel(Xin, Yin, Zin, Ain)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setvelsingleaxis(self, axis: int, vel: float) -> bool:
        """
        set speed velocity
        """
        axis_in = ctypes.c_int(axis)
        vel_in = ctypes.c_double(vel)

        try:
            executed = self.__LS4.SetVelSingleAxis(axis_in, vel_in)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setaccel(self, X=0.05, Y=0.05, Z=0.05, A=0.05) -> bool:
        Xin = ctypes.c_double(X)
        Yin = ctypes.c_double(Y)
        Zin = ctypes.c_double(Z)
        Ain = ctypes.c_double(A)
        try:
            executed = self.__LS4.SetAccel(Xin, Yin, Zin, Ain)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setpitch(self, X=0.05, Y=0.05, Z=0.05, A=0.05) -> bool:
        Xin = ctypes.c_double(X)
        Yin = ctypes.c_double(Y)
        Zin = ctypes.c_double(Z)
        Ain = ctypes.c_double(A)
        try:
            executed = self.__LS4.SetPitch(Xin, Yin, Zin, Ain)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setmotorcurrent(self, X=0.05, Y=0.05, Z=0.05, A=0.05) -> bool:
        Xin = ctypes.c_double(X)
        Yin = ctypes.c_double(Y)
        Zin = ctypes.c_double(Z)
        Ain = ctypes.c_double(A)
        try:
            executed = self.__LS4.SetMotorCurrent(Xin, Yin, Zin, Ain)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setdimensions(self, X=1, Y=1, Z=1, A=1) -> bool:
        """
        0-steps, 1-um, 2-mm, 3-degrees, 4-revolutions
        """
        Xin = ctypes.c_int(X)
        Yin = ctypes.c_int(Y)
        Zin = ctypes.c_int(Z)
        Ain = ctypes.c_int(A)
        try:
            executed = self.__LS4.SetDimensions(Xin, Yin, Zin, Ain)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _setlimit(self, axis: int, minr: float, maxr: float) -> bool:
        axis_in = ctypes.c_int(axis)
        minr_in = ctypes.c_double(minr)
        maxr_in = ctypes.c_double(maxr)

        try:
            executed = self.__LS4.SetLimit(axis_in, minr_in, maxr_in)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _getpossingleaxis(self, axis: int) -> float:
        axis_in = ctypes.c_int(axis)
        pos = ctypes.c_double
        ppos = ctypes.pointer(pos)
        try:
            executed = self.__LS4.GetPosSingleAxis(axis_in, ctypes.c_double(0))
            pos = ppos.contents.value
        except:
            pos = 0
        finally:
            return pos

    def _disconnect(self) -> bool:
        try:
            executed = self.__LS4.LS_Disconnect()
            self.connected = False
            self.logger.info('stepmotors is disconnected')
        except:
            executed = 1
            self.logger.error('Cannot disconnect stepmotors')
        finally:
            return True if executed == 0 else False

    def _movesingleaxis(self, axis: int, pos: float, wait=True, mode='abs') -> bool:
        axis_in = ctypes.c_int(axis)
        pos_in = ctypes.c_double(pos)
        if wait:
            wait_in = ctypes.c_int(1)
        else:
            wait_in = ctypes.c_int(0)

        try:
            if mode == 'abs':
                executed = self.__LS4.LS_MoveAbsSingleAxis(axis_in, pos_in, wait_in)
        except:
            executed = 1
        finally:
            return True if executed == 0 else False

    def _set_settings(self):
        if self.connected:
            X, Y, Z, A = self.__mconfig['General']['Velocities'].values()
            self._setvel(X, Y, Z, A)

            X, Y, Z, A = self.__mconfig['General']['Accelerations'].values()
            self._setaccel(X, Y, Z, A)

            X, Y, Z, A = self.__mconfig['General']['Pitches'].values()
            self._setpitch(X, Y, Z, A)

            X, Y, Z, A = self.__mconfig['General']['Motor_Currents'].values()
            self._setmotorcurrent(X, Y, Z, A)

            X, Y, Z, A = self.__mconfig['General']['Dimensions'].values()
            self._setdimensions(X, Y, Z, A)

            # Limits for long delay
            lmin, lmax, _ = self.__mconfig['Long']['Ranges'].values()
            axisL = self.__mconfig['Long']['axis']
            self._setlimit(axisL, lmin, lmax)
            # Limits for short delay
            axisS = self.__mconfig['Short']['axis']
            lmin, lmax, _ = self.__mconfig['Short']['Ranges'].values()
            self._setlimit(axisS, lmin, lmax)

            vel = self.__mconfig['Long']['Single_Axis_vel']
            self._setvelsingleaxis(axisL, vel)

            vel = self.__mconfig['Short']['Single_Axis_vel']
            self._setvelsingleaxis(axisS, vel)

            self._setlanguage(lang='ENG')
        else:
            self.logger.info('Connect stepmotors before applying settings')


class StpMtrCtrl_emulate(StpMtrController):
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

    def move_axis_to(self, axis: int, pos: float, how='absolute')-> Tuple[Union[bool, Dict[str, Union[int, bool]]], str]:
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
                    StpMtrController._write_to_file(str(self._pos), self._file_pos)
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
            if self._axes_status[axis] == 2:
                self._axes_status[axis] = 1
                comments = 'stopped by user'
            elif self._axes_status[axis] == 1:
                comments = 'was already stopped'

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
        desc = {'GUI_title': """StpMtrCtrl_emulate service, 4 axes""",
                'axes_names': ['0/90 mirror', 'iris', 'filter wheel 1', 'filter wheel 2'],
                'axes_values': [0, 3],
                'ranges': [((0.0, 100.0), (0, 91)),
                           ((-100.0, 100.0), (0, 50)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360))],
                'info': "StpMtrCtrl_emulate controller, it emulates stepmotor controller with 4 axes"}
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

    def _is_within_limits(self, axis:int, pos) -> bool:
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
            return False, f'axis {axis} is out of range {list(range(self._axis_number))}'\

    def _check_axis_active(self, axis: int) -> bool:
        comments = ''
        if self._axes_status[axis] > 0:
            return True, comments
        else:
            return False, f'axis {axis} is not active, activate it first'

    def _set_controller_activity(self):
        self.device_status.active = True


class StpMtrCtrl_OWIS(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._PS90: ctypes.WinDLL = None


    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        pass

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
        self._DLpath = self.get_general_settings()['DLL_path']
        self._PS90 = ctypes.WinDLL(self._DLpath)
        self._interface = int(self.get_general_settings()['interface'])
        self._baudrate = int(self.get_general_settings()['baudrate'])
        self._port = int(self.get_general_settings()['port'])

    #TODO add documention to all functionsof PS90, what parameters
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

    def _disconnect(self, control_unit: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        res = self._PS90.PS90_Disconnect(control_unit)
        success = True if res else False
        return success, self._error(res, 0), 0

    def _get_axis_state(self, control_unit: int, axis: int) -> Tuple[Union[bool, str, int]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error(control_unit)
        success = True if error == 0 else False
        return success, self._error(res, 1), res

    def _get_position_ex(self, control_unit: int, axis: int) -> Tuple[Union[bool, str, float]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GetPositionEx(control_unit, axis)
        error = self.__get_read_error(control_unit)
        success = True if error == 0 else False
        return success, self._error(res, 1), res

    def _go_target(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_GoTarget(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    def __get_read_error(self, control_unit: int) -> int:
        control_unit = ctypes.c_int(control_unit)
        return self._PS90.PS90_GetReadError(control_unit)

    def _free_switch(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_FreeSwitch(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _motor_init(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorInit(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _motor_on(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorOn(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _motor_off(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        res = self._PS90.PS90_MotorOff(control_unit, axis)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _set_pos_mode(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        return self._PS90.PS90_SetPosMode(control_unit, axis, value)

    def _set_target_mode(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetTargetMode(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _set_pos_velocity(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetPosVel(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _set_target(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_int(value)
        res = self._PS90.PS90_SetTarget(control_unit, axis, value)
        success = True if res else False
        return success, self._error(res, 1), 0

    def _set_target_ex(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis)
        value = ctypes.c_double(value)
        res = self._PS90.PS90_SetTargetEx(control_unit, axis, value)
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

