from devices.devices import Service
import logging
import ctypes
from errors.myexceptions import CannotmoveDL
module_logger = logging.getLogger(__name__)


# is not working anymore, no support is available
class StpMtrCtrl_2axis(Service):
    """
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
        return {'connect': [[], None],
                'disconnect': [[], None],
                'move': [[('axis',  int), ('position', float)], None]}

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


class StpMtrCtrl_emulate(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def moveto(self, pos: float):
        from time import sleep
        sleep(pos/1000. * 5)
        self.pos = pos

    def getpos(self) -> float:
        return self.pos


class StpMtrCtrl_emulate2(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def moveto(self, pos: float):
        from time import sleep
        sleep(pos/1000. * 5)
        self.pos = pos

    def getpos(self) -> float:
        return self.pos
