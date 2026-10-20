"""Focused actual-Python-3.4 gate: fake NI/processes and loopback only.

Run with the existing XP-compatible interpreter, never a modern substitute.
This script does not install a driver, deploy a server or initialize hardware.
"""
import ctypes
import glob
import ipaddress
import os
import socket
import subprocess
import sys
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


def main():
    if sys.version_info[:2] != (3, 4):
        raise RuntimeError("Actual Python 3.4 required; do not substitute modern Python")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    install_guards()
    folder = os.path.join(root, "legacy", "xp_acq_agent", "tests")
    paths = glob.glob(os.path.join(folder, "test_acquisition*.py"))
    paths += [os.path.join(folder, name) for name in
              ("test_chroma_focal_command.py", "test_runtime_identity.py")]
    names = ["legacy.xp_acq_agent.tests." + os.path.basename(path)[:-3] for path in sorted(set(paths))]
    suite = unittest.TestLoader().loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    loaded = set(sys.modules).intersection(("nidaqmx", "PyDAQmx", "visa", "pyvisa"))
    if loaded:
        raise AssertionError("Driver modules unexpectedly loaded: " + ", ".join(sorted(loaded)))
    print("Actual Python 3.4; external network/native loading denied; no NI/VISA module loaded")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
