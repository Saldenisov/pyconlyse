"""Host-local discovery cache shared by the Standa Tango processes.

One libximc enumeration probes the complete serial bus and returns every free
controller.  Caching that result briefly lets a group of independently started
Tango servers share the same probe instead of each flooding the USB/COM bus.
The cache is only a discovery hint; opening and serial verification still take
place before an axis is initialised or resumed.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Mapping, Optional


_CACHE_VERSION = 1


def default_cache_path() -> Path:
    configured = os.environ.get("PYCONLYSE_STANDA_DISCOVERY_CACHE", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "pyconlyse" / "standa-discovery.json"


def load_discovery_snapshot(
    max_age_seconds: float,
    *,
    path: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, str]]:
    """Load a fresh serial-to-URI map, or ``None`` for stale/invalid data."""

    cache_path = Path(path) if path is not None else default_cache_path()
    try:
        age = (time.time() if now is None else float(now)) - cache_path.stat().st_mtime
        if age < -5.0 or age > max(0.0, float(max_age_seconds)):
            return None
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("version") != _CACHE_VERSION:
            return None
        devices = payload.get("devices")
        if not isinstance(devices, dict):
            return None
        return {
            str(serial): str(uri)
            for serial, uri in devices.items()
            if str(serial) and isinstance(uri, str) and uri
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def load_discovery_map(
    max_age_seconds: float,
    *,
    path: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, str]:
    """Compatibility wrapper returning an empty map for missing snapshots."""

    return load_discovery_snapshot(
        max_age_seconds, path=path, now=now
    ) or {}


def load_cached_uri(
    serial: object,
    max_age_seconds: float,
    *,
    path: Optional[Path] = None,
) -> Optional[bytes]:
    uri = load_discovery_map(max_age_seconds, path=path).get(str(serial))
    return uri.encode("utf-8") if uri else None


def store_discovery_map(
    devices: Mapping[object, object], *, path: Optional[Path] = None
) -> None:
    """Atomically publish a discovery result while the caller owns probe lock."""

    cache_path = Path(path) if path is not None else default_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {}
    for serial, uri in devices.items():
        if isinstance(uri, bytes):
            uri = uri.decode("utf-8", errors="replace")
        if str(serial) and isinstance(uri, str) and uri:
            normalized[str(serial)] = uri
    payload = {"version": _CACHE_VERSION, "devices": normalized}
    temporary_path = cache_path.with_name(
        f".{cache_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )
        os.replace(str(temporary_path), str(cache_path))
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
