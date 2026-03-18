#!/usr/bin/env python
"""PSP Tango receiver with FIFO history grouped by subsystem."""

import json
import sys
import threading
import time
from collections import deque
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
    """PSP receiver DS: stores latest payload and grouped FIFO history."""

    _version_ = "1.1"
    _model_ = "PSP String Receiver"
    polling = 500
    _DEFAULT_FIFO_SIZE = 5000
    _KNOWN_GROUPS = (
        "timestamp",
        "cooling",
        "hf",
        "ht",
        "modulator",
        "vacuum",
        "magnets",
        "other",
    )

    def init_device(self):
        self._lock = threading.RLock()
        self._last_payload = ""
        self._last_timestamp = 0.0
        self._messages_received = 0
        self._last_sender = ""
        self._last_error = ""
        self._fifo_size = self._read_fifo_size_property()
        self._fifo_all = deque(maxlen=self._fifo_size)
        self._fifo_by_group = {
            group_name: deque(maxlen=self._fifo_size) for group_name in self._KNOWN_GROUPS
        }
        self._latest_by_channel = {}
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

    def _read_fifo_size_property(self) -> int:
        fallback = self._DEFAULT_FIFO_SIZE
        try:
            props = self.get_device_properties("fifo_size")
            raw = props.get("fifo_size")
            if isinstance(raw, list) and raw:
                value = int(float(raw[0]))
                return max(1000, value)
            if raw not in (None, ""):
                value = int(float(raw))
                return max(1000, value)
        except Exception:
            pass
        return fallback

    @staticmethod
    def _safe_float(value, default=None):
        try:
            return float(str(value))
        except Exception:
            return default

    @classmethod
    def _normalize_group_name(cls, group_name: str) -> str:
        normalized = str(group_name or "").strip().lower()
        aliases = {
            "high_tension": "ht",
            "hightension": "ht",
            "magnet": "magnets",
            "time": "timestamp",
        }
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in cls._KNOWN_GROUPS else "other"

    @classmethod
    def _parse_payload(cls, payload: str):
        raw = str(payload or "").strip()
        if not raw:
            return {
                "channel": "",
                "group": "other",
                "value_raw": "",
                "value": "",
                "source_ts": None,
            }

        first_colon = raw.find(":")
        second_colon = raw.find(":", first_colon + 1) if first_colon >= 0 else -1

        if first_colon < 0:
            channel = raw
            value_raw = ""
            source_ts = None
        elif second_colon < 0:
            channel = raw[:first_colon]
            value_raw = raw[first_colon + 1 :]
            source_ts = None
        else:
            channel = raw[:first_colon]
            value_raw = raw[first_colon + 1 : second_colon]
            source_ts = cls._safe_float(raw[second_colon + 1 :], None)

        parts = [part for part in str(channel).split("/") if part]
        group_raw = parts[1].lower() if len(parts) >= 2 else ""
        group = cls._normalize_group_name(group_raw)

        numeric_value = cls._safe_float(value_raw, None)
        value = numeric_value if numeric_value is not None else value_raw

        return {
            "channel": str(channel),
            "group": group,
            "value_raw": str(value_raw),
            "value": value,
            "source_ts": source_ts,
        }

    def _build_message(self, payload: str, recv_ts: float):
        parsed = self._parse_payload(payload)
        return {
            "id": int(self._messages_received),
            "payload": str(payload),
            "recv_ts": float(recv_ts),
            "channel": parsed["channel"],
            "group": parsed["group"],
            "value_raw": parsed["value_raw"],
            "value": parsed["value"],
            "source_ts": parsed["source_ts"],
        }

    def _snapshot_group_counts(self):
        with self._lock:
            return {group: len(queue) for group, queue in self._fifo_by_group.items()}

    def _resize_fifos(self, new_size: int):
        with self._lock:
            old_all = list(self._fifo_all)
            old_by_group = {group: list(queue) for group, queue in self._fifo_by_group.items()}
            self._fifo_size = int(max(1000, new_size))
            self._fifo_all = deque(old_all[-self._fifo_size :], maxlen=self._fifo_size)
            self._fifo_by_group = {}
            for group_name in self._KNOWN_GROUPS:
                items = old_by_group.get(group_name, [])
                self._fifo_by_group[group_name] = deque(
                    items[-self._fifo_size :], maxlen=self._fifo_size
                )

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
        label="FIFO Size",
        dtype=int,
        access=AttrWriteType.READ_WRITE,
        doc="Max messages kept per FIFO queue (all + each group).",
    )
    def fifo_size(self):
        return int(self._fifo_size)

    def write_fifo_size(self, value):
        self._resize_fifos(int(value))

    @attribute(
        label="FIFO Total Cached",
        dtype=int,
        access=AttrWriteType.READ,
        doc="Current number of cached messages in global FIFO.",
    )
    def fifo_total_cached(self):
        with self._lock:
            return int(len(self._fifo_all))

    @attribute(
        label="Group Counts JSON",
        dtype=str,
        access=AttrWriteType.READ,
        doc="Current cached message counts per group.",
    )
    def group_counts_json(self):
        return json.dumps(self._snapshot_group_counts(), ensure_ascii=False)

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
            "fifo_total_cached": len(self._fifo_all),
            "fifo_size": self._fifo_size,
            "group_counts": self._snapshot_group_counts(),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parse_group_query(self, query: str):
        group = "other"
        seconds = 0.0
        limit = 0
        raw = str(query or "").strip()
        if not raw:
            return group, seconds, limit

        parts = [part.strip() for part in raw.split("|")]
        group = self._normalize_group_name(parts[0] if parts else "")
        if len(parts) >= 2:
            seconds = max(0.0, self._safe_float(parts[1], 0.0) or 0.0)
        if len(parts) >= 3:
            try:
                limit = max(0, int(float(parts[2])))
            except Exception:
                limit = 0
        return group, seconds, limit

    @command(dtype_in=str, dtype_out=str, doc_in="String payload", doc_out="OK")
    def receive(self, payload: str):
        """Receive raw string payload and store latest + FIFO entries."""
        try:
            with self._lock:
                self._last_payload = str(payload)
                self._last_timestamp = time.time()
                self._messages_received += 1

                message = self._build_message(self._last_payload, self._last_timestamp)
                self._fifo_all.append(message)
                group_queue = self._fifo_by_group.get(message["group"])
                if group_queue is None:
                    group_queue = self._fifo_by_group["other"]
                group_queue.append(message)

                channel_name = str(message.get("channel") or "")
                if channel_name:
                    self._latest_by_channel[channel_name] = message

                self._last_error = ""
            return "OK"
        except Exception as exc:
            self._last_error = str(exc)
            self.error(f"receive failed: {exc}")
            return f"ERROR: {exc}"

    @command(dtype_out=str)
    def get_groups_json(self):
        with self._lock:
            payload = {
                "groups": list(self._KNOWN_GROUPS),
                "counts": self._snapshot_group_counts(),
                "fifo_size": self._fifo_size,
                "messages_received": self._messages_received,
            }
        return json.dumps(payload, ensure_ascii=False)

    @command(dtype_in=str, dtype_out=str)
    def get_group_history_json(self, query: str):
        group, seconds, limit = self._parse_group_query(query)
        now_ts = time.time()

        with self._lock:
            samples = list(self._fifo_by_group.get(group, []))
        if seconds > 0:
            min_ts = now_ts - seconds
            samples = [entry for entry in samples if float(entry.get("recv_ts", 0.0)) >= min_ts]
        if limit > 0:
            samples = samples[-limit:]

        payload = {
            "group": group,
            "seconds": seconds,
            "limit": limit,
            "sample_count": len(samples),
            "history": samples,
        }
        return json.dumps(payload, ensure_ascii=False)

    @command(dtype_in=float, dtype_out=str)
    def get_history_json(self, seconds: float):
        span_s = max(0.0, float(seconds))
        now_ts = time.time()
        with self._lock:
            samples = list(self._fifo_all)
        if span_s > 0:
            min_ts = now_ts - span_s
            samples = [entry for entry in samples if float(entry.get("recv_ts", 0.0)) >= min_ts]
        return json.dumps(samples, ensure_ascii=False)

    @command(dtype_out=str)
    def get_latest_values_json(self):
        with self._lock:
            latest_data = {}
            for channel_name, message in self._latest_by_channel.items():
                latest_data[channel_name] = message.get("value")
            payload = {
                "timestamp": self._last_timestamp,
                "messages_received": self._messages_received,
                "fifo_size": self._fifo_size,
                "cached": len(self._fifo_all),
                "group_counts": self._snapshot_group_counts(),
                "data": latest_data,
            }
        return json.dumps(payload, ensure_ascii=False)

    @command(dtype_in=str, dtype_out=str)
    def clear_fifo(self, group_name: str):
        raw_group = str(group_name or "").strip().lower()
        with self._lock:
            if raw_group in ("", "all", "*"):
                self._fifo_all.clear()
                for queue in self._fifo_by_group.values():
                    queue.clear()
                self._latest_by_channel.clear()
                return "OK"

            target = self._normalize_group_name(raw_group)
            if target == "other" and raw_group != "other":
                return f"ERROR: unknown group '{group_name}'"
            if target in self._fifo_by_group:
                self._fifo_by_group[target].clear()
        return "OK"


if __name__ == "__main__":
    DS_PSP.run_server()
