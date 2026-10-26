"""Shared native branch and historical OFF-only chr62000 process adapter.

The prepared server uses ChromaFocalCommand's retained process ownership for
both ON and OFF. This historical wrapper is not its General-OFF process owner.
run_branch retains an OFF default and accepts the reviewed ON/OFF Boolean.

No DLL load/process/device access on import or construction. COM10/11/12 are
saved VI defaults, NOT evidence of current Moxa mapping. Until an operator
verifies that mapping, this adapter fails explicitly; later NI stop stages
still run. Never silently substitute a guessed TCP/SCPI protocol.
"""
import ctypes
import hashlib
import os
import subprocess
from .native_process_spawn import spawn_native_process
import sys
import time


DRIVER_SHA256 = "d581e088f5d4b25796fe2b758fbec21a1ea7f4edb172b2aa7064dd70246677f8"
DEFAULT_DLL = r"C:\Program Files\National Instruments\LabVIEW 2012\instr.lib\chr62000\chr62000.dll"
BRANCHES = ((3, "COM10", 70.0, .02, 15.1),
            (2, "COM11", 80.0, .02, 20.9),
            (1, "COM12", 80.0, .02, 13.73))


def verify_driver(path):
    if not os.path.isabs(path):
        raise ValueError("Absolute Chroma DLL path required")
    with open(path, "rb") as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    if digest != DRIVER_SHA256:
        raise ValueError("Chroma DLL differs from reviewed source copy")


def run_branch(dll, branch, output_enabled=False):
    """One saved Initialize(reset=True)->V->slew->I->Output->Close chain.

    DLL exports/disassembly: stdcall; session uint32, status int32, Boolean
    uint16, setpoints double. Init consumes 16 stack bytes, Close 4, DBL
    setters 12, Output 8. Close-in-finally is an explicit Python safeguard.
    Function is used only in an isolated, time-bounded worker process.
    """
    if type(output_enabled) is not bool:
        raise ValueError("Explicit Boolean Chroma output state required")
    _number, resource, voltage, slew, current = branch
    init = dll.chr62000_init
    init.argtypes = [ctypes.c_char_p, ctypes.c_uint16, ctypes.c_uint16,
                     ctypes.POINTER(ctypes.c_uint32)]
    init.restype = ctypes.c_int32
    close = dll.chr62000_close
    close.argtypes, close.restype = [ctypes.c_uint32], ctypes.c_int32
    session, errors = ctypes.c_uint32(0), []

    def check(name, *args):
        status = getattr(dll, name)(*args)
        if status < 0:
            raise RuntimeError("{0}: status {1}".format(name, status))
        if status > 0:
            # Warnings do not bypass subsequent Output/Close, but must not be
            # silently converted to an unqualified successful stop.
            errors.append("{0}: warning status {1}".format(name, status))

    try:
        check("chr62000_init", resource.encode("ascii"), 0, 1, ctypes.byref(session))
        if not session.value:
            raise RuntimeError("Chroma returned an empty session")
        for name, value in (("chr62000_SetVoltage", voltage),
                            ("chr62000_SetCurrentSlew", slew),
                            ("chr62000_SetCurrent", current)):
            function = getattr(dll, name)
            function.argtypes, function.restype = [ctypes.c_uint32, ctypes.c_double], ctypes.c_int32
            check(name, session.value, value)
        function = dll.chr62000_SetOutput
        function.argtypes, function.restype = [ctypes.c_uint32, ctypes.c_uint16], ctypes.c_int32
        check("chr62000_SetOutput", session.value, int(output_enabled))
    except Exception as error:
        errors.append(str(error))
    finally:
        if session.value:
            try:
                check("chr62000_close", session.value)
            except Exception as error:
                errors.append(str(error))
    if errors:
        raise RuntimeError("; ".join(errors))


class ChromaFocalStop(object):
    def __init__(self, dll_path=DEFAULT_DLL, resources_verified=False, timeout=10):
        if type(resources_verified) is not bool or not 1 <= timeout <= 30:
            raise ValueError("Invalid Chroma stop configuration")
        self.dll_path = dll_path
        self.resources_verified = resources_verified
        self.timeout = timeout

    def ensure_ready(self):
        if not self.resources_verified:
            raise RuntimeError("Focales OFF blocked: verify F3=COM10, F2=COM11, F1=COM12 on XP first")
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 4:
            raise RuntimeError("Chroma requires the existing 32-bit XP Python process")
        verify_driver(self.dll_path)

    def __call__(self):
        self.ensure_ready()
        python = sys.executable
        if os.path.basename(python).lower() == "pythonw.exe":
            python = os.path.join(os.path.dirname(python), "python.exe")
        processes, failures = [], []
        deadline = time.monotonic() + self.timeout
        try:
            for branch in BRANCHES:
                try:
                    process = spawn_native_process(
                        [python, "-m", "elyse_agent.chroma_focal_stop", "--worker",
                         self.dll_path, str(branch[0])],
                        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, creationflags=0x08000000)
                    processes.append((branch[0], process))
                except Exception as error:
                    failures.append("F{0} spawn: {1}".format(branch[0], error))
            for focal, process in processes:
                try:
                    _out, error = process.communicate(timeout=max(.001, deadline - time.monotonic()))
                    if process.returncode:
                        failures.append("F{0}: {1}".format(focal, error.decode("utf-8", "replace")[:1000]))
                except subprocess.TimeoutExpired:
                    failures.append("F{0}: Chroma worker timeout; output state unknown".format(focal))
        finally:
            for focal, process in processes:
                try:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=2)
                except Exception as error:
                    failures.append("F{0} worker cleanup: {1}".format(focal, error))
        if failures:
            raise RuntimeError("; ".join(failures))


def worker(argv):
    if len(argv) != 3 or argv[0] != "--worker" or argv[2] not in ("1", "2", "3"):
        raise ValueError("OFF-only worker arguments required")
    verify_driver(argv[1])
    if ctypes.sizeof(ctypes.c_void_p) != 4 or sys.platform != "win32":
        raise RuntimeError("32-bit Windows required")
    branch = next(row for row in BRANCHES if row[0] == int(argv[2]))
    run_branch(ctypes.WinDLL(argv[1]), branch)


if __name__ == "__main__":
    try:
        worker(sys.argv[1:])
    except Exception as error:
        sys.stderr.write(type(error).__name__ + ": " + str(error) + "\n")
        sys.exit(1)
