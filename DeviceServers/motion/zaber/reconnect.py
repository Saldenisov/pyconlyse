"""Passive retry loop for a Zaber controller whose supply may be off at boot."""

from __future__ import annotations

import threading
from typing import Callable


class ZaberConnectionMonitor:
    """Read status and reopen the serial connection without moving the stage."""

    def __init__(
        self,
        stage,
        lock: threading.RLock,
        is_moving: Callable[[], bool],
        on_snapshot: Callable,
        on_error: Callable[[Exception], None],
        interval_s: float = 5.0,
    ) -> None:
        self.stage = stage
        self.lock = lock
        self.is_moving = is_moving
        self.on_snapshot = on_snapshot
        self.on_error = on_error
        self.interval_s = max(0.1, float(interval_s))
        self._stop = threading.Event()
        self._thread = None

    def probe_once(self) -> None:
        with self.lock:
            if self.is_moving():
                return
            try:
                snapshot = self.stage.snapshot() if self.stage.connected else self.stage.connect()
            except Exception as exc:
                try:
                    self.stage.close()
                except Exception:
                    pass
                self.on_error(exc)
                return
            self.on_snapshot(snapshot)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="zaber-connection", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.probe_once()

    def stop(self) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            return not self._thread.is_alive()
        return True
