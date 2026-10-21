"""Dedicated bounded telemetry publisher and signed relay ownership."""
import datetime
import threading

from .standard_banks import standard_packet, validate_standard_packet, _finite
from .shared_state import LatestSnapshotOutbox
from .telemetry_relay import TelemetryRelay
from .telemetry_view import TelemetryView

class StandardTelemetryPublisher(object):
    """Bounded latest-only forwarding, authenticated ACK and read-only retry."""
    def __init__(self, runtime, address, key, period=.2):
        if address[0] not in ("10.20.30.202", "127.0.0.1") or not .05 <= period <= 10:
            raise ValueError("Explicit Everest telemetry endpoint and bounded period required")
        self.runtime, self.period = runtime, period
        self.view = TelemetryView(runtime)
        self.outbox = LatestSnapshotOutbox()
        self.relay = TelemetryRelay(self.outbox, address, key)
        self.stop_event, self.worker = threading.Event(), None
        self.sequence, self.identity, self.error = 0, None, ""

    def publish_once(self):
        value = self.view.snapshot()
        identity = tuple(value.get(k) for k in ("session_id", "sequence", "state_revision", "state", "stale", "error", "telemetry_view_current"))
        if identity == self.identity:
            return False
        packet = standard_packet(value, self.sequence + 1)
        encoded = validate_standard_packet(packet)
        age = value.get("age_seconds")
        age = age if _finite(age) and age >= 0 else 0
        self.outbox.enqueue(encoded, datetime.datetime.now(datetime.timezone.utc).isoformat(), age_seconds=age)
        self.sequence += 1
        self.identity, self.error = identity, ""
        return True

    def start(self):
        if self.worker is not None or self.stop_event.is_set():
            raise RuntimeError("Telemetry publisher cannot be started twice")
        def run():
            while not self.stop_event.is_set():
                try:
                    self.publish_once()
                except Exception as error:
                    self.error = type(error).__name__ + ": " + str(error)[:300]
                self.stop_event.wait(self.period)
        self.relay.start()
        self.worker = threading.Thread(target=run, name="ACQ-standard-telemetry-publisher")
        self.worker.daemon = True
        try:
            self.worker.start()
        except Exception:
            self.worker = None
            self.stop_event.set()
            self.relay.close()
            raise

    def close(self):
        self.stop_event.set()
        if self.worker is not None:
            self.worker.join(3)
            if self.worker.is_alive():
                raise RuntimeError("Telemetry publisher still owned; no overlapping replacement")
        self.relay.close()

    def status(self):
        return dict(self.relay.status(), standard_bank_count=27, publication_sequence=self.sequence,
                    telemetry_view=self.view.status(),
                    publisher_error=self.error, semantics="AI/DI measurements; AO/DO last successful commands; other banks explicitly unavailable")
