"""One XP process: VI loopback bridge while IDLE, NI publisher otherwise.

No PSP reads, VI launch/stop, native imports or card operations. Source admission
and Initialize share the runtime lock. Silence is not proof that LabVIEW has
released cards: the existing explicit local startup confirmation still applies.
"""
import datetime
import threading
import time

from .telemetry_publisher import StandardTelemetryPublisher
from .standard_banks import standard_packet, validate_standard_packet
from .shared_state import decode_snapshot_xml, validate_snapshot_packet
from .shared_state_receiver import SharedStateServer

BRIDGE_SITE = "xp_unified_labview_bridge_27_banks"
NATIVE_SITE = "xp_unified_python_owner_27_banks"


class DualModeTelemetryPublisher(StandardTelemetryPublisher):
    def __init__(self, runtime, address, key, period=.2, ingress_address=("127.0.0.1", 8766),
                 xml_encoding="cp1252", clock=None):
        StandardTelemetryPublisher.__init__(self, runtime, address, key, period)
        if xml_encoding not in ("utf-8", "cp1252"):
            raise ValueError("Explicit saved VI XML encoding required")
        self.xml_encoding, self.ingress_address = xml_encoding, ingress_address
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()  # Also used by the bounded ingress error handler.
        self.owner_state_current = False
        self.rejected, self.last_error, self.vi_accepted = 0, "", 0
        self.last_vi_receipt, self.last_vi_seen = None, None
        self.server, self.ingress_worker = None, None
        self.mode = "LABVIEW_BRIDGE"

    def assert_initialize_allowed(self):
        # Called with the runtime lock BEFORE the NI owner is woken.
        with self.lock:
            if self.last_vi_seen is not None and self.clock() - self.last_vi_seen < 2:
                raise RuntimeError("LabVIEW telemetry is still arriving; stop Acquisition VI and confirm card release locally")

    def _enqueue(self, packet, age=0):
        encoded = (validate_standard_packet(packet) if packet["producer_kind"] == "python_acquisition"
                   else validate_snapshot_packet(packet))
        self.outbox.enqueue(encoded, datetime.datetime.now(datetime.timezone.utc).isoformat(), age_seconds=age)
        self.sequence = packet["sequence"]
        self.error = ""

    def ingest(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI snapshot ingestion requires IPv4 loopback")
        # Parsing is driver-free and outside the owner lock; recheck after it.
        records = decode_snapshot_xml(raw, self.xml_encoding)
        with self.lock:
            self.last_vi_seen = self.clock()
        if not self.runtime._lock.acquire(False):
            raise ValueError("OWNER_STATE_BUSY_VI_NOT_ADMITTED")
        try:
            # RAM projection only. The RLock also fences local Initialize, but
            # ingress never waits for command admission, policy or disk I/O.
            value = self.view.snapshot()
            with self.lock:
                if self.stop_event.is_set() or not value.get("telemetry_bridge_mode"):
                    self.last_error = "VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS"
                    raise ValueError(self.last_error)
                packet = standard_packet(value, self.sequence + 1)
                packet.update(producer_kind="copied_acquisition", source_site=BRIDGE_SITE)
                packet["data"].update(capture_kind="sequential_local_controls",
                                      timestamp_origin="xp_receipt_not_card_sample", banks=records)
                self._enqueue(packet)
                self.last_vi_receipt = self.clock()
                self.vi_accepted += 1
                self.mode, self.last_error, self.owner_state_current = "LABVIEW_BRIDGE", "", True
                # Polling must not erase this VI image with an IDLE boundary.
                self.identity = self._identity(value)
                return dict(accepted=True, bank_count=27, sequence=self.sequence,
                            hardware_writes=False, acknowledged_on="xp_ram_not_everest")
        finally:
            self.runtime._lock.release()

    @staticmethod
    def _identity(value):
        return tuple(value.get(k) for k in ("session_id", "sequence", "state_revision", "state", "stale", "error", "telemetry_view_current"))

    def publish_once(self):
        with self.lock:
            generation = self.sequence
        value = self.view.snapshot()
        with self.lock:
            # A VI image published during capture takes precedence over the
            # older poll, including captures spanning deinitialization.
            if generation != self.sequence:
                return False
            identity = self._identity(value)
            if identity == self.identity:
                return False
            bridge = value.get("telemetry_bridge_mode", False)
            self.owner_state_current = value.get("telemetry_view_current", False)
            packet = standard_packet(value, self.sequence + 1)
            if bridge:
                packet.update(producer_kind="copied_acquisition", source_site=BRIDGE_SITE)
                packet["data"].update(capture_kind="sequential_local_controls",
                                      timestamp_origin="xp_receipt_not_card_sample")
                for record in packet["data"]["banks"]:
                    record["error"]["source"] = ("LABVIEW_WAITING_FOR_NEW_SNAPSHOT" if self.owner_state_current
                                                   else "OWNER_STATE_BUSY")
                if self.owner_state_current:
                    self.mode = "LABVIEW_BRIDGE"
                    self.last_vi_receipt = None  # Never revive a pre-initialization VI image.
            else:
                packet["source_site"] = NATIVE_SITE
                # A failed read with retained NI ownership still needs the
                # explicitly requested stop path. It must not fall back to VI.
                if self.owner_state_current:
                    self.mode = "PYTHON_NATIVE" if (value["state"] in ("RUNNING", "EXECUTING")
                        or (value["state"] == "FAULT" and value.get("resource_count", 0) > 0)) else "TRANSITION_OR_FAULT"
            age = value.get("age_seconds")
            self._enqueue(packet, age if type(age) in (int, float) and age >= 0 and not bridge else 0)
            self.identity = identity
            return True

    def start(self):
        if self.server is not None or self.stop_event.is_set():
            raise RuntimeError("Unified telemetry cannot start twice")
        # Bind first. Another bridge on 8766 blocks startup rather than being
        # terminated or silently becoming a competing publisher.
        self.server = SharedStateServer(self.ingress_address, self)
        self.ingress_worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.1),
                                               name="ACQ-VI-loopback-ingress")
        self.ingress_worker.daemon = True
        try:
            self.ingress_worker.start()
            StandardTelemetryPublisher.start(self)
        except Exception:
            self.close()
            raise

    def close(self):
        self.stop_event.set()
        if self.server is not None:
            if self.ingress_worker is not None and self.ingress_worker.is_alive():
                self.server.shutdown()
                self.ingress_worker.join(3)
                if self.ingress_worker.is_alive():
                    raise RuntimeError("VI ingress remains owned; replacement refused")
            self.server.server_close()
            self.server = None
        StandardTelemetryPublisher.close(self)

    def status(self):
        result = StandardTelemetryPublisher.status(self)
        with self.lock:
            result.update(source_mode=self.mode, owner_state_current=self.owner_state_current,
                          vi_accepted=self.vi_accepted, vi_rejected=self.rejected, vi_ingress_error=self.last_error,
                          vi_age_seconds=None if self.last_vi_receipt is None else max(0, self.clock() - self.last_vi_receipt),
                          ingress_endpoint="{0}:{1}".format(*self.ingress_address),
                          vi_state_not_proof_of_card_release=True)
        return result
