"""Trailing structures from the XIMC Python ctypes binding."""

from ctypes import *


class debug_read_t(Structure):
    _fields_ = [
        ("DebugData", c_ubyte * 128),
    ]


class debug_write_t(Structure):
    _fields_ = [
        ("DebugData", c_ubyte * 128),
    ]


class stage_name_t(Structure):
    _fields_ = [
        ("PositionerName", c_char * 17),
    ]


class stage_information_t(Structure):
    _fields_ = [
        ("Manufacturer", c_char * 17),
        ("PartNumber", c_char * 25),
    ]


class stage_settings_t(Structure):
    _fields_ = [
        ("LeadScrewPitch", c_float),
        ("Units", c_char * 9),
        ("MaxSpeed", c_float),
        ("TravelRange", c_float),
        ("SupplyVoltageMin", c_float),
        ("SupplyVoltageMax", c_float),
        ("MaxCurrentConsumption", c_float),
        ("HorizontalLoadCapacity", c_float),
        ("VerticalLoadCapacity", c_float),
    ]


class motor_information_t(Structure):
    _fields_ = [
        ("Manufacturer", c_char * 17),
        ("PartNumber", c_char * 25),
    ]


class motor_settings_t(Structure):
    _fields_ = [
        ("MotorType", c_uint),
        ("ReservedField", c_uint),
        ("Poles", c_uint),
        ("Phases", c_uint),
        ("NominalVoltage", c_float),
        ("NominalCurrent", c_float),
        ("NominalSpeed", c_float),
        ("NominalTorque", c_float),
        ("NominalPower", c_float),
        ("WindingResistance", c_float),
        ("WindingInductance", c_float),
        ("RotorInertia", c_float),
        ("StallTorque", c_float),
        ("DetentTorque", c_float),
        ("TorqueConstant", c_float),
        ("SpeedConstant", c_float),
        ("SpeedTorqueGradient", c_float),
        ("MechanicalTimeConstant", c_float),
        ("MaxSpeed", c_float),
        ("MaxCurrent", c_float),
        ("MaxCurrentTime", c_float),
        ("NoLoadCurrent", c_float),
        ("NoLoadSpeed", c_float),
    ]


class encoder_information_t(Structure):
    _fields_ = [
        ("Manufacturer", c_char * 17),
        ("PartNumber", c_char * 25),
    ]


class encoder_settings_t(Structure):
    _fields_ = [
        ("MaxOperatingFrequency", c_float),
        ("SupplyVoltageMin", c_float),
        ("SupplyVoltageMax", c_float),
        ("MaxCurrentConsumption", c_float),
        ("PPR", c_uint),
        ("EncoderSettings", c_uint),
    ]


class hallsensor_information_t(Structure):
    _fields_ = [
        ("Manufacturer", c_char * 17),
        ("PartNumber", c_char * 25),
    ]


class hallsensor_settings_t(Structure):
    _fields_ = [
        ("MaxOperatingFrequency", c_float),
        ("SupplyVoltageMin", c_float),
        ("SupplyVoltageMax", c_float),
        ("MaxCurrentConsumption", c_float),
        ("PPR", c_uint),
    ]


class gear_information_t(Structure):
    _fields_ = [
        ("Manufacturer", c_char * 17),
        ("PartNumber", c_char * 25),
    ]


class gear_settings_t(Structure):
    _fields_ = [
        ("ReductionIn", c_float),
        ("ReductionOut", c_float),
        ("RatedInputTorque", c_float),
        ("RatedInputSpeed", c_float),
        ("MaxOutputBacklash", c_float),
        ("InputInertia", c_float),
        ("Efficiency", c_float),
    ]


class accessories_settings_t(Structure):
    _fields_ = [
        ("MagneticBrakeInfo", c_char * 25),
        ("MBRatedVoltage", c_float),
        ("MBRatedCurrent", c_float),
        ("MBTorque", c_float),
        ("MBSettings", c_uint),
        ("TemperatureSensorInfo", c_char * 25),
        ("TSMin", c_float),
        ("TSMax", c_float),
        ("TSGrad", c_float),
        ("TSSettings", c_uint),
        ("LimitSwitchesSettings", c_uint),
    ]


class init_random_t(Structure):
    _fields_ = [
        ("key", c_ubyte * 16),
    ]


class globally_unique_identifier_t(Structure):
    _fields_ = [
        ("UniqueID0", c_uint),
        ("UniqueID1", c_uint),
        ("UniqueID2", c_uint),
        ("UniqueID3", c_uint),
    ]


class command_change_motor_t(Structure):
    _fields_ = [
        ("Motor", c_uint),
    ]
