"""Direct access to the installed C13410 through its Windows HPK driver."""

import ctypes
from ctypes import wintypes

from DeviceServers.instruments.dg645.vd2_timing import timing_for_range


DEVICE_PATH = r"\\?\USB#VID_0661&PID_0812#1.000#{bb509ad0-6adc-4800-9f3f-7f0363102e38}"
WRITE_COMMAND = 0x8000000C
READ_RESPONSE = 0x80000010


class C13410Usb:
    """One exclusive, synchronous command/response session for the VD2 streak head."""

    def __init__(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                           wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        create.restype = wintypes.HANDLE
        self._io = kernel.DeviceIoControl
        self._io.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                             wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                             wintypes.LPVOID)
        self._io.restype = wintypes.BOOL
        self._close = kernel.CloseHandle
        self._close.argtypes = (wintypes.HANDLE,)
        self._close.restype = wintypes.BOOL
        self._handle = create(DEVICE_PATH, 0xC0000000, 0, None, 3, 0, None)
        if self._handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self._handle is not None:
            if not self._close(self._handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self._handle = None

    def _command(self, command):
        payload = command.encode("ascii") + b"\0"
        sent = ctypes.create_string_buffer(payload)
        count = wintypes.DWORD()
        if not self._io(self._handle, WRITE_COMMAND, sent, len(payload), None, 0, ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value != len(payload):
            raise RuntimeError(f"C13410 accepted only {count.value} bytes of {command!r}")
        received = ctypes.create_string_buffer(256)
        if not self._io(self._handle, READ_RESPONSE, None, 0, received, len(received),
                        ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return received.raw[:count.value].rstrip(b"\0\r\n").decode("ascii", errors="strict")

    def read(self, register):
        reply = self._command(f"?{register}")
        if not reply.startswith("OK:"):
            raise RuntimeError(f"C13410 ?{register} returned {reply!r}")
        return reply[3:]

    def write(self, command):
        reply = self._command(command)
        if reply != "OK":
            raise RuntimeError(f"C13410 {command} returned {reply!r}")

    def rearm(self):
        self.write("VRT")


def configure_synchronized_sweep(head, time_range, *, accept_open=False):
    """Changes to the sweep still require a closed shutter."""
    profile = timing_for_range(time_range)
    head.read("ALL")
    shutter = head.read("SHT")
    if shutter != "SHT C" and not (accept_open and shutter == "SHT O"):
        raise RuntimeError("C13410 requires a closed shutter to configure the sweep")
    safe = {"MCP": "MCP 0", "GMD": "GMD N",
            "VTM": "VTM S", "VTS": "VTS P", "VTL": "VTL 1.0V"}
    for register, desired in safe.items():
        actual = head.read(register)
        if actual != desired:
            raise RuntimeError(f"C13410 ?{register}: expected {desired}, read {actual}")
    sweep = profile.time_range.replace(" ", "").upper()
    for register, desired in (("OPE", "OPE"), ("VSR", f"VSR {sweep}")):
        if head.read(register) != desired:
            if shutter != "SHT C":
                raise RuntimeError("Close the streak shutter before changing the sweep")
            head.write(desired)
            if head.read(register) != desired:
                raise RuntimeError(f"C13410 did not verify {desired}")
    return profile.time_range
