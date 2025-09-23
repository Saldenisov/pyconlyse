import ctypes
import numpy as np
from pathlib import Path
import inspect
class GlobalSettings(ctypes.Structure):
    MAXPCIECARDS = 5

    _fields_ = [("useSoftwarePolling", ctypes.c_uint32),
                ("nos", ctypes.c_uint32),
                ("nob", ctypes.c_uint32),
                ("sti_mode", ctypes.c_uint32),
                ("bti_mode", ctypes.c_uint32),
                ("stime_in_microsec", ctypes.c_uint32),
                ("btime_in_microsec", ctypes.c_uint32),
                ("sdat_in_10ns", ctypes.c_uint32),
                ("bdat_in_10ns", ctypes.c_uint32),
                ("sslope", ctypes.c_uint32),
                ("bslope", ctypes.c_uint32),
                ("sec_in_10ns", ctypes.c_uint32),
                ("XCK delay in 10 ns steps", ctypes.c_uint32),
                ("trigger_mode_cc", ctypes.c_uint32),
                ("board_sel", ctypes.c_uint32),
                ("sensor_type", ctypes.c_uint32),
                ("camera_system", ctypes.c_uint32),
                ("camcnt", ctypes.c_uint32),
                ("pixel", ctypes.c_uint32),
                ("mshut", ctypes.c_uint32),
                ("led_off", ctypes.c_uint32),
                ("sensor_gain", ctypes.c_uint32),
                ("adc_gain", ctypes.c_uint32),
                ("Temp_level", ctypes.c_uint32),
                ("dac", ctypes.c_uint32),
                ("enable_gpx", ctypes.c_uint32),
                ("gpx_offset", ctypes.c_uint32),
                ("FFTLines", ctypes.c_uint32),
                ("Vfreq", ctypes.c_uint32),
                ("FFTMode", ctypes.c_uint32),
                ("lines_binning", ctypes.c_uint32),
                ("number_of_regions", ctypes.c_uint32),
                ("keep", ctypes.c_uint32),
                ("region_size", ctypes.c_uint32 * 8),
                ("dac_output", (ctypes.c_uint32 * MAXPCIECARDS) * 8),
                ("TORmodus", ctypes.c_uint32),
                ("ADC_Mode", ctypes.c_uint32),
                ("ADC_custom_pattern", ctypes.c_uint32),
                ("bec_in_10ns", ctypes.c_uint32),
                ("cont_pause_in_microseconds", ctypes.c_uint32),
                ("isIr", ctypes.c_uint32),
                ("IOCtrl_impact_start_pixel", ctypes.c_uint32),
                ("IOCtrl_output_width_in_5ns", ctypes.c_uint32 * 8),
                ("IOCtrl_output_delay_in_5ns", ctypes.c_uint32 * 8),
                ("IOCtrl_T0_period_in_10ns", ctypes.c_uint32),
                ("dma_buffer_size_in_scans", ctypes.c_uint32),
                ("tocnt", ctypes.c_uint32),
                ("ticnt", ctypes.c_uint32)
                ]

    _defaults_ = {"useSoftwarePolling": 0,
                "nos": 100,
                "nob": 1,
                "sti_mode": 4,
                "bti_mode": 4,
                "stime_in_microsec": 1000,
                "btime_in_microsec": 100000,
                "sdat_in_10ns": 0,
                "bdat_in_10ns": 0,
                "sslope": 0,
                "bslope": 1,
                "sec_in_10ns": 0,
                "XCK delay in 10 ns steps": 0,
                "trigger_mode_cc": 1,
                "board_sel": 1,
                "sensor_type": 1,
                "camera_system": 0,
                "camcnt": 1,
                "pixel": 1088,
                "mshut": 0,
                "led_off": 0,
                "sensor_gain": 0,
                "adc_gain": 1,
                "Temp_level": 1,
                "dac": 0,
                "enable_gpx": 0,
                "gpx_offset": 1000,
                "FFTLines": 128,
                "Vfreq": 7,
                "FFTMode": 0,
                "lines_binning": 1,
                "number_of_regions": 2,
                "keep": 0,
                "region_size": [32, 32, 16, 32, 68, 0, 0, 0],
                "dac_output":
                 [[51500, 51500, 51520, 51580, 51560, 51590, 51625, 51745],
                  [55000, 54530, 54530, 54530, 54530, 54530, 54530, 54530],
                  [0, 0, 0, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 0, 0, 0]],
                "TORmodus": 0,
                "ADC_Mode": 0,
                "ADC_custom_pattern": 100,
                "bec_in_10ns": 0,
                "cont_pause_in_microseconds": 1,
                "isIr": 0,
                "IOCtrl_impact_start_pixel": 1078,
                "IOCtrl_output_width_in_5ns": [50, 50, 50, 50, 50, 50, 50, 0],
                "IOCtrl_output_delay_in_5ns": [0, 100, 200, 300, 400, 500, 600, 0],
                "IOCtrl_T0_period_in_10ns": 1000,
                "dma_buffer_size_in_scans": 1000,
                "tocnt": 0,
                "ticnt": 0
                }
nos = 100
nob = 1
pixels = 576
parameters = {"Measurement_Settings":
{"useSoftwarePolling": 0,
            "nos": nos,
            "nob": nob,
            "sti_mode": 0,
            "bti_mode": 0,
            "stime_in_microsec": 1000,
            "btime_in_microsec": 100000,
            "sdat_in_10ns": 0,
            "bdat_in_10ns": 0,
            "sslope": 0,
            "bslope": 0,
            "sec_in_10ns": 0,
            "XCK delay in 10 ns steps": 0,
            "trigger_mode_cc": 1,
            "board_sel": 1,
            "sensor_type": 0,
            "camera_system": 0,
            "camcnt": 2,
            "pixel": 576,
            "mshut": 0,
            "led_off": 0,
            "sensor_gain": 0,
            "adc_gain": 1,
            "Temp_level": 1,
            "dac": 0,
            "enable_gpx": 0,
            "gpx_offset": 1000,
            "FFTLines": 128,
            "Vfreq": 7,
            "FFTMode": 0,
            "lines_binning": 1,
            "number_of_regions": 2,
            "keep": 0,
            "region_size": [32, 32, 16, 32, 68, 0, 0, 0],
            "dac_output":
                [[51500, 51500, 51520, 51580, 51560, 51590, 51625, 51745],
                 [55000, 54530, 54530, 54530, 54530, 54530, 54530, 54530],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0]],
            "TORmodus": 0,
            "ADC_Mode": 0,
            "ADC_custom_pattern": 100,
            "bec_in_10ns": 0,
            "cont_pause_in_microseconds": 1,
            "isIr": 0,
            "IOCtrl_impact_start_pixel": 1078,
            "IOCtrl_output_width_in_5ns": [50, 50, 50, 50, 50, 50, 50, 0],
            "IOCtrl_output_delay_in_5ns": [0, 100, 200, 300, 400, 500, 600, 0],
            "IOCtrl_T0_period_in_10ns": 1000,
            "dma_buffer_size_in_scans": 1000,
            "tocnt": 0,
            "ticnt": 0
 }
              }

def DLLCCDDrvInit(dll):
    """
    int32_t DLLCCDDrvInit(uint8_t * number_of_boards);
    """
    number_of_boards = ctypes.c_int8(0)
    res = dll.DLLCCDDrvInit(ctypes.byref(number_of_boards))
    number_of_boards = int(number_of_boards.value)
    return True if number_of_boards > 0 else False

def DLLInitBoard(dll):
    """
        int32_t DLLInitBoard(void );
    """
    res = dll.DLLInitBoard()
    return True if res == 0 else False


def DLLSetGlobalSettings(dll, parameters):
    settings = parameters['Measurement_Settings']
    global_settings = GlobalSettings(settings=settings)
    global_settings_pointer = ctypes.byref(global_settings)
    res = dll.DLLSetGlobalSettings(global_settings_pointer)
    return True if res == 0 else False

def _DLLInitMeasurement(dll):
    """
    int32_t DLLInitMeasurement(void );
    """
    res = dll.DLLInitMeasurement()
    return True if res == 0 else False


def DLLConvertErrorCodeToMsg(dll, error_code: int) -> str:
    """
    CStr DLLConvertErrorCodeToMsg(int32_t status);
    """
    error_code = ctypes.c_int(error_code)
    dll.DLLConvertErrorCodeToMsg.restype = ctypes.c_char_p
    res = dll.DLLConvertErrorCodeToMsg(error_code)
    return res

def DLLInitMeasurement(dll):
    """
    int32_t DLLInitMeasurement(void );
    """
    res = dll.DLLInitMeasurement()
    return True if res == 0 else False

def Shutdown(dll):
    dll.DLLStopFFLoop()
    dll.DLLCCDDrvExit(ctypes.c_uint32(1))
    return True

def DLLisMeasureOn(dll, drv: int):
    """
    int32_t DLLisMeasureOn(uint32_t drv, uint8_t *measureOn);
    """
    drv = ctypes.c_uint32(drv)
    measureOn = ctypes.c_uint8(1)
    res = dll.DLLisMeasureOn(drv, ctypes.byref(measureOn))
    smeasure_on = not bool(measureOn.value)
    return smeasure_on

def DLLRetrunFrame(dll, drv:int, curr_nos: int, curr_nob: int, curr_cam: int, length: int):
    """
    void  DLLReturnFrame(uint32_t drv, uint32_t curr_nos, uint32_t curr_nob, uint16_t curr_cam,
    uint16_t *dioden, uint32_t length);
    """
    drv = ctypes.c_uint32(drv)
    curr_nos = ctypes.c_uint32(curr_nos)
    curr_nob = ctypes.c_uint32(curr_nob)
    curr_cam = ctypes.c_uint32(curr_cam)
    array = (ctypes.c_uint16 * length)()
    array_p = ctypes.cast(array, ctypes.POINTER(ctypes.c_uint16))
    length = ctypes.c_uint32(length)
    dll.DLLReturnFrame(drv, curr_nos, curr_nob, curr_cam, array_p, length)
    print(np.array(array))

dll_path = Path('C:/dev/pyconlyse/DeviceServers/STRESING_IR/ESLSCDLL.dll')

dll = ctypes.WinDLL(str(dll_path))

res = DLLCCDDrvInit(dll)

res = DLLInitBoard(dll)

res = DLLSetGlobalSettings(dll, parameters)

res = DLLInitMeasurement(dll)

# dll.DLLReadFFLoop()

from time import sleep
sleep(1)
while DLLisMeasureOn(dll, 0):
    print('Measuring')
    sleep(1)

print('Measrument finished')
DLLRetrunFrame(dll, drv=1, curr_nos=60, curr_nob=0, curr_cam=0, length=pixels)

res = Shutdown(dll)









