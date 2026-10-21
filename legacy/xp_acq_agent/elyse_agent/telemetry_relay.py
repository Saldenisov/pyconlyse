"""Bounded telemetry FIFO and signed XP -> Everest forwarding, Python 3.4.

No hardware, PSP or Tango imports. Successful local receipt is distinct from
Everest acknowledgement. Pending RAM messages do not survive process restart.
"""
from __future__ import division

from collections import deque
import hashlib
import hmac
import json
import socket
import threading
import time
import uuid

from .protocol import recv_message, send_message
from .supervision_wire import validate_key


MAX_RELAY_FRAME = 1048576


class DeadlineSocket(object):
    """Absolute transaction deadline, including peers that trickle bytes."""
    def __init__(self, connection, deadline, clock=None):
        self.connection, self.deadline = connection, deadline
        self.clock = clock or time.monotonic

    def _remaining(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise socket.timeout("telemetry transaction deadline exceeded")
        self.connection.settimeout(remaining)

    def recv(self, count):
        self._remaining()
        return self.connection.recv(count)

    def sendall(self, payload):
        self._remaining()
        return self.connection.sendall(payload)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sign(key, direction, value):
    return hmac.new(validate_key(key), direction.encode("ascii") + b"\n" + canonical(value),
                    hashlib.sha256).hexdigest()


class TelemetryOutbox(object):
    def __init__(self, capacity=1000, max_bytes=16777216, clock=None):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("FIFO capacity must be a positive integer")
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("FIFO byte limit must be a positive integer")
        self.capacity, self.max_bytes = capacity, max_bytes
        self._clock = clock or time.monotonic
        self._queue = deque()
        self._lock = threading.RLock()
        self._pending_bytes = 0
        self._next_id = 1
        self.relay_id = uuid.uuid4().hex
        self.rejected = self.delivered = 0
        self.changed = threading.Event()

    def enqueue(self, encoded, received_utc):
        byte_count = len(encoded.encode("utf-8"))
        with self._lock:
            if len(self._queue) >= self.capacity or self._pending_bytes + byte_count > self.max_bytes:
                self.rejected += 1
                raise ValueError("telemetry FIFO full; new publication rejected")
            entry = (self._next_id, encoded, received_utc, self._clock(), byte_count)
            self._next_id += 1
            self._queue.append(entry)
            self._pending_bytes += byte_count
            self.changed.set()
            return entry[0]

    def peek(self):
        with self._lock:
            if not self._queue:
                self.changed.clear()
                return None
            sequence, encoded, received_utc, received_at, byte_count = self._queue[0]
            return {"schema_version": 1, "relay_id": self.relay_id, "message_id": sequence,
                    "received_utc_on_xp": received_utc,
                    "age_seconds_on_xp": max(0.0, self._clock() - received_at),
                    "packet": json.loads(encoded), "hardware_writes": False}

    def acknowledge(self, relay_id, message_id):
        with self._lock:
            if relay_id != self.relay_id or not self._queue or self._queue[0][0] != message_id:
                raise ValueError("ACK does not match FIFO head")
            entry = self._queue.popleft()
            self._pending_bytes -= entry[4]
            self.delivered += 1
            if not self._queue:
                self.changed.clear()

    def status(self):
        with self._lock:
            return {"capacity": self.capacity, "pending": len(self._queue),
                    "pending_bytes": self._pending_bytes, "max_bytes": self.max_bytes,
                    "rejected_new": self.rejected, "everest_acknowledged": self.delivered,
                    "overflow_policy": "reject_new", "durable": False,
                    "relay_id": self.relay_id}


class TelemetryRelay(object):
    """One forwarding thread; dequeue only after a verified matching ACK."""
    def __init__(self, outbox, address, key, timeout=2.0, retry_seconds=1.0):
        if not isinstance(address, tuple) or len(address) != 2:
            raise ValueError("explicit Everest host/port tuple required")
        if not isinstance(address[0], str) or not address[0] or type(address[1]) is not int or not 1 <= address[1] <= 65535:
            raise ValueError("invalid Everest endpoint")
        if not 0 < timeout <= 10 or not 0 < retry_seconds <= 60:
            raise ValueError("invalid relay time bounds")
        self.outbox, self.address, self.key = outbox, address, validate_key(key)
        self.timeout, self.retry_seconds = timeout, retry_seconds
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._last_error = "Not started"
        self._attempts = 0

    def send_once(self):
        body = self.outbox.peek()
        if body is None:
            return False
        nonce = uuid.uuid4().hex
        signed = dict(body=body, nonce=nonce)
        request = dict(signed, signature=sign(self.key, "ACQ-TELEMETRY-REQUEST-1", signed))
        deadline = time.monotonic() + self.timeout
        with socket.create_connection(self.address, timeout=self.timeout) as connection:
            bounded = DeadlineSocket(connection, deadline)
            send_message(bounded, request, MAX_RELAY_FRAME)
            ack = recv_message(bounded, MAX_RELAY_FRAME)
        if not isinstance(ack, dict) or set(ack) != set(("body", "nonce", "signature")):
            raise ValueError("malformed Everest ACK")
        signed_ack = dict(body=ack["body"], nonce=ack["nonce"])
        expected = sign(self.key, "ACQ-TELEMETRY-ACK-1", signed_ack)
        if not isinstance(ack["signature"], str) or not hmac.compare_digest(ack["signature"], expected):
            raise ValueError("Everest ACK authentication failed")
        result = ack["body"]
        if (ack["nonce"] != nonce or not isinstance(result, dict)
                or result.get("accepted") is not True
                or result.get("relay_id") != body["relay_id"]
                or type(result.get("message_id")) is not int
                or result["message_id"] != body["message_id"]):
            raise ValueError("Everest ACK does not accept this FIFO message")
        self.outbox.acknowledge(body["relay_id"], body["message_id"])
        return True

    def _run(self):
        while not self._stop.is_set():
            if self.outbox.peek() is None:
                self.outbox.changed.wait(0.25)
                continue
            try:
                with self._lock:
                    self._attempts += 1
                self.send_once()
                with self._lock:
                    self._last_error = ""
            except Exception as error:
                with self._lock:
                    self._last_error = str(error)
                self._stop.wait(self.retry_seconds)

    def start(self):
        if self._thread is not None:
            raise RuntimeError("relay already started")
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        try:
            self._thread.start()
        except Exception:
            self._thread = None
            raise

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(self.timeout * 2 + 1)
            if self._thread.is_alive():
                raise RuntimeError("telemetry relay did not stop within shutdown bound")

    def status(self):
        with self._lock:
            return dict(self.outbox.status(), attempts=self._attempts,
                        last_error=self._last_error, endpoint="{0}:{1}".format(*self.address))
