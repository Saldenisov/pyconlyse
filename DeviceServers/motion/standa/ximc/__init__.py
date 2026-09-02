import platform
import os
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

XIMC_BACKEND = "unavailable"
XIMC_BACKEND_ERROR = ""

# The maintained PyPI package contains the current vendor DLL, dependencies,
# and generated Python structures. Keep the bundled 2018 binding only as a
# controlled fallback while Elysium2 is migrated.
_backend_choice = os.environ.get("PYCONLYSE_LIBXIMC_BACKEND", "official").strip().lower()
if _backend_choice not in {"official", "bundled"}:
    raise RuntimeError(
        "PYCONLYSE_LIBXIMC_BACKEND must be 'official' or 'bundled'"
    )

if _backend_choice == "official":
    try:
        from libximc import *  # type: ignore  # noqa: F403

        XIMC_BACKEND = "official-pypi"
    except Exception as error:
        XIMC_BACKEND_ERROR = str(error)

if XIMC_BACKEND == "unavailable":
    try:
        from .myximc import *  # type: ignore  # noqa: F403

        XIMC_BACKEND = "bundled-legacy"
    except Exception as error:
        XIMC_BACKEND_ERROR = str(error)


def runtime_version() -> str:
    """Return the loaded vendor library version without touching hardware."""

    try:
        import ctypes

        buffer = ctypes.create_string_buffer(64)
        lib.ximc_version(buffer)  # type: ignore[name-defined]  # noqa: F405
        return buffer.value.decode("ascii", errors="replace")
    except Exception:
        return "unknown"
