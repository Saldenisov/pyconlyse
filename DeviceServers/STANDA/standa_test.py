import os
from ctypes import *

try:
    from DeviceServers.STANDA.ximc import (lib, device_information_t, Result, status_t,
                                                         get_position_t, motor_settings_t, move_settings_t,
                                                         engine_settings_t, MicrostepMode, EnumerateFlags,
                                                         controller_name_t, ximc_dir)

except ImportError as err:
    print("Can't import pyximc module."
          "The most probable reason is that you changed the relative location of the testpython.py and pyximc.py files. "
          "See developers' documentation for details.")
    exit()
except OSError as err:
    print("Can't load libximc library."
          "Please add all shared libraries to the appropriate places."
          "It is decribed in detail in developers' documentation."
          "On Linux make sure you installed libximc-dev package."
          "\nmake sure that the architecture of the system and the interpreter is the same")
    exit()


def test_info(lib, device_id):
    print("\nGet device info")
    x_device_information = device_information_t()
    result = lib.get_device_information(device_id, byref(x_device_information))
    print("Result: " + repr(result))
    if result == Result.Ok:
        print("Device information:")
        print(" Manufacturer: " +
              repr(string_at(x_device_information.Manufacturer).decode()))
        print(" ManufacturerId: " +
              repr(string_at(x_device_information.ManufacturerId).decode()))
        print(" ProductDescription: " +
              repr(string_at(x_device_information.ProductDescription).decode()))
        print(" Major: " + repr(x_device_information.Major))
        print(" Minor: " + repr(x_device_information.Minor))
        print(" Release: " + repr(x_device_information.Release))


def test_status(lib, device_id):
    print("\nGet status")
    x_status = status_t()
    result = lib.get_status(device_id, byref(x_status))
    print("Result: " + repr(result))
    if result == Result.Ok:
        print("Status.Ipwr: " + repr(x_status.Ipwr))
        print("Status.Upwr: " + repr(x_status.Upwr))
        print("Status.Iusb: " + repr(x_status.Iusb))
        print("Status.Flags: " + repr(hex(x_status.Flags)))


def test_get_position(lib, device_id):
    print("\nRead position")
    x_pos = get_position_t()
    result = lib.get_position(device_id, byref(x_pos))
    print("Result: " + repr(result))
    if result == Result.Ok:
        print("Position: {0} steps, {1} microsteps".format(x_pos.Position, x_pos.uPosition))
    return x_pos.Position, x_pos.uPosition


def test_left(lib, device_id):
    print("\nMoving left")
    result = lib.command_left(device_id)
    print("Result: " + repr(result))


def test_move(lib, device_id, distance, udistance):
    print("\nGoing to {0} steps, {1} microsteps".format(distance, udistance))
    result = lib.command_move(device_id, distance, udistance)
    print("Result: " + repr(result))


def test_wait_for_stop(lib, device_id, interval):
    print("\nWaiting for stop")
    result = lib.command_wait_for_stop(device_id, interval)
    print("Result: " + repr(result))


def test_serial_number(lib, device_id):
    print("\nReading serial")
    x_serial = c_uint()
    result = lib.get_serial_number(device_id, byref(x_serial))
    if result == Result.Ok:
        print("Serial: " + repr(x_serial.value))

def test_get_speed(lib, device_id):
    print("\nGet speed")
    # Create move settings structure
    mvst = move_settings_t()
    # Get current move settings from controller
    result = lib.get_move_settings(device_id, byref(mvst))
    # Print command return status. It will be 0 if all is OK
    print("Read command result: " + repr(result))

    return mvst.Speed


def test_set_speed(lib, device_id, speed):
    print("\nSet speed")
    # Create move settings structure
    mvst = move_settings_t()
    # Get current move settings from controller
    result = lib.get_move_settings(device_id, byref(mvst))
    # Print command return status. It will be 0 if all is OK
    print("Read command result: " + repr(result))
    print("The speed was equal to {0}. We will change it to {1}".format(mvst.Speed, speed))
    # Change current speed
    mvst.Speed = int(speed)
    # Write new move settings to controller
    result = lib.set_move_settings(device_id, byref(mvst))
    # Print command return status. It will be 0 if all is OK
    print("Write command result: " + repr(result))


def test_set_microstep_mode_256(lib, device_id):
    print("\nSet microstep mode to 256")
    # Create engine settings structure
    eng = engine_settings_t()
    # Get current engine settings from controller
    result = lib.get_engine_settings(device_id, byref(eng))
    # Print command return status. It will be 0 if all is OK
    print("Read command result: " + repr(result))
    # Change MicrostepMode parameter to MICROSTEP_MODE_FRAC_256
    # (use MICROSTEP_MODE_FRAC_128, MICROSTEP_MODE_FRAC_64 ... for other microstep modes)
    eng.MicrostepMode = MicrostepMode.MICROSTEP_MODE_FRAC_256
    # Write new engine settings to controller
    result = lib.set_engine_settings(device_id, byref(eng))
    # Print command return status. It will be 0 if all is OK
    print("Write command result: " + repr(result))


# variable 'lib' points to tests_devices loaded library
# note that ximc uses stdcall on win

sbuf = create_string_buffer(64)
lib.ximc_version(sbuf)

"""
Set bindy (network) keyfile. Must be called before any call to "enumerate_devices" or "open_device" if you
wish to use network-attached controllers. Accepts both absolute and relative paths, relative paths are resolved
relative to the process working directory. If you do not need network soft then "set_bindy_key" is optional.
In Python make sure to pass byte-array object to this function (b"string literal").
"""
lib.set_bindy_key(os.path.join(ximc_dir, "win32", "keyfile.sqlite").encode("utf-8"))

# This is device search and enumeration with probing. It gives more information about soft.
probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
enum_hints = b"addr=10.20.30.204, 10.20.30.202"
# enum_hints = b"addr=" # Use this hint string for broadcast enumerate
devenum = lib.enumerate_devices(probe_flags, enum_hints)
dev_count = lib.get_device_count(devenum)

names = []
device_ids = {}
pos = {}
for i in range(dev_count):
    name = lib.get_device_name(devenum, i)
    names.append(name)
    device_id = lib.open_device(name)
    device_ids[name] = device_id
    pos[name] = test_get_position(lib, device_ids[name])
    friendly_name = controller_name_t()
    result = lib.get_controller_name(name, byref(friendly_name))
    friendly_name = friendly_name.ControllerName
    x_serial = c_uint()
    result = lib.get_serial_number(device_id, byref(x_serial))



for i in [2, 3, 1, 4]:
    res = lib.close_device(byref(cast(i, POINTER(c_int))))

from time import sleep
from random import randint
for i in range(1000):
    print(f'i: {i}')
    for name in device_ids.keys():
        x, y = randint(10, 4000), randint(10, 256)
        test_move(lib, device_ids[name], x, y)
    sleep(2)

for name in device_ids.keys():
    pos[name] = test_get_position(lib, device_ids[name])

print(pos)

for name in device_ids.keys():
    x, y = pos[name]
    #test_move(lib, device_ids[name], x, y)
    #test_wait_for_stop(lib, device_ids[name], 100)


res = lib.close_device(byref(cast(device_id, POINTER(c_int))))

print(res)
