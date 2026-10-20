"""Focused actual-Python-3.4 gate: fake NI/processes and loopback only.

Run with the existing XP-compatible interpreter, never a modern substitute.
This script does not install a driver, deploy a server or initialize hardware.
"""
import ctypes
from contextlib import contextmanager
from enum import Enum
import glob
import ipaddress
import os
import socket
import subprocess
import sys
import types
import unittest


def denied_native(*args, **kwargs):
    raise AssertionError("Native library loading forbidden in software gate")


def denied_process(*args, **kwargs):
    raise AssertionError("Real child processes forbidden in focused software gate")


def local(host):
    if isinstance(host, bytes):
        host = host.decode("ascii")
    host = str(host or "").strip("[]")
    if host in ("", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def install_guards():
    ctypes._dlopen = denied_native
    ctypes.CDLL = denied_native
    if hasattr(ctypes, "WinDLL"):
        ctypes.WinDLL = denied_native
    ctypes.cdll.LoadLibrary = denied_native
    if hasattr(ctypes, "windll"):
        ctypes.windll.LoadLibrary = denied_native
    subprocess.Popen = denied_process
    getaddrinfo = socket.getaddrinfo
    connect, connect_ex, bind = socket.socket.connect, socket.socket.connect_ex, socket.socket.bind
    create_connection, sendto = socket.create_connection, socket.socket.sendto
    gethostbyname, gethostbyname_ex = socket.gethostbyname, socket.gethostbyname_ex

    def check(address):
        host = address[0] if isinstance(address, tuple) else address
        if not local(host):
            raise AssertionError("External network forbidden in software gate")

    def guarded_dns(host, *args, **kwargs):
        check(host)
        return getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock, address):
        check(address)
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        check(address)
        return connect_ex(sock, address)

    def guarded_bind(sock, address):
        check(address)
        return bind(sock, address)

    def guarded_create_connection(address, *args, **kwargs):
        check(address)
        return create_connection(address, *args, **kwargs)

    def guarded_sendto(sock, data, *args):
        check(args[-1])
        return sendto(sock, data, *args)

    def guarded_lookup(host):
        check(host)
        return gethostbyname(host)

    def guarded_lookup_ex(host):
        check(host)
        return gethostbyname_ex(host)

    socket.getaddrinfo = guarded_dns
    socket.create_connection = guarded_create_connection
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.bind = guarded_bind
    socket.socket.sendto = guarded_sendto
    socket.gethostbyname = guarded_lookup
    socket.gethostbyname_ex = guarded_lookup_ex


def assert_no_driver_modules():
    roots = ("nidaqmx", "PyDAQmx", "visa", "pyvisa")
    loaded = sorted(name for name in sys.modules
                    if any(name == root or name.startswith(root + ".") for root in roots))
    if loaded:
        raise AssertionError("Driver modules unexpectedly retained: " + ", ".join(loaded))


def reviewed_fake_constants():
    """Narrow pure-source fixture; never import the installed vendor package.

    Values transcribed from reviewed nidaqmx==0.5.7 constants.py, SHA256:
    C8C32A3EA38AC18C0656007F45090FF8891ED8EE6A7B37699D6CC1D4B3550DD8.
    Local review source: tools/xp_python34_testenv/Lib/site-packages/nidaqmx/
    constants.py. That ignored SDK copy is not a clean-checkout dependency.
    These six enum subsets are all hardware_tasks' fake task builder needs;
    no Task, library loader, DAQ API or fallback module is provided.
    """
    module = types.ModuleType("nidaqmx.constants")
    subsets = {
        "AcquisitionType": {"FINITE": 10178},
        "Edge": {"RISING": 10280, "FALLING": 10171},
        "Level": {"LOW": 10214},
        "LineGrouping": {"CHAN_PER_LINE": 0},
        "TerminalConfiguration": {"RSE": 10083},
        "ReadRelativeTo": {"CURRENT_READ_POSITION": 10425},
    }
    for name, members in subsets.items():
        setattr(module, name, Enum(name, members))
    return module


@contextmanager
def fake_constants_scope(constants):
    # Refuse to overwrite a real/already loaded driver or another shim.
    assert_no_driver_modules()
    package = types.ModuleType("nidaqmx")
    package.__path__ = []
    package.constants = constants
    entries = {"nidaqmx": package, "nidaqmx.constants": constants}
    sys.modules.update(entries)
    try:
        yield
    finally:
        replaced = []
        for name, expected in entries.items():
            if sys.modules.get(name) is expected:
                del sys.modules[name]
            else:
                replaced.append(name)
        assert_no_driver_modules()
        if replaced:
            raise AssertionError("Fake constants module unexpectedly replaced: " + ", ".join(replaced))


class FakeHardwareSuite(unittest.TestSuite):
    """Scope the constants-only shim to the twelve fake low-level tests."""
    def __init__(self):
        self.constants = reviewed_fake_constants()
        with fake_constants_scope(self.constants):
            suite = unittest.TestLoader().loadTestsFromName(
                "legacy.xp_acq_agent.tests.test_hardware_tasks")
        unittest.TestSuite.__init__(self, (suite,))

    def run(self, result, debug=False):
        with fake_constants_scope(self.constants):
            return unittest.TestSuite.run(self, result, debug)


def main():
    if sys.version_info[:2] != (3, 4):
        raise RuntimeError("Actual Python 3.4 required; do not substitute modern Python")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    # The historical low-level tests use elyse_agent.*, whereas the runtime
    # suite uses the namespace-qualified legacy.xp_acq_agent.elyse_agent.*.
    sys.path.insert(0, os.path.join(root, "legacy", "xp_acq_agent"))
    install_guards()
    folder = os.path.join(root, "legacy", "xp_acq_agent", "tests")
    paths = glob.glob(os.path.join(folder, "test_acquisition*.py"))
    paths += [os.path.join(folder, name) for name in
              ("test_chroma_focal_command.py", "test_runtime_identity.py")]
    names = ["legacy.xp_acq_agent.tests." + os.path.basename(path)[:-3] for path in sorted(set(paths))]
    suite = unittest.TestLoader().loadTestsFromNames(names)
    suite.addTest(FakeHardwareSuite())
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    assert_no_driver_modules()
    print("Actual Python 3.4; external network/native/process loading denied; "
          "hardware fake uses reviewed enum-only shim; no NI/VISA module retained")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
