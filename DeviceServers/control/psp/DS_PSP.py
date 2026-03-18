#!/usr/bin/env python
"""
Minimal Tango Device Server to receive string payloads from external sender
(e.g. LabVIEW bridge or any Python client).

Target device name:
    manip/general/PSP

Main command:
    receive(str_payload) -> "OK"
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, Union

from tango import AttrWriteType, DevState
from tango.server import attribute, command

# Add pyconlyse root to import path when started directly.
_PYCONLYSE_ROOT = Path(__file__).resolve().parents[3]
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    from DeviceServers.base.general import DS_General


class DS_PSP(DS_General):
    """Simple receiver DS: accepts string payload via receive command."""

    _version_ = "1.0"
    _model_ = "PSP String Receiver"
    polling = 500

    def init_device(self):
        self._last_payload = ""
        self._last_timestamp = 0.0
        self._messages_received = 0
        self._last_sender = ""
        self._last_error = ""
        super().init_device()
        self.turn_on()

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "psp://receiver"
        return 1, self._uri

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    @attribute(
        label="Last Payload",
        dtype=str,
        access=AttrWriteType.READ,
        doc="Last received string payload",
    )
    def last_payload(self):
        return self._last_payload

    @attribute(
        label="Last Timestamp",
        dtype=float,
        access=AttrWriteType.READ,
        doc="Unix timestamp of the last received payload",
    )
    def last_timestamp(self):
        return float(self._last_timestamp)

    @attribute(
        label="Messages Received",
        dtype=int,
        access=AttrWriteType.READ,
        doc="Total number of received payloads",
    )
    def messages_received(self):
        return int(self._messages_received)

    @attribute(
        label="Last Sender",
        dtype=str,
        access=AttrWriteType.READ_WRITE,
        doc="Optional sender identifier (set by client).",
    )
    def last_sender(self):
        return self._last_sender

    def write_last_sender(self, value):
        self._last_sender = str(value)

    @attribute(
        label="Last Payload JSON",
        dtype=str,
        access=AttrWriteType.READ,
        doc="JSON wrapper around last payload and metadata.",
    )
    def last_payload_json(self):
        payload: Dict[str, object] = {
            "payload": self._last_payload,
            "timestamp": self._last_timestamp,
            "messages_received": self._messages_received,
            "sender": self._last_sender,
            "error": self._last_error,
        }
        return json.dumps(payload, ensure_ascii=False)

    @command(dtype_in=str, dtype_out=str, doc_in="String payload", doc_out="OK")
    def receive(self, payload: str):
        """Receive raw string payload and store as latest message."""
        try:
            self._last_payload = str(payload)
            self._last_timestamp = time.time()
            self._messages_received += 1
            self._last_error = ""
            return "OK"
        except Exception as exc:
            self._last_error = str(exc)
            self.error(f"receive failed: {exc}")
            return f"ERROR: {exc}"


if __name__ == "__main__":
    DS_PSP.run_server()
