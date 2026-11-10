"""Read and verify the local HPD-TA RemoteEx startup files."""
from configparser import ConfigParser
from pathlib import Path

import psutil


def remoteex_process_identity():
    matches = [(proc.info["pid"], proc.info["create_time"])
               for proc in psutil.process_iter(["pid", "name", "create_time"])
               if (proc.info["name"] or "").lower() == "taremoteex.exe"]
    return matches[0] if len(matches) == 1 else None


DEFAULT_REMOTE_INI = r"C:\ProgramData\Hamamatsu\HPDTA\HPDTA8_VD2_RemoteEx.INI"


def _read_profile(path: Path) -> ConfigParser:
    data = path.read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    settings = ConfigParser(interpolation=None)
    settings.read_string(data.decode(encoding))
    return settings


def checked_camera_only_ini(path: str) -> str:
    ini = Path(path)
    if not ini.is_absolute() or ini.suffix.lower() != ".ini":
        raise ValueError("RemoteEx requires an absolute camera-only INI path")
    profile = Path(_read_profile(ini)["Init"]["HWprofile"])
    if not profile.is_absolute() or profile.suffix.lower() != ".hwp":
        raise ValueError("RemoteEx INI requires an absolute hardware profile path")
    devices = _read_profile(profile)["External devices"]
    enabled = tuple(index for index in range(1, 6) if devices.getint(f"UseDeviceType{index}") != 0)
    if enabled != (1,):
        raise ValueError("RemoteEx hardware profile must enable only the streak camera")
    return str(ini)
