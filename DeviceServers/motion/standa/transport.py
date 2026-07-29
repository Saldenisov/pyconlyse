"""Cross-process serialization for the shared Standa USB transport."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


class StandaTransportBusyError(RuntimeError):
    """Raised when another Standa server currently owns the USB transport."""


_LOCAL_LOCK = threading.RLock()


def default_lock_path() -> Path:
    configured = os.environ.get("PYCONLYSE_STANDA_TRANSPORT_LOCK", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "pyconlyse" / "standa-ximc.lock"


def _try_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_standa_transport(
    path: Optional[str] = None,
    timeout_seconds: float = 1.0,
    retry_seconds: float = 0.05,
) -> Iterator[None]:
    """Serialize libximc calls across Tango server processes on one host."""

    lock_path = Path(path) if path else default_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))

    local_timeout = max(0.0, deadline - time.monotonic())
    if not _LOCAL_LOCK.acquire(timeout=local_timeout):
        raise StandaTransportBusyError(
            f"Standa USB transport is busy for {timeout_seconds:.1f}s"
        )
    try:
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()

            while True:
                try:
                    _try_lock(handle)
                    break
                except OSError as error:
                    if time.monotonic() >= deadline:
                        raise StandaTransportBusyError(
                            f"Standa USB transport is busy for {timeout_seconds:.1f}s"
                        ) from error
                    time.sleep(max(0.01, float(retry_seconds)))

            try:
                yield
            finally:
                _unlock(handle)
    finally:
        _LOCAL_LOCK.release()
