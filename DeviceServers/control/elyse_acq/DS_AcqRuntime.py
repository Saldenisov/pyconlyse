"""Read-only Everest Tango view of the separate Python XP acquisition runtime.

No commands, no initialization and no fallback to simulated or LabVIEW values.
Run separately from DS_AcqTelemetry; its source/schema are deliberately distinct.
"""
import json
import threading
import time

import tango
from tango.server import Device, attribute, device_property, run

from DeviceServers.control.elyse_acq.runtime_client import read_runtime


class AcqRuntime(Device):
    key_file = device_property(dtype=str)
    xp_port = device_property(dtype=int, default_value=8771)

    def init_device(self):
        if getattr(self, "_worker", None) is not None:
            self.delete_device()
            if self._worker.is_alive():
                raise RuntimeError("Previous runtime reader has not exited")
        super().init_device()
        self._cache_lock = threading.RLock()
        self._stop = threading.Event()
        self._latest = None
        self._last_read = None
        self._last_error = "Waiting for XP runtime"
        self._worker = None
        self.set_state(tango.DevState.INIT)
        try:
            with open(self.key_file, "rb") as source:
                self._key = source.read().strip()
            if len(self._key) < 32:
                raise ValueError("Invalid runtime shared key")
            self._worker = threading.Thread(target=self._poll, daemon=True)
            self._worker.start()
        except Exception as error:
            self._last_error = str(error)
            self.set_state(tango.DevState.FAULT)
            self.set_status(self._last_error)

    def _poll(self):
        while not self._stop.is_set():
            try:
                value = read_runtime(self._key, port=int(self.xp_port))
                with self._cache_lock:
                    self._latest, self._last_read, self._last_error = value, time.monotonic(), ""
            except Exception as error:
                with self._cache_lock:
                    self._last_error = str(error)
            self._stop.wait(1.0)

    @attribute(dtype=str)
    def runtime_json(self):
        with self._cache_lock:
            age = None if self._last_read is None else time.monotonic() - self._last_read
            value = self._latest
            stale = bool(self._last_error) or age is None or age > 3
            result = dict(source="xp_python_acquisition_runtime", storage_mode="ram_latest",
                          bridge_stale=stale, bridge_age_seconds=age,
                          bridge_error=self._last_error, runtime=value)
        self.set_state(self.dev_state())
        return json.dumps(result, allow_nan=False)

    def dev_state(self):
        with self._cache_lock:
            if self._worker is None:
                self.set_status(self._last_error)
                return tango.DevState.FAULT
            if (self._last_error or self._last_read is None
                    or time.monotonic() - self._last_read > 3):
                self.set_status("No current authenticated XP runtime snapshot: " + self._last_error)
                return tango.DevState.UNKNOWN
            state = self._latest["state"]
            self.set_status("XP runtime: " + state + "; no remote controls enabled")
            return (tango.DevState.FAULT if state == "FAULT" else
                    tango.DevState.RUNNING if state in ("RUNNING", "EXECUTING") else tango.DevState.STANDBY)

    def delete_device(self):
        if hasattr(self, "_stop"):
            self._stop.set()
        if getattr(self, "_worker", None) is not None:
            self._worker.join(3.0)


if __name__ == "__main__":
    run((AcqRuntime,))
