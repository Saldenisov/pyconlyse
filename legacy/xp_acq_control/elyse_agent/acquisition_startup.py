"""Explicitly install this application's cold supervisor in user Startup."""
import ctypes
import os
import sys
import tempfile


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
    interpreter = interpreter or os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    supervisor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acquisition_supervisor.py")
    if not all(os.path.isfile(path) for path in (entrypoint, config_path, interpreter, supervisor)):
        raise ValueError("Installed entrypoint/config/pythonw.exe/supervisor must exist")
    folder = folder or startup_directory()
    target = os.path.join(folder, FILENAME)
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as source:
            if not source.read().startswith(MARKER):
                raise ValueError("Refusing to overwrite an unrelated Startup file")
    # Updating this file is only an explicit GUI button operation. It does not
    # execute the supervisor, child, shell, network or any card operation here.
    arguments = [interpreter, supervisor, "--interpreter", interpreter,
                 "--entrypoint", entrypoint, "--config", config_path]
    source = (MARKER + "\n# coding: utf-8\n# COLD_SUPERVISOR_V2\nimport subprocess\n"
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
