from __future__ import annotations

import os
from pathlib import Path


def _normalize_dll_root(path_value: str) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""

    path = Path(raw)
    if path.is_file():
        return str(path.parent)
    return str(path)


def configure_andor_dll_paths(
    sdk_path: str = "",
    shamrock_path: str = "",
):
    try:
        import pylablib as pll
    except ImportError as exc:  # pragma: no cover - depends on deployment env
        raise RuntimeError(
            "pylablib is not installed. Install it in the PYCONLYSE environment "
            "before starting the Andor Tango device servers."
        ) from exc

    if os.name != "nt":
        pll.par["devices/only_windows_dlls"] = False

    sdk_root = _normalize_dll_root(sdk_path)
    shamrock_root = _normalize_dll_root(shamrock_path)

    if sdk_root:
        pll.par["devices/dlls/andor_sdk2"] = sdk_root
    if shamrock_root:
        pll.par["devices/dlls/andor_shamrock"] = shamrock_root

    return pll


def get_andor_module(
    sdk_path: str = "",
    shamrock_path: str = "",
):
    configure_andor_dll_paths(sdk_path=sdk_path, shamrock_path=shamrock_path)
    from pylablib.devices import Andor

    return Andor

