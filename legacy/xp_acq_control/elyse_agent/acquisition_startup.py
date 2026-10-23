"""Install a short-lived launcher for ONE cold unified server in user Startup.

No resident Python supervisor, duplicate telemetry app or automatic NI replay.
The unified application owns its own exclusion lock before journal startup.
"""
import ctypes
import os
import sys
import tempfile
import datetime
import uuid


MARKER = "# ELYSE_ACQUISITION_COLD_LAUNCHER_V1"
FILENAME = "ELYSE_Acquisition_Server.pyw"


def startup_directory():
    if sys.platform != "win32":
        raise RuntimeError("Windows Startup folder required")
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 7, None, 0, buffer)
    if result != 0 or not os.path.isdir(buffer.value):
        raise RuntimeError("Cannot resolve current user's Startup folder")
    return buffer.value


def install_startup(entrypoint, config_path, folder=None, interpreter=None):
    entrypoint, config_path = os.path.abspath(entrypoint), os.path.abspath(config_path)
    if os.path.basename(entrypoint) not in ("acquisition_control_server.pyw", "acquisition_server.pyw"):
        raise ValueError("Only the unified Acquisition entrypoint may be installed")
    entrypoint = os.path.join(os.path.dirname(entrypoint), "acquisition_control_server.pyw")
    if (os.path.normcase(os.path.dirname(config_path)) != os.path.normcase(os.path.dirname(entrypoint))
            or os.path.basename(config_path) != "config.acquisition.control.json"):
        raise ValueError("Matching installation-local unified control configuration required")
    interpreter = interpreter or os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not all(os.path.isfile(path) for path in (entrypoint, config_path, interpreter)):
        raise ValueError("Installed unified entrypoint/config/pythonw.exe must exist")
    folder = folder or startup_directory()
    target = os.path.join(folder, FILENAME)
    if os.path.exists(target):
        with open(target, "rb") as source:
            original = source.read(32769)
            if len(original) > 32768 or not original.decode("utf-8").startswith(MARKER):
                raise ValueError("Refusing to overwrite an unrelated Startup file")
        backup = target + ".backup_" + datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        with open(backup, "xb") as preserved:
            preserved.write(original)
            preserved.flush()
            os.fsync(preserved.fileno())
    # Updating this file is only an explicit GUI button operation. It does not
    # execute the child, shell, network or any card operation here. The launcher
    # exits after Popen: no persistent supervisor Python process competes with
    # the explicit local handover inventory check.
    arguments = [interpreter, entrypoint, "--config", config_path]
    source = (MARKER + "\n# coding: utf-8\n# ONE_UNIFIED_SERVER_V3\nimport subprocess\n"
              "subprocess.Popen({0!r}, cwd={1!r}, shell=False, close_fds=True)\n").format(
                  arguments, os.path.dirname(entrypoint))
    descriptor, temporary = tempfile.mkstemp(prefix=".elyse-acq-", suffix=".pyw", dir=folder)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(source)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return target
