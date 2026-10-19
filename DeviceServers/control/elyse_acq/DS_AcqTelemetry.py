"""Read-only Tango facade for XP telemetry; no hardware/PSP control paths."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tango import DevState
from tango.server import Device, attribute, device_property, run
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkServer, TelemetrySinkStore


class DS_AcqTelemetry(Device):
    listen_host = device_property(dtype=str, default_value="10.20.30.202")
    listen_port = device_property(dtype=int, default_value=8767)
    key_file = device_property(dtype=str, default_value="")
    permitted_xp_host = device_property(dtype=str, default_value="10.20.30.10")
    producer_kind_filter = device_property(dtype=str, default_value="")

    def init_device(self):
        if getattr(self, '_server', None) is not None:
            self.delete_device()
        self._server = self._store = self._thread = None
        super().init_device()
        if not self.key_file:
            self.set_state(DevState.FAULT)
            self.set_status("Not listening: configure key_file; RAM-only telemetry, no database.")
            return
        try:
            if self.listen_host not in ("10.20.30.202", "127.0.0.1"):
                raise ValueError("explicit Everest address required; wildcard disabled")
            key = Path(self.key_file).read_bytes().strip()
            self._store = TelemetrySinkStore(key, permitted_producer_kind=self.producer_kind_filter or None)
            self._server = TelemetrySinkServer((self.listen_host, self.listen_port), self._store,
                                              permitted_peers=(self.permitted_xp_host,))
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            kwargs={"poll_interval": 0.1}, daemon=True)
            self._thread.start()
            self.set_state(DevState.ON)
            self.set_status("Receive-only telemetry; latest values in RAM, no SQLite or archive writes. "
                            "Values reset on restart. No NI/PSP tasks or hardware commands.")
        except Exception as error:
            self.delete_device()
            self.set_state(DevState.FAULT)
            self.set_status(str(error))

    @attribute(dtype=str)
    def telemetry_json(self):
        if self._store is None:
            return json.dumps(dict(available=False, hardware_writes=False))
        return json.dumps(self._store.snapshot(), allow_nan=False)

    @attribute(dtype=int)
    def received_messages(self):
        return 0 if self._store is None else self._store.snapshot()["received_this_process"]

    def delete_device(self):
        if self._server is not None:
            if self._thread is not None:
                self._server.shutdown()
                self._thread.join(3)
            self._server.server_close()
            self._server = None
        if self._store is not None:
            self._store.close()
            self._store = None
        self._thread = None


if __name__ == "__main__":
    run((DS_AcqTelemetry,))
