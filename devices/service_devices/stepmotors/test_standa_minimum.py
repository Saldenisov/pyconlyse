import os
import platform
import re
import sys
import tempfile
import time
from ctypes import *
from pathlib import Path

if sys.version_info >= (3, 0):
    import urllib.parse

cur_dir = Path(os.path.dirname(__file__))
ximc_dir = Path(cur_dir / "ximc")
sys.path.append(ximc_dir)  # add ximc.py wrapper to python path

if platform.system() == "Windows":
    arch_dir = "win64" if "64" in platform.architecture()[0] else "win32"
    libdir = os.path.join(Path(ximc_dir / arch_dir))
    os.environ["Path"] = libdir + ";" + os.environ["Path"]  # add dll

try:
    from devices.service_devices.stepmotors.ximc import (lib, device_information_t, Result, status_t,
                                                         get_position_t, motor_settings_t, move_settings_t,
                                                         engine_settings_t, MicrostepMode, EnumerateFlags,
                                                         controller_name_t)
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








lib.set_bindy_key(os.path.join(ximc_dir, "win32", "keyfile.sqlite").encode("utf-8"))
probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
enum_hints = b"addr=10.20.30.204"
devenum = lib.enumerate_devices(probe_flags, enum_hints)
dev_count = lib.get_device_count(devenum)
print("Device count: " + repr(dev_count))
uri = lib.get_device_name(devenum, 9)
dev_count = None
devenum = None
device_id = lib.open_device(uri)
print("Device id: " + repr(device_id))

print("\nRead position")
x_pos = get_position_t()
result = lib.get_position(device_id, byref(x_pos))
print("Result: " + repr(result))
if result == Result.Ok:
    print("Position: {0} steps, {1} microsteps".format(x_pos.Position, x_pos.uPosition))

    print("\nGet status")
    x_status = status_t()
    result = lib.get_status(device_id, byref(x_status))
    print("Result: " + repr(result))
    if result == Result.Ok:
        print("Status.Ipwr: " + repr(x_status.Ipwr))
        print("Status.Upwr: " + repr(x_status.Upwr))
        print("Status.Iusb: " + repr(x_status.Iusb))
        print("Status.Flags: " + repr(hex(x_status.Flags)))
print("\nClosing")
a = lib.close_device(byref(cast(device_id, POINTER(c_int))))
print(a)
print("Done")
