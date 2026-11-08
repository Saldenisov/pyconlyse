"""Install only this application's cold launcher in current user's Startup."""
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
    if not all(os.path.isfile(path) for path in (entrypoint, config_path, interpreter)):
        raise ValueError("Installed entrypoint/config/pythonw.exe must exist")
    folder = folder or startup_directory()
    target = os.path.join(folder, FILENAME)
    if os.path.exists(target):
        with open(target, "r") as source:
            if not source.read().startswith(MARKER):
                raise ValueError("Refusing to overwrite an unrelated Startup file")
    # No shell/cmd, installation, network operation or card initialization.
    source = (MARKER + "\nimport subprocess\nsubprocess.Popen({0!r}, cwd={1!r})\n").format(
        [interpreter, entrypoint, "--config", config_path], os.path.dirname(entrypoint))
    descriptor, temporary = tempfile.mkstemp(prefix=".elyse-acq-", suffix=".pyw", dir=folder)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(source)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return target
