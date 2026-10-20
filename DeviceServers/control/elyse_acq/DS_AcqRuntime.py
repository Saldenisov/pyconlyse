"""Read-only Everest Tango view of the separate Python XP acquisition runtime.

No commands, no initialization and no fallback to simulated or LabVIEW values.
Run separately from DS_AcqTelemetry; its source/schema are deliberately distinct.
"""
import json

import tango
from tango.server import Device, attribute, device_property, run

from DeviceServers.control.elyse_acq.runtime_health import project_runtime_contract
from DeviceServers.control.elyse_acq.runtime_polling import RuntimePollingWorker


class AcqRuntime(Device):
    key_file = device_property(dtype=str)
    xp_port = device_property(dtype=int, default_value=8771)

    def init_device(self):
        if getattr(self, "_reader", None) is not None:
            if not self._reader.stop(3.0):
                raise RuntimeError("Previous runtime reader has not exited")
        super().init_device()
        self._reader = None
        self._init_error = "Waiting for XP runtime"
        self.set_state(tango.DevState.INIT)
        try:
            with open(self.key_file, "rb") as source:
                key = source.read().strip()
            if len(key) < 32:
                raise ValueError("Invalid runtime shared key")
            self._reader = RuntimePollingWorker(key, port=int(self.xp_port))
            self._reader.start()
        except Exception as error:
            self._init_error = type(error).__name__ + ": " + str(error)[:500]
            self.set_state(tango.DevState.FAULT)
            self.set_status(self._init_error)

    def _view(self):
        if self._reader is not None:
            return self._reader.snapshot()
        health = project_runtime_contract(None, None, self._init_error, reader_started=False)
        return dict(source="xp_python_acquisition_runtime", storage_mode="ram_latest",
                    execution_allowed=False, hardware_writes=False, runtime=None,
                    bridge_stale=True, bridge_age_seconds=None, bridge_error=self._init_error,
                    source_current=False, source_stale=True, source_age_seconds=None,
                    quality="UNAVAILABLE", measurements_hidden=True, health=health)

    @attribute(dtype=str)
    def runtime_json(self):
        result = self._view()
        health = result.pop("health")
        self.set_status(health["status"])
        self.set_state(getattr(tango.DevState, health["tango_state"]))
        return json.dumps(result, allow_nan=False)

    def _health(self):
        return self._view()["health"]

    def dev_state(self):
        health = self._health()
        self.set_status(health["status"])
        return getattr(tango.DevState, health["tango_state"])

    def delete_device(self):
        if getattr(self, "_reader", None) is not None:
            if not self._reader.stop(3.0):
                message = "Runtime reader stop timed out; live owner retained; restart refused"
                self.set_status(message)
                self.warn_stream(message)


if __name__ == "__main__":
    run((AcqRuntime,))
