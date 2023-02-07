from pathlib import Path
import ctypes
import numpy as np
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

    def __init__(self, settings):
        for name, value in settings.items():
            if isinstance(value, list):
                value = np.asarray(value, dtype=np.uint)
                if len(value.shape) == 1:
                    arr = (ctypes.c_uint * value.shape[0])(*value)
                elif len(value.shape) == 2:
                    arr = ((ctypes.c_uint * value.shape[0]) * value.shape[1])()
                    # value = np.transpose(value)
                    # for x in range(value.shape[0]):
                    #     for y in range(value.shape[1]):
                    #         arr[x][y] = value[x][y]
                    # print(np.ctypeslib.as_array(arr))
                value = arr
            setattr(self, name, value)

dll_path = 'C:/dev/pyconlyse/DeviceServers/STRESING_IR/ESLSCDLL.dll'
dll = dll = ctypes.WinDLL(str(dll_path))

number_of_boards = ctypes.c_int8(0)
res = dll.DLLCCDDrvInit(ctypes.byref(number_of_boards))
number_of_boards = int(number_of_boards.value)
print(f'Number of boards: {number_of_boards}')
res = dll.DLLInitBoard()
print(f'Board Init {res}')

settings = {"useSoftwarePolling": 0,
            "nos": 100,
            "nob": 1,
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
global_settings = GlobalSettings(settings=settings)
global_settings_pointer = ctypes.byref(global_settings)
res = dll.DLLSetGlobalSettings(global_settings_pointer)
print(f'Global settings {res}')
res = dll.DLLInitMeasurement()
print(f'Init measurement {res}')


