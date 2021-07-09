from ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                  controller_name_t, status_t, set_position_t, PositionFlags)
from typing import Dict
from pathlib import Path
from time import sleep
#----- PROTECTED REGION END -----#	//	DS_STANDA_STEP_MOTOR.additionnal_import

# Device States Description
# ON : 
# OFF : 
# MOVING : 
import ctypes

class test_DS_STANDA_STEP_MOTOR():

    def __init__(self):
        self.device_property_list = {}
        self.device_property_list['ip_address'] = '10.20.30.204'
        self.device_property_list["device_id"] = "000043CA"
        self.lib = lib
        self.device_id_internal_seq = -1

    def init_device(self):
        def find_device() -> int:
            self.lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
            # Enumerate devices
            probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
            enum_hints = f"addr={self.device_property_list['ip_address']}".encode('utf-8')
            # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
            devenum = self.lib.enumerate_devices(probe_flags, enum_hints)
            device_counts = self.lib.get_device_count(devenum)
            sleep(0.05)
            argreturn = -1
            if device_counts > 0:
                for device_id_internal_seq in range(device_counts):
                    uri = self.lib.get_device_name(devenum, device_id_internal_seq)
                    sleep(0.01)
                    if self.device_property_list['device_id'] in uri.decode('utf-8'):
                        return device_id_internal_seq
                return argreturn
            else:
                return argreturn

        self.attr_device_id_internal_read = find_device()


    def Off(self):

        arg = ctypes.byref(ctypes.cast(self.attr_device_id_internal_read, ctypes.POINTER(ctypes.c_int)))
        result = self.lib.close_device(arg)

        return result

a = test_DS_STANDA_STEP_MOTOR()
a.init_device()
print(a.attr_device_id_internal_read)
print(a.Off())