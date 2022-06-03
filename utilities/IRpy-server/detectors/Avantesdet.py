import ctypes as ct
import numpy as np

from errors import myexceptions as myexc


class Avantesdet:
    def __init__(self, dllpath, parameters={}, dev=True):
        self.__dllpath = dllpath
        self.connected = False
        self.datacleanning = False
        self.__parameters = parameters
        self.dev = dev

    def connect(self):
        return self._init(self.__parameters) if not self.dev else True

    def disconnect(self):
        return self._stop() if not self.dev else True

    def read(self, number_of_scans):
        if not self.dev:
            rawdata = self._readraw(number_of_scans)
        else:
            rawdataI = np.zeros(shape=(10, 600))
            rawdataII = np.zeros(shape=(10, 600))
            rawdata = np.array[rawdataI, rawdataII]

        return rawdata if not self.datacleanning else self._clean(rawdata)

    def _clean(self, rawdata):
        if not self.dev:
            pass
        else:
            datacleaned = rawdata
        return datacleaned

    def _init(self, parameters):
        try:
            self.__AvantesDet = ct.WinDLL(self.__dllpath)
            self.connected = True
            print("connected")
        except myexc.MyException as e:
            print(e)
            raise
        finally:
            return self.connected

    def _readraw(self, number_of_scans):
        rawdata = np.array([np.zeros(shape=(10, 600)), np.zeros(shape=(10, 600))])
        try:
            pass
        except myexc.MyException as e:
            print(e)
            raise
        finally:
            return rawdata

    def _stop(self) -> bool:
        stopped = False
        try:
            stopped = True
            print("Disconnected")
        except myexc.MyException as e:
            print(e)
            raise
        finally:
            return stopped

    def __AVS_init(self, a_port) -> int:
        a_port_cv = ct.c_int32(a_port)
        out = 0
        try:
            out = self.__AvantesDet.AVS_Init(a_port_cv)
            if out == 'ERR_DEVICE_NOT_FOUND':
                raise myexc.DLLerror("AVS_Init")
        except:
            raise myexc.DLLerror("AVS_Init")
        finally:
            return out

    def __AVS_Done(self) -> bool:
        try:
            self.__AvantesDet.AVS_Done()
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("AVS_Done")
        finally:
            return SUCCESS

    def __AVS_GetList(self, a_ListSize, a_pRequiredSize, a_pList) -> bool:
        a_port_cv = ct.c_int32(a_port)
        out = 0
        try:
            self.__AvantesDet.AVS_GetList(a_port_cv)

        except:
            raise myexc.DLLerror("AVS_Init")
        finally:
            return out

