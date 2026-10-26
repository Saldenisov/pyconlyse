"""Serialize Windows3.4 temporary inheritable stdio handle construction only.

Initialization, native calls and telemetry remain concurrent. Holding this
lock across any process wait/read would defeat card isolation. Import is cold.
"""
import subprocess
import threading

_SPAWN_LOCK = threading.Lock()


def spawn_native_process(arguments, **options):
    with _SPAWN_LOCK:
        return subprocess.Popen(arguments, **options)
