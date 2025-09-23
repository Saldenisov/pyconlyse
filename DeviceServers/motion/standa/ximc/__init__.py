import platform
from os import path
from pathlib import Path

ximc_dir = Path(path.dirname(__file__))

if platform.system() == "Windows":
    arch_type = "win64" if "64" in platform.architecture()[0] else "win32"
    if arch_type == "win64":
        path_dll = ximc_dir / "win64" / "libximc.dll"
    elif arch_type == "win32":
        path_dll = ximc_dir / "win32" / "libximc.dll"
elif platform.system() == "Linux":
    arch_type = "win64"
    path_dll = Path("/usr/lib/")

else:
    raise Exception("Only Windows/Linux is available at this moment")

try:
    # Prefer relative import in the reorganized package
    from .myximc import *  # type: ignore
except Exception:
    # During unit test discovery or environments without the native library,
    # avoid raising so that importers can proceed without using ximc APIs.
    pass
