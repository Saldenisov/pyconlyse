import ctypes as ct
import numpy as np
from time import sleep
from utilities.errors import myexceptions as myexc
from devices import OpticalDetector


class IRdet(OpticalDetector):
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
            self.__IRdet = ct.WinDLL(self.__dllpath)
            self.__DLLCCDDrvInit(1)
            self.__DLLRsTOREG(1)
            self.__DLLSetTORReg(1, 5)
            self.__DLLWriteLongS0(1, 2147483648 + 1, 32)
            self.__DLLInitBoard(1, 0, 1, 600, 3, 1, 378, 2, 3)
            self.__DLLSetISPDA(1, 1)
            self.__DLLVOff(1)
            self.__DLLSetupVCLK(1, 0, 12)
            self.__DLLWriteLongS0(1, 100, 52)
            self.__DLLRSFifo(1)
            self.__DLLSetExtTrig(1)
            self.__DLLStartRingReadThread(1, 1000, 15, 0)
            self.__DLLStartFetchRingBuf()

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
            status = 1
            while status == 1:
                print("waiting low")
                status = self.__DLLRingBlockTrig(1)
            while status != 1:
                print("waiting high")
                status = self.__DLLRingBlockTrig(1)
            data = self.__DLLReadRingBlock(600, 0, number_of_scans * 9)
        except myexc.MyException as e:
            print(e)
            raise
        finally:
            return rawdata

    def _stop(self) -> bool:
        stopped = False
        try:
            self.__DLLStopRingReadThread()

            for i in range(0, 100):
                if self.__DLLRingThreadIsOFF() != 0:
                    break
                else:
                    sleep(1)
            self.__DLLStopFFTimer(1)
            self.__DLLSetIntTrig(1)
            self.__DLLCCDDrvExit(1)
            stopped = True
            print("Disconnected")
        except myexc.MyException as e:
            print(e)
            raise
        finally:
            return stopped

    def __DLLCCDDrvInit(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLCCDDrvInit(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLCCDDrvInit")
        finally:
            return SUCCESS

    def __DLLRsTOREG(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLRsTOREG(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLRsTOREG")
        finally:
            return SUCCESS

    def __DLLSetTORReg(self, drv, fkt) -> bool:
        drv_ct = ct.c_int32(drv)
        fkt_ct = ct.c_int8(fkt)
        try:
            self.__IRdet.DLLSetTORReg(drv_ct, fkt_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLSetTORReg")
        finally:
            return SUCCESS

    def __DLLInitBoard(self, drv, sym, burst, pixel, waits,
                       flag816, pportadress, pclk, adrdelay) -> bool:
        drv_ct = ct.c_int32(drv)
        sym_ct = ct.c_int8(sym)
        burst_ct = ct.c_int8(burst)
        pixel_ct = ct.c_int32(pixel)
        waits_ct = ct.c_int32(waits)
        flag816_ct = ct.c_int32(flag816)
        pportadress_ct = ct.c_int32(pportadress)
        pclk_ct = ct.c_int32(pclk)
        adrdelay_ct = ct.c_int32(adrdelay)
        try:
            self.__IRdet.DLLInitBoard(drv_ct, sym_ct, burst_ct,
                                      pixel_ct, waits_ct, flag816_ct, pportadress_ct,
                                      pclk_ct, adrdelay_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLInitBoard")
        finally:
            return SUCCESS

    def __DLLWriteLongS0(self, drv, val, offset) -> bool:
        drv_ct = ct.c_int32(drv)
        val_ct = ct.c_int32(val)
        offset_ct = ct.c_int32(offset)
        try:
            self.__IRdet.DLLWriteLongS0(drv_ct, val_ct, offset_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLWriteLongS0")
        finally:
            return SUCCESS

    def __DLLSetISPDA(self, drv, set) -> bool:
        drv_ct = ct.c_int32(drv)
        set_ct = ct.c_int8(set)
        try:
            self.__IRdet.DLLSetISPDA(drv_ct, set_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLSetISPDA")
        finally:
            return SUCCESS

    def __DLLVOff(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLVOff(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLVOff")
        finally:
            return SUCCESS

    def __DLLSetupVCLK(self, drv, lines, vfreq) -> bool:
        drv_ct = ct.c_int32(drv)
        lines_ct = ct.c_int32(lines)
        vfreq_ct = ct.c_int8(vfreq)
        try:
            self.__IRdet.DLLSetupVCLK(drv_ct, lines_ct, vfreq_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLSetupVCLK")
        finally:
            return SUCCESS

    def __DLLRSFifo(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLRSFifo(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLRSFifo")
        finally:
            return SUCCESS

    def __DLLSetExtTrig(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLSetExtTrig(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLSetExtTrig")
        finally:
            return SUCCESS

    def __DLLStartRingReadThread(self, drv, ringdepth, threadp, releasems) -> bool:
        drv_ct = ct.c_int32(drv)
        ringdepth_ct = ct.c_int32(ringdepth)
        threadp_ct = ct.c_int32(threadp)
        releasems_ct = ct.c_int16(releasems)
        try:
            self.__IRdet.DLLStartRingReadThread(drv_ct, ringdepth_ct,
                                                threadp_ct, releasems_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLStartRingReadThread")
        finally:
            return SUCCESS

    def __DLLStartFetchRingBuf(self) -> bool:
        try:
            self.__IRdet.DLLStartFetchRingBuf()
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLStartFetchRingBuf")
        finally:
            return SUCCESS

    def __DLLStopRingReadThread(self) -> bool:
        try:
            self.__IRdet.DLLStopRingReadThread()
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLStopRingReadThread")
        finally:
            return SUCCESS

    def __DLLRingThreadIsOFF(self) -> int:
        try:
            out = self.__IRdet.DLLRingThreadIsOFF()
        except:
            raise myexc.DLLerror("DLLRingThreadIsOFF")
        finally:
            return out

    def __DLLStopFFTimer(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLStopFFTimer(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLStopFFTimer")
        finally:
            return SUCCESS

    def __DLLSetIntTrig(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLSetIntTrig(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLSetIntTrig")
        finally:
            return SUCCESS

    def __DLLCCDDrvExit(self, drv) -> bool:
        drv_ct = ct.c_int32(drv)
        try:
            self.__IRdet.DLLCCDDrvExit(drv_ct)
            SUCCESS = True
        except:
            SUCCESS = False
            raise myexc.DLLerror("DLLCCDDrvExit")
        finally:
            return SUCCESS

    def __DLLRingBlockTrig(self, channel) -> bool:
        channel_ct = ct.c_int8(channel)
        try:
            out = self.__IRdet.DLLRingBlockTrig(channel_ct)
        except:
            out = 0
            raise myexc.DLLerror("DLLRingBlockTrig")
        finally:
            return True if out != 0 else False

    def __DLLReadRingBlock(self, pixel: int, start: int, stop: int):
        num_lines = stop - start + 1
        num_columns = pixel
        ar = np.zeros(num_lines * num_columns, dtype=np.int32)
        ptr = ar.ctypes.data_as(ct.POINTER(ct.c_int32))
        start_ct = ct.c_int32(start)
        stop_ct = ct.c_int32(stop)
        try:
            self.__IRdet.DLLReadRingBlock(ptr, start_ct, stop_ct)
        except:
            raise myexc.DLLerror("DLLReadRingBlock")
        finally:
            return ar

class Avantesdet(OpticalDetector):
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