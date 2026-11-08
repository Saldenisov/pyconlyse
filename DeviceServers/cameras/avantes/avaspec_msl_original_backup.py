"""
Wrapper around the ``avaspec.dll`` SDK from Avantes.

The wrapper was written using v9.7.0.0 of the SDK.
"""
from __future__ import annotations

from sys import modules as _refactor_modules

from DeviceServers.cameras.avantes.avaspec_msl_original_backup_methods_err_check import _bind_avaspec_msl_original_backup_methods_err_check

from DeviceServers.cameras.avantes.avaspec_msl_original_backup_methods_measure_callback import _bind_avaspec_msl_original_backup_methods_measure_callback

from ctypes import POINTER
from ctypes import Structure
from ctypes import c_bool
from ctypes import c_char
from ctypes import c_char_p
from ctypes import c_double
from ctypes import c_float
from ctypes import c_int16
from ctypes import c_int32
from ctypes import c_ubyte
from ctypes import c_uint16
from ctypes import c_uint32
from ctypes import c_ulong
from ctypes import c_void_p
from ctypes import create_string_buffer
from ctypes import sizeof
from enum import IntEnum

import numpy as np
from msl.loadlib import LoadLibrary

from msl.equipment.connection_sdk import ConnectionSDK
from msl.equipment.constants import IS_WINDOWS
from msl.equipment.exceptions import AvantesError
from msl.equipment.resources import register

WM_MEAS_READY = 0x8001
SETTINGS_RESERVED_LEN = 9720
INVALID_AVS_HANDLE_VALUE = 1000
USER_ID_LEN = 64
AVS_SERIAL_LEN = 10
MAX_TEMP_SENSORS = 3
ROOT_NAME_LEN = 6
VERSION_LEN = 16
AVASPEC_ERROR_MSG_LEN = 8
AVASPEC_MIN_MSG_LEN = 6
OEM_DATA_LEN = 4096
NR_WAVELEN_POL_COEF = 5
NR_NONLIN_POL_COEF = 8
MAX_VIDEO_CHANNELS = 2
NR_DEFECTIVE_PIXELS = 30
MAX_NR_PIXELS = 4096
NR_TEMP_POL_COEF = 5
NR_DAC_POL_COEF = 2
SAT_PEAK_INVERSION = 2
SW_TRIGGER_MODE = 0
HW_TRIGGER_MODE = 1
SS_TRIGGER_MODE = 2
EXTERNAL_TRIGGER = 0
SYNC_TRIGGER = 1
EDGE_TRIGGER_SOURCE = 0
LEVEL_TRIGGER_SOURCE = 1
ILX_FIRST_USED_DARK_PIXEL = 2
ILX_USED_DARK_PIXELS = 14
ILX_TOTAL_DARK_PIXELS = 18
TCD_FIRST_USED_DARK_PIXEL = 0
TCD_USED_DARK_PIXELS = 12
TCD_TOTAL_DARK_PIXELS = 13
HAMS9840_FIRST_USED_DARK_PIXEL = 0
HAMS9840_USED_DARK_PIXELS = 8
HAMS9840_TOTAL_DARK_PIXELS = 8
HAMS10420_FIRST_USED_DARK_PIXEL = 0
HAMS10420_USED_DARK_PIXELS = 4
HAMS10420_TOTAL_DARK_PIXELS = 4
HAMS11071_FIRST_USED_DARK_PIXEL = 0
HAMS11071_USED_DARK_PIXELS = 4
HAMS11071_TOTAL_DARK_PIXELS = 4
HAMS7031_FIRST_USED_DARK_PIXEL = 0
HAMS7031_USED_DARK_PIXELS = 4
HAMS7031_TOTAL_DARK_PIXELS = 4
HAMS11155_TOTAL_DARK_PIXELS = 20
MIN_ILX_INTTIME = 1.1
MILLI_TO_MICRO = 1000
NR_DIGITAL_OUTPUTS = 13
NR_DIGITAL_INPUTS = 13
NTC1_ID = 0
NTC2_ID = 1
TEC_ID = 2
NR_ANALOG_OUTPUTS = 2
ETH_CONN_STATUS_CONNECTING = 0
ETH_CONN_STATUS_CONNECTED = 1
ETH_CONN_STATUS_CONNECTED_NOMON = 2
ETH_CONN_STATUS_NOCONNECTION = 3


ERROR_CODES = {
    -1: ('ERR_INVALID_PARAMETER',
         'Function called with invalid parameter value.'),
    -2: ('ERR_OPERATION_NOT_SUPPORTED',
         'Function not supported (e.g. use 16bit ADC mode with 14bit ADC hardware)'),
    -3: ('ERR_DEVICE_NOT_FOUND',
         'Opening communication failed or time-out during communication occurred.'),
    -4: ('ERR_INVALID_DEVICE_ID',
         'AvsHandle is unknown in the DLL'),
    -5: ('ERR_OPERATION_PENDING',
         'Function is called while result of previous call to AVS_Measure() is not received yet'),
    -6: ('ERR_TIMEOUT',
         'No answer received from device'),
    -7: ('Reserved',
         ''),
    -8: ('ERR_INVALID_MEAS_DATA',
         'No measurement data is received at the point AVS_GetScopeData() is called'),
    -9: ('ERR_INVALID_SIZE',
         'Allocated buffer size too small'),
    -10: ('ERR_INVALID_PIXEL_RANGE',
          'Measurement preparation failed because pixel range is invalid'),
    -11: ('ERR_INVALID_INT_TIME',
          'Measurement preparation failed because integration time is invalid (for selected sensor)'),
    -12: ('ERR_INVALID_COMBINATION',
          'Measurement preparation failed because of an invalid combination of parameters, e.g. integration time of 600000 and Navg > 5000'),
    -13: ('Reserved',
          ''),
    -14: ('ERR_NO_MEAS_BUFFER_AVAIL',
          'Measurement preparation failed because no measurement buffers available'),
    -15: ('ERR_UNKNOWN',
          'Unknown error reason received from spectrometer'),
    -16: ('ERR_COMMUNICATION',
          'Error in communication or Ethernet connection failure'),
    -17: ('ERR_NO_SPECTRA_IN_RAM',
          'No more spectra available in RAM, all read or measurement not started yet'),
    -18: ('ERR_INVALID_DLL_VERSION',
          'DLL version information could not be retrieved'),
    -19: ('ERR_NO_MEMORY',
          'Memory allocation error in the DLL'),
    -20: ('ERR_DLL_INITIALISATION',
          'Function called before AVS_Init() is called'),
    -21: ('ERR_INVALID_STATE',
          'Function failed because AvaSpec is in wrong state, e.g. AVS_Measure() without calling AVS_PrepareMeasurement() first'),
    -22: ('ERR_INVALID_REPLY',
          'Reply is not a recognized protocol message'),
    -23: ('Reserved',
          ''),
    -24: ('ERR_ACCESS',
          'Error occurred while opening a bus device on the host, e.g. USB device access denied due to user rights'),
    -100: ('ERR_INVALID_PARAMETER_NR_PIXEL',
           'NrOfPixel in Device data incorrect'),
    -101: ('ERR_INVALID_PARAMETER_ADC_GAIN',
           'Gain Setting Out of Range'),
    -102: ('ERR_INVALID_PARAMETER_ADC_OFFSET',
           'OffSet Setting Out of Range'),
    -110: ('ERR_INVALID_MEASPARAM_AVG_SAT2',
           'Use of Saturation Detection Level 2 is not compatible with the Averaging function'),
    -111: ('ERR_INVALID_MEASPARAM_AVG_RAM',
           'Use of Averaging is not compatible with the StoreToRam function'),
    -112: ('ERR_INVALID_MEASPARAM_SYNC_RAM',
           'Use of the Synchronize setting is not compatible with the StoreToRam function'),
    -113: ('ERR_INVALID_MEASPARAM_LEVEL_RAM',
           'Use of Level Triggering is not compatible with the StoreToRam function'),
    -114: ('ERR_INVALID_MEASPARAM_SAT2_RAM',
           'Use of Saturation Detection Level 2 Parameter is not compatible with the StoreToRam function'),
    -115: ('ERR_INVALID_MEASPARAM_FWVER_RAM',
           'The StoreToRam function is only supported with firmware version 0.20.0.0 or later.'),
    -116: ('ERR_INVALID_MEASPARAM_DYNDARK',
           'Dynamic Dark Correction not supported'),
    -120: ('ERR_NOT_SUPPORTED_BY_SENSOR_TYPE',
           'Use of AVS_SetSensitivityMode() not supported by detector type'),
    -121: ('ERR_NOT_SUPPORTED_BY_FW_VER',
           'Use of AVS_SetSensitivityMode() not supported by firmware version'),
    -122: ('ERR_NOT_SUPPORTED_BY_FPGA_VER',
           'Use of AVS_SetSensitivityMode() not supported by FPGA version'),
    -140: ('ERR_SL_CALIBRATION_NOT_AVAILABLE',
           'Spectrometer was not calibrated for stray light correction'),
    -141: ('ERR_SL_STARTPIXEL_NOT_IN_RANGE',
           'Incorrect start pixel found in EEPROM'),
    -142: ('ERR_SL_ENDPIXEL_NOT_IN_RANGE',
           'Incorrect end pixel found in EEPROM'),
    -143: ('ERR_SL_STARTPIX_GT_ENDPIX',
           'Incorrect start or end pixel found in EEPROM'),
    -144: ('ERR_SL_MFACTOR_OUT_OF_RANGE',
           'Factor should be in range 0.0 - 4.0'),
}


class DeviceStatus(IntEnum):
    """DeviceStatus enum."""
    UNKNOWN = 0
    USB_AVAILABLE = 1
    USB_IN_USE_BY_APPLICATION = 2
    USB_IN_USE_BY_OTHER = 3
    ETH_AVAILABLE = 4
    ETH_IN_USE_BY_APPLICATION = 5
    ETH_IN_USE_BY_OTHER = 6
    ETH_ALREADY_IN_USE_USB = 7


class InterfaceType(IntEnum):
    """InterfaceType enum."""
    RS232 = 0
    USB5216 = 1
    USBMINI = 2
    USB7010 = 3
    ETH7010 = 4


class SensType(IntEnum):
    """SensType enum."""
    SENS_HAMS8378_256 = 1
    SENS_HAMS8378_1024 = 2
    SENS_ILX554 = 3
    SENS_HAMS9201 = 4
    SENS_TCD1304 = 5
    SENS_TSL1301 = 6
    SENS_TSL1401 = 7
    SENS_HAMS8378_512 = 8
    SENS_HAMS9840 = 9
    SENS_ILX511 = 10
    SENS_HAMS10420_2048X64 = 11
    SENS_HAMS11071_2048X64 = 12
    SENS_HAMS7031_1024X122 = 13
    SENS_HAMS7031_1024X58 = 14
    SENS_HAMS11071_2048X16 = 15
    SENS_HAMS11155_2048 = 16
    SENS_SU256LSB = 17
    SENS_SU512LDB = 18
    SENS_HAMS11638 = 21
    SENS_HAMS11639 = 22
    SENS_HAMS12443 = 23
    SENS_HAMG9208_512 = 24
    SENS_HAMG13913 = 25
    SENS_HAMS13496 = 26


class AvsIdentityType(Structure):
    """IdentityType Structure."""
    _pack_ = 1
    _fields_ = [
        ('SerialNumber', c_char * AVS_SERIAL_LEN),
        ('UserFriendlyName', c_char * USER_ID_LEN),
        ('Status', c_ubyte)
    ]


class BroadcastAnswerType(Structure):
    """BroadcastAnswerType Structure."""
    _pack_ = 1
    _fields_ = [
        ('InterfaceType', c_ubyte),
        ('serial', c_ubyte * AVS_SERIAL_LEN),
        ('port', c_uint16),
        ('status', c_ubyte),
        ('RemoteHostIp', c_uint32),
        ('LocalIp', c_uint32),
        ('reserved', c_ubyte * 4)
    ]


class ControlSettingsType(Structure):
    """ControlSettingsType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_StrobeControl', c_uint16),
        ('m_LaserDelay', c_uint32),
        ('m_LaserWidth', c_uint32),
        ('m_LaserWaveLength', c_float),
        ('m_StoreToRam', c_uint16),
    ]


class DarkCorrectionType(Structure):
    """DarkCorrectionType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Enable', c_ubyte),
        ('m_ForgetPercentage', c_ubyte),
    ]


class DetectorType(Structure):
    """DetectorType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_SensorType', c_ubyte),
        ('m_NrPixels', c_uint16),
        ('m_aFit', c_float * NR_WAVELEN_POL_COEF),
        ('m_NLEnable', c_bool),
        ('m_aNLCorrect', c_double * NR_NONLIN_POL_COEF),
        ('m_aLowNLCounts', c_double),
        ('m_aHighNLCounts', c_double),
        ('m_Gain', c_float * MAX_VIDEO_CHANNELS),
        ('m_Reserved', c_float),
        ('m_Offset', c_float * MAX_VIDEO_CHANNELS),
        ('m_ExtOffset', c_float),
        ('m_DefectivePixels', c_uint16 * NR_DEFECTIVE_PIXELS)
    ]


class SmoothingType(Structure):
    """SmoothingType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_SmoothPix', c_uint16),
        ('m_SmoothModel', c_ubyte),
    ]


class SpectrumCalibrationType(Structure):
    """SpectrumCalibrationType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Smoothing', SmoothingType),
        ('m_CalInttime', c_float),
        ('m_aCalibConvers', c_float * MAX_NR_PIXELS),
    ]


class IrradianceType(Structure):
    """IrradianceType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_IntensityCalib', SpectrumCalibrationType),
        ('m_CalibrationType', c_ubyte),
        ('m_FiberDiameter', c_uint32),
    ]


class SpectrumCorrectionType(Structure):
    """SpectrumCorrectionType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_aSpectrumCorrect', c_float * MAX_NR_PIXELS),
    ]


class TriggerType(Structure):
    """TriggerType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Mode', c_ubyte),
        ('m_Source', c_ubyte),
        ('m_SourceType', c_ubyte),
    ]


class MeasConfigType(Structure):
    """MeasConfigType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_StartPixel', c_uint16),
        ('m_StopPixel', c_uint16),
        ('m_IntegrationTime', c_float),
        ('m_IntegrationDelay', c_uint32),
        ('m_NrAverages', c_uint32),
        ('m_CorDynDark', DarkCorrectionType),
        ('m_Smoothing', SmoothingType),
        ('m_SaturationDetection', c_ubyte),
        ('m_Trigger', TriggerType),
        ('m_Control', ControlSettingsType)
    ]


class TimeStampType(Structure):
    """TimeStampType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Date', c_uint16),
        ('m_Time', c_uint16),
    ]


class StandAloneType(Structure):
    """StandAloneType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Enable', c_bool),
        ('m_Meas', MeasConfigType),
        ('m_Nmsr', c_int16)
    ]


class DynamicStorageType(Structure):
    """DynamicStorageType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Nmsr', c_int32),
        ('m_Reserved', c_ubyte * 8),
    ]


class TempSensorType(Structure):
    """TempSensorType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_aFit', c_float * NR_TEMP_POL_COEF),
    ]


class TecControlType(Structure):
    """TecControlType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Enable', c_bool),
        ('m_Setpoint', c_float),
        ('m_aFit', c_float * NR_DAC_POL_COEF),
    ]


class ProcessControlType(Structure):
    """ProcessControlType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_AnalogLow', c_float * 2),
        ('m_AnalogHigh', c_float * 2),
        ('m_DigitalLow', c_float * 10),
        ('m_DigitalHigh', c_float * 10),
    ]


class EthernetSettingsType(Structure):
    """EthernetSettingsType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_IpAddr', c_uint32),
        ('m_NetMask', c_uint32),
        ('m_Gateway', c_uint32),
        ('m_DhcpEnabled', c_ubyte),
        ('m_TcpPort', c_uint16),
        ('m_LinkStatus', c_ubyte),
    ]


class OemDataType(Structure):
    """OemDataType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_data', c_ubyte * OEM_DATA_LEN)
    ]


class HeartbeatRespType(Structure):
    """HeartbeatRespType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_BitMatrix', c_uint32),
        ('m_Reserved', c_uint32)
    ]


class DeviceConfigType(Structure):
    """DeviceConfigType Structure."""
    _pack_ = 1
    _fields_ = [
        ('m_Len', c_uint16),
        ('m_ConfigVersion', c_uint16),
        ('m_aUserFriendlyId', c_char * USER_ID_LEN),
        ('m_Detector', DetectorType),
        ('m_Irradiance', IrradianceType),
        ('m_Reflectance', SpectrumCalibrationType),
        ('m_SpectrumCorrect', SpectrumCorrectionType),
        ('m_StandAlone', StandAloneType),
        ('m_DynamicStorage', DynamicStorageType),
        ('m_aTemperature', TempSensorType * MAX_TEMP_SENSORS),
        ('m_TecControl', TecControlType),
        ('m_ProcessControl', ProcessControlType),
        ('m_EthernetSettings', EthernetSettingsType),
        ('m_aReserved', c_ubyte * SETTINGS_RESERVED_LEN),
        ('m_OemData', OemDataType)
    ]


if IS_WINDOWS:
    from ctypes import WINFUNCTYPE
    FUNCTYPE = WINFUNCTYPE
else:
    from ctypes import CFUNCTYPE
    FUNCTYPE = CFUNCTYPE

_handles: list[int] = []

MeasureCallback = FUNCTYPE(None, POINTER(c_int32), POINTER(c_int32))
"""Used as a decorator for a callback function when a scan is available."""


@register(manufacturer=r'Avantes', model=r'.')
class Avantes(ConnectionSDK):

    # constants
    WM_MEAS_READY = WM_MEAS_READY
    SETTINGS_RESERVED_LEN = SETTINGS_RESERVED_LEN
    INVALID_AVS_HANDLE_VALUE = INVALID_AVS_HANDLE_VALUE
    USER_ID_LEN = USER_ID_LEN
    AVS_SERIAL_LEN = AVS_SERIAL_LEN
    MAX_TEMP_SENSORS = MAX_TEMP_SENSORS
    ROOT_NAME_LEN = ROOT_NAME_LEN
    VERSION_LEN = VERSION_LEN
    AVASPEC_ERROR_MSG_LEN = AVASPEC_ERROR_MSG_LEN
    AVASPEC_MIN_MSG_LEN = AVASPEC_MIN_MSG_LEN
    OEM_DATA_LEN = OEM_DATA_LEN
    NR_WAVELEN_POL_COEF = NR_WAVELEN_POL_COEF
    NR_NONLIN_POL_COEF = NR_NONLIN_POL_COEF
    MAX_VIDEO_CHANNELS = MAX_VIDEO_CHANNELS
    NR_DEFECTIVE_PIXELS = NR_DEFECTIVE_PIXELS
    MAX_NR_PIXELS = MAX_NR_PIXELS
    NR_TEMP_POL_COEF = NR_TEMP_POL_COEF
    NR_DAC_POL_COEF = NR_DAC_POL_COEF
    SAT_PEAK_INVERSION = SAT_PEAK_INVERSION
    SW_TRIGGER_MODE = SW_TRIGGER_MODE
    HW_TRIGGER_MODE = HW_TRIGGER_MODE
    SS_TRIGGER_MODE = SS_TRIGGER_MODE
    EXTERNAL_TRIGGER = EXTERNAL_TRIGGER
    SYNC_TRIGGER = SYNC_TRIGGER
    EDGE_TRIGGER_SOURCE = EDGE_TRIGGER_SOURCE
    LEVEL_TRIGGER_SOURCE = LEVEL_TRIGGER_SOURCE
    ILX_FIRST_USED_DARK_PIXEL = ILX_FIRST_USED_DARK_PIXEL
    ILX_USED_DARK_PIXELS = ILX_USED_DARK_PIXELS
    ILX_TOTAL_DARK_PIXELS = ILX_TOTAL_DARK_PIXELS
    TCD_FIRST_USED_DARK_PIXEL = TCD_FIRST_USED_DARK_PIXEL
    TCD_USED_DARK_PIXELS = TCD_USED_DARK_PIXELS
    TCD_TOTAL_DARK_PIXELS = TCD_TOTAL_DARK_PIXELS
    HAMS9840_FIRST_USED_DARK_PIXEL = HAMS9840_FIRST_USED_DARK_PIXEL
    HAMS9840_USED_DARK_PIXELS = HAMS9840_USED_DARK_PIXELS
    HAMS9840_TOTAL_DARK_PIXELS = HAMS9840_TOTAL_DARK_PIXELS
    HAMS10420_FIRST_USED_DARK_PIXEL = HAMS10420_FIRST_USED_DARK_PIXEL
    HAMS10420_USED_DARK_PIXELS = HAMS10420_USED_DARK_PIXELS
    HAMS10420_TOTAL_DARK_PIXELS = HAMS10420_TOTAL_DARK_PIXELS
    HAMS11071_FIRST_USED_DARK_PIXEL = HAMS11071_FIRST_USED_DARK_PIXEL
    HAMS11071_USED_DARK_PIXELS = HAMS11071_USED_DARK_PIXELS
    HAMS11071_TOTAL_DARK_PIXELS = HAMS11071_TOTAL_DARK_PIXELS
    HAMS7031_FIRST_USED_DARK_PIXEL = HAMS7031_FIRST_USED_DARK_PIXEL
    HAMS7031_USED_DARK_PIXELS = HAMS7031_USED_DARK_PIXELS
    HAMS7031_TOTAL_DARK_PIXELS = HAMS7031_TOTAL_DARK_PIXELS
    HAMS11155_TOTAL_DARK_PIXELS = HAMS11155_TOTAL_DARK_PIXELS
    MIN_ILX_INTTIME = MIN_ILX_INTTIME
    MILLI_TO_MICRO = MILLI_TO_MICRO
    NR_DIGITAL_OUTPUTS = NR_DIGITAL_OUTPUTS
    NR_DIGITAL_INPUTS = NR_DIGITAL_INPUTS
    NTC1_ID = NTC1_ID
    NTC2_ID = NTC2_ID
    TEC_ID = TEC_ID
    NR_ANALOG_OUTPUTS = NR_ANALOG_OUTPUTS
    ETH_CONN_STATUS_CONNECTING = ETH_CONN_STATUS_CONNECTING
    ETH_CONN_STATUS_CONNECTED = ETH_CONN_STATUS_CONNECTED
    ETH_CONN_STATUS_CONNECTED_NOMON = ETH_CONN_STATUS_CONNECTED_NOMON
    ETH_CONN_STATUS_NOCONNECTION = ETH_CONN_STATUS_NOCONNECTION

    # enums
    DeviceStatus = DeviceStatus
    InterfaceType = InterfaceType
    SensType = SensType

    # structs
    AvsIdentityType = AvsIdentityType
    BroadcastAnswerType = BroadcastAnswerType
    ControlSettingsType = ControlSettingsType
    DarkCorrectionType = DarkCorrectionType
    DetectorType = DetectorType
    SmoothingType = SmoothingType
    SpectrumCalibrationType = SpectrumCalibrationType
    IrradianceType = IrradianceType
    SpectrumCorrectionType = SpectrumCorrectionType
    TriggerType = TriggerType
    MeasConfigType = MeasConfigType
    TimeStampType = TimeStampType
    StandAloneType = StandAloneType
    DynamicStorageType = DynamicStorageType
    TempSensorType = TempSensorType
    TecControlType = TecControlType
    ProcessControlType = ProcessControlType
    EthernetSettingsType = EthernetSettingsType
    OemDataType = OemDataType
    HeartbeatRespType = HeartbeatRespType
    DeviceConfigType = DeviceConfigType

    def __init__(self, record):
        """Wrapper around the ``avaspec.dll`` SDK from Avantes.

        The :attr:`~msl.equipment.record_types.ConnectionRecord.properties`
        for an Avantes connection supports the following key-value pairs in the
        :ref:`connections-database`::

            'port_id': int, One of -1 (Ethernet+USB), 0 (USB) or 256 (Ethernet) [default: -1]
            'activate': bool, Whether to automatically activate the connection [default: True]

        Do not instantiate this class directly. Use the :meth:`~.EquipmentRecord.connect`
        method to connect to the equipment.

        Parameters
        ----------
        record : :class:`~.EquipmentRecord`
            A record from an :ref:`equipment-database`.
        """
        self._handle = None
        self._sdk = None
        libtype = 'windll' if IS_WINDOWS else 'cdll'
        super(Avantes, self).__init__(record, libtype)
        self.set_exception_class(AvantesError)

        functions = {
            'AVS_Init': (c_int32, self._err_check,
                [('a_Port', c_int16)]),
            'AVS_Done': (c_int32, self._err_check,
                []),
            'AVS_GetNrOfDevices': (c_int32, self.log_errcheck,
                []),
            'AVS_UpdateUSBDevices': (c_int32, self.log_errcheck,
                []),
            'AVS_UpdateETHDevices': (c_int32, self._err_check,
                [('a_ListSize', c_uint32),
                 ('a_pRequiredSize', POINTER(c_uint32)),
                 ('a_pList', POINTER(BroadcastAnswerType))]),
            'AVS_GetList': (c_int32, self._err_check,
                [('a_ListSize', c_uint32),
                 ('a_pRequiredSize', POINTER(c_uint32)),
                 ('a_pList', POINTER(AvsIdentityType))]),
            'AVS_Activate': (c_int32, self._err_check,
                [('a_pDeviceId', POINTER(AvsIdentityType))]),
            'AVS_ActivateConn': (c_int32, self._err_check,
                [('a_pDeviceId', POINTER(AvsIdentityType))]),
            'AVS_ActivateConnCb': (c_int32, self._err_check,
                [('a_pDeviceId', POINTER(AvsIdentityType))]),
            'AVS_Deactivate': (c_bool, self._check_bool,
                [('a_hDevice', c_int32)]),
            'AVS_GetHandleFromSerial': (c_int32, self._err_check,
                [('a_pSerial', c_char_p)]),
            'AVS_GetStatusBySerial': (c_int32, self._err_check,
                [('a_pSerial', c_char_p),
                 ('a_status', POINTER(c_int32))]),
            'AVS_Register': (c_bool, self._check_bool,
                [('a_Hwnd', c_void_p)]),
            'AVS_Measure': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_hWnd', c_void_p),
                 ('a_Nmsr', c_int16)]),
            'AVS_MeasureCallback': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('__Done', MeasureCallback),
                 ('a_Nmsr', c_int16)]),
            'AVS_PrepareMeasure': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pMeasConfig', POINTER(MeasConfigType))]),
            'AVS_StopMeasure': (c_int32, self._err_check,
                [('a_hDevice', c_int32)]),
            'AVS_PollScan': (c_int32, self._err_check,
                [('a_hDevice', c_int32)]),
            'AVS_GetScopeData': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pTimeLabel', POINTER(c_uint32)),
                 ('a_pSpectrum', POINTER(c_double))]),
            'AVS_GetSaturatedPixels': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pSaturated', POINTER(c_ubyte))]),
            'AVS_GetLambda': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pWaveLength', POINTER(c_double))]),
            'AVS_GetNumPixels': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pNumPixels', POINTER(c_uint16))]),
            'AVS_GetParameter': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_Size', c_uint32),
                 ('a_pRequiredSize', POINTER(c_uint32)),
                 ('a_pDeviceParm', POINTER(DeviceConfigType))]),
            'AVS_SetParameter': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pDeviceParm', POINTER(DeviceConfigType))]),
            'AVS_GetVersionInfo': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pFPGAVersion', c_char_p),
                 ('a_pFirmwareVersion', c_char_p),
                 ('a_pDLLVersion', c_char_p)]),
            'AVS_GetDLLVersion': (c_int32, self._err_check,
                [('a_pVersionString', c_char_p)]),
            'AVS_SetSyncMode': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_Enable', c_ubyte)]),
            'AVS_SetPrescanMode': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_Prescan', c_bool)]),
            'AVS_UseHighResAdc': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_Enable', c_bool)]),
            'AVS_GetAnalogIn': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_AnalogInId', c_ubyte),
                 ('a_pAnalogIn', POINTER(c_float))]),
            'AVS_GetDigIn': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_DigInId', c_ubyte),
                 ('a_pDigIn', POINTER(c_ubyte))]),
            'AVS_SetAnalogOut': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_PortId', c_ubyte),
                 ('a_Value', c_float)]),
            'AVS_SetDigOut': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_PortId', c_ubyte),
                 ('a_Status', c_ubyte)]),
            'AVS_SetPwmOut': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_PortId', c_ubyte),
                 ('a_Freq', c_ulong),
                 ('a_Duty', c_ubyte)]),
            'AVS_GetDarkPixelData': (c_int32, self._check_bool,
                [('a_hDevice', c_int32),
                 ('a_pDarkData', POINTER(c_double))]),
            'AVS_GetComPortName': (c_int32, self._check_bool,
                [('a_pDeviceId', POINTER(AvsIdentityType)),
                 ('a_pIp', c_char_p),
                 ('a_size', POINTER(c_int32))]),
            'AVS_GetComType': (c_int32, self._err_check,
                [('a_pDeviceId', POINTER(AvsIdentityType)),
                 ('a_type', POINTER(c_int32))]),
            'AVS_SetSensitivityMode': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_SensitivityMode', c_uint32)]),
            'AVS_GetIpConfig': (c_int32, self._check_bool,
                [('a_hDevice', c_int32),
                 ('a_Data', POINTER(EthernetSettingsType))]),
            'AVS_SuppressStrayLight': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_Multifactor', c_float),
                 ('a_pSrcSpectrum', POINTER(c_double)),
                 ('a_pDestSpectrum', POINTER(c_double))]),
            'AVS_Heartbeat': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pHbReq', POINTER(c_uint32)),
                 ('a_pHbResp', POINTER(HeartbeatRespType))]),
            'AVS_ResetDevice': (c_int32, self._err_check,
                [('a_hDevice', c_int32)]),
            'AVS_GetOemParameter': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pOemData', POINTER(OemDataType))]),
            'AVS_SetOemParameter': (c_int32, self._err_check,
                [('a_hDevice', c_int32),
                 ('a_pOemData', POINTER(OemDataType))]),
        }

        for key, value in functions.items():
            try:
                attr = getattr(self.sdk, key)
            except AttributeError as e:
                self.log_debug('%s: %s', self.__class__.__name__, e)
                continue
            attr.restype, attr.errcheck = value[:2]
            attr.argtypes = [typ for _, typ in value[2]]

        props = record.connection.properties
        self.init(props.get('port_id', -1))
        if props.get('activate', True):
            self.activate()

    _avaspec_msl_original_backup_methods_err_check = _bind_avaspec_msl_original_backup_methods_err_check(_refactor_modules[__name__])
    _err_check = _avaspec_msl_original_backup_methods_err_check["_err_check"]

    _check_bool = _avaspec_msl_original_backup_methods_err_check["_check_bool"]

    activate = _avaspec_msl_original_backup_methods_err_check["activate"]

    deactivate = _avaspec_msl_original_backup_methods_err_check["deactivate"]

    get_analog_in = _avaspec_msl_original_backup_methods_err_check["get_analog_in"]

    get_com_port_name = _avaspec_msl_original_backup_methods_err_check["get_com_port_name"]

    get_com_type = _avaspec_msl_original_backup_methods_err_check["get_com_type"]

    get_dark_pixel_data = _avaspec_msl_original_backup_methods_err_check["get_dark_pixel_data"]

    get_dll_version = _avaspec_msl_original_backup_methods_err_check["get_dll_version"]

    get_digital_in = _avaspec_msl_original_backup_methods_err_check["get_digital_in"]

    get_handle_from_serial = _avaspec_msl_original_backup_methods_err_check["get_handle_from_serial"]

    find = (staticmethod)(_avaspec_msl_original_backup_methods_err_check["find"])

    get_status_by_serial = _avaspec_msl_original_backup_methods_err_check["get_status_by_serial"]

    done = _avaspec_msl_original_backup_methods_err_check["done"]

    disconnect = _avaspec_msl_original_backup_methods_err_check["disconnect"]

    get_ip_config = _avaspec_msl_original_backup_methods_err_check["get_ip_config"]

    get_lambda = _avaspec_msl_original_backup_methods_err_check["get_lambda"]

    get_num_devices = _avaspec_msl_original_backup_methods_err_check["get_num_devices"]

    get_oem_parameter = _avaspec_msl_original_backup_methods_err_check["get_oem_parameter"]

    get_parameter = _avaspec_msl_original_backup_methods_err_check["get_parameter"]

    get_saturated_pixels = _avaspec_msl_original_backup_methods_err_check["get_saturated_pixels"]

    get_version_info = _avaspec_msl_original_backup_methods_err_check["get_version_info"]

    get_data = _avaspec_msl_original_backup_methods_err_check["get_data"]

    get_num_pixels = _avaspec_msl_original_backup_methods_err_check["get_num_pixels"]

    heartbeat = _avaspec_msl_original_backup_methods_err_check["heartbeat"]

    init = _avaspec_msl_original_backup_methods_err_check["init"]

    measure = _avaspec_msl_original_backup_methods_err_check["measure"]
    del _avaspec_msl_original_backup_methods_err_check

    _avaspec_msl_original_backup_methods_measure_callback = _bind_avaspec_msl_original_backup_methods_measure_callback(_refactor_modules[__name__])
    measure_callback = _avaspec_msl_original_backup_methods_measure_callback["measure_callback"]

    poll_scan = _avaspec_msl_original_backup_methods_measure_callback["poll_scan"]

    prepare_measure = _avaspec_msl_original_backup_methods_measure_callback["prepare_measure"]

    register = _avaspec_msl_original_backup_methods_measure_callback["register"]

    reset_device = _avaspec_msl_original_backup_methods_measure_callback["reset_device"]

    set_analog_out = _avaspec_msl_original_backup_methods_measure_callback["set_analog_out"]

    set_digital_out = _avaspec_msl_original_backup_methods_measure_callback["set_digital_out"]

    set_oem_parameter = _avaspec_msl_original_backup_methods_measure_callback["set_oem_parameter"]

    set_parameter = _avaspec_msl_original_backup_methods_measure_callback["set_parameter"]

    set_prescan_mode = _avaspec_msl_original_backup_methods_measure_callback["set_prescan_mode"]

    set_pwm_out = _avaspec_msl_original_backup_methods_measure_callback["set_pwm_out"]

    set_sensitivity_mode = _avaspec_msl_original_backup_methods_measure_callback["set_sensitivity_mode"]

    set_sync_mode = _avaspec_msl_original_backup_methods_measure_callback["set_sync_mode"]

    stop_measure = _avaspec_msl_original_backup_methods_measure_callback["stop_measure"]

    suppress_stray_light = _avaspec_msl_original_backup_methods_measure_callback["suppress_stray_light"]

    update_eth_devices = _avaspec_msl_original_backup_methods_measure_callback["update_eth_devices"]

    update_usb_devices = _avaspec_msl_original_backup_methods_measure_callback["update_usb_devices"]

    use_high_res_adc = _avaspec_msl_original_backup_methods_measure_callback["use_high_res_adc"]
    del _avaspec_msl_original_backup_methods_measure_callback
