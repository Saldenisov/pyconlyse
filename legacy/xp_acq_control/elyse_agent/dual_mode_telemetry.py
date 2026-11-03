"""One XP process: VI loopback bridge while IDLE, NI publisher otherwise.

No PSP reads, VI launch/stop, native imports or card operations. Source admission
and Initialize share the runtime lock. Silence is not proof that LabVIEW has
released cards: the existing explicit local startup confirmation still applies.
"""
import datetime
import threading
import time

from .telemetry_publisher import StandardTelemetryPublisher, telemetry_identity
from .standard_banks import standard_packet, validate_standard_packet, packet_age_seconds
from .shared_state import decode_snapshot_xml, validate_snapshot_packet
from .shared_state_receiver import SharedStateServer

BRIDGE_SITE = "xp_unified_labview_bridge_27_banks"
NATIVE_SITE = "xp_unified_python_owner_27_banks"
VI_QUIET_SECONDS = 2


class DualModeTelemetryPublisher(StandardTelemetryPublisher):
    def __init__(self, runtime, address, key, period=.2, ingress_address=("127.0.0.1", 8766),
                 xml_encoding="cp1252", clock=None, packet_transform=None):
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
        self._vi_condition = threading.Condition(self.lock)
        self._pending_vi = None
        self.vi_admission_worker = None
        self._vi_ingress_sequence = self._vi_admitted_sequence = 0
        self.vi_deferred = self.vi_deferred_replaced = self.vi_deferred_rejected = 0
        self.vi_owner_contentions = 0
        self.vi_admission_delay_seconds = self.vi_admission_delay_max_seconds = 0.
        if packet_transform is not None and not callable(packet_transform):
            raise TypeError("Trusted local telemetry transform required")
        self.packet_transform = packet_transform

    def assert_initialize_allowed(self):
        # Called with the runtime lock BEFORE the NI owner is woken.
        with self.lock:
            if self.last_vi_seen is not None and self.clock() - self.last_vi_seen < VI_QUIET_SECONDS:
                raise RuntimeError("LabVIEW telemetry is still arriving; stop Acquisition VI and confirm card release locally")

    def _enqueue(self, packet, age=0, projection=None):
        encoded = (validate_standard_packet(packet) if packet["producer_kind"] == "python_acquisition"
                   else validate_snapshot_packet(packet))
        if self.packet_transform is not None:
            encoded = self.packet_transform(packet, age, projection)
            age = 0  # Owner frames carry a separate age on every source record.
        self.outbox.enqueue(encoded, datetime.datetime.now(datetime.timezone.utc).isoformat(), age_seconds=age)
        self.sequence = packet["sequence"]
        self.error = ""

    def ingest(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI snapshot ingestion requires IPv4 loopback")
        received_at = self.clock()
        received_utc = datetime.datetime.now(datetime.timezone.utc)
        # A scalar epoch is only an invalidation tag, never admission proof.
        # Admission still captures/rechecks under the real lifecycle lock.
        epoch = self.runtime._state_revision
        with self.lock:
            self._vi_ingress_sequence += 1
            number = self._vi_ingress_sequence
        # Parsing is driver-free and outside the owner lock; recheck after it.
        records = decode_snapshot_xml(raw, self.xml_encoding)
        with self.lock:
            self.last_vi_seen = self.clock()
            observation = (number, epoch, received_at, received_utc, records)
        if not self.runtime._lock.acquire(False):
            # Metadata captures share this lock. Contention is not evidence
            # that a valid loopback packet is bad or that NI is initializing.
            # ACK only bounded RAM staging, not source admission or delivery.
            with self._vi_condition:
                if self.stop_event.is_set():
                    raise ValueError("VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS")
                self.vi_owner_contentions += 1
                if observation[0] <= self._vi_admitted_sequence:
                    return self._staging_reply(superseded=True)
                if self._pending_vi is not None:
                    if observation[0] <= self._pending_vi[0]:
                        return self._staging_reply(superseded=True)
                    self.vi_deferred_replaced += 1
                self._pending_vi = observation
                self.vi_deferred += 1
                self._vi_condition.notify_all()
                return self._staging_reply()
        try:
            # RAM projection only. The RLock also fences local Initialize, but
            # ingress never waits for command admission, policy or disk I/O.
            value = self.view.snapshot()
            with self.lock:
                return self._admit_vi_locked(observation, value)
        finally:
            self.runtime._lock.release()

    @staticmethod
    def _staging_reply(superseded=False):
        return dict(accepted=True, admission_pending=not superseded, superseded=superseded,
                    bank_count=27, sequence=None, hardware_writes=False,
                    acknowledged_on="xp_ram_staging_not_published_or_everest")

    def _admit_vi_locked(self, observation, value):
        # Caller holds runtime then publication lock, exactly as Initialize.
        number, epoch, received_at, received_utc, records = observation
        if self.stop_event.is_set() or not value.get("telemetry_bridge_mode"):
            raise ValueError("VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS")
        if value.get("state_revision") != epoch:
            raise ValueError("VI_INGRESS_OWNER_EPOCH_CHANGED")
        age = max(0., self.clock() - received_at)
        if age >= VI_QUIET_SECONDS:
            raise ValueError("VI_DEFERRED_SOURCE_EXPIRED")
        if number <= self._vi_admitted_sequence:
            return self._staging_reply(superseded=True)
        packet = standard_packet(value, self.sequence + 1, now=received_utc)
        packet.update(producer_kind="copied_acquisition", source_site=BRIDGE_SITE)
        packet["data"].update(capture_kind="sequential_local_controls",
                              timestamp_origin="xp_receipt_not_card_sample", banks=records)
        age = max(0., self.clock() - received_at)
        if age >= VI_QUIET_SECONDS:
            raise ValueError("VI_DEFERRED_SOURCE_EXPIRED")
        self._enqueue(packet, age=age, projection=value)
        self._vi_admitted_sequence = number
        if self._pending_vi is not None and self._pending_vi[0] <= number:
            self._pending_vi = None
            self.vi_deferred_replaced += 1
        self.last_vi_receipt = received_at
        self.vi_admission_delay_seconds = age
        self.vi_admission_delay_max_seconds = max(self.vi_admission_delay_max_seconds, age)
        self.vi_accepted += 1
        self.mode, self.last_error, self.owner_state_current = "LABVIEW_BRIDGE", "", True
        # Polling must not erase this VI image with an IDLE boundary.
        self.identity = self._identity(value)
        return dict(accepted=True, admission_pending=False, bank_count=27, sequence=self.sequence,
                    hardware_writes=False, acknowledged_on="xp_ram_not_everest")

    def _drain_deferred_once(self):
        if not self.runtime._lock.acquire(False):
            return False
        try:
            value = self.view.snapshot()
            with self.lock:
                observation, self._pending_vi = self._pending_vi, None
                if observation is None:
                    return True
                try:
                    self._admit_vi_locked(observation, value)
                except Exception as error:
                    self.vi_deferred_rejected += 1
                    self.rejected += 1
                    self.last_error = str(error)
                return True
        finally:
            self.runtime._lock.release()

    def _vi_admission_loop(self):
        while not self.stop_event.is_set():
            with self._vi_condition:
                while self._pending_vi is None and not self.stop_event.is_set():
                    self._vi_condition.wait(.25)
                if self.stop_event.is_set():
                    return
            try:
                drained = self._drain_deferred_once()
            except Exception as error:
                # A diagnostic capture error cannot silently kill this worker.
                with self.lock:
                    self.last_error = type(error).__name__ + ": " + str(error)[:300]
                drained = False
            if not drained:
                # Retain one latest packet without spinning or holding either
                # lock. New observations and Stop wake this wait immediately.
                with self._vi_condition:
                    self._vi_condition.wait(.01)

    @staticmethod
    def _identity(value):
        return telemetry_identity(value)

    def publish_once(self):
        with self.lock:
            generation = self.sequence
        value = self.view.snapshot()
        with self.lock:
            # A VI image published during capture takes precedence over the
            # older poll, including captures spanning deinitialization.
            if generation != self.sequence:
                return False
            self.owner_state_current = value.get("telemetry_view_current", False)
            identity = self._identity(value)
            if identity == self.identity:
                return False
            bridge = value.get("telemetry_bridge_mode", False)
            if (bridge and not self.owner_state_current and self.last_vi_receipt is not None
                    and self.clock() - self.last_vi_receipt < VI_QUIET_SECONDS):
                # Ingress itself briefly owns the lifecycle lock. A poll that
                # collides with it must not erase a recently admitted VI image.
                # Initialize is fenced for at least this same quiet interval.
                # Send nothing: retained receiver data ages normally, with no
                # replay, new sequence, timestamp or freshness extension. Once
                # quiet expires, unavailable/native transition packets still win.
                return False
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
            self._enqueue(packet, packet_age_seconds(value, packet) if not bridge else 0, projection=value)
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
            self.vi_admission_worker = threading.Thread(target=self._vi_admission_loop,
                                                       name="ACQ-VI-deferred-admission")
            self.vi_admission_worker.daemon = True
            self.vi_admission_worker.start()
            self.ingress_worker.start()
            StandardTelemetryPublisher.start(self)
        except Exception:
            self.close()
            raise

    def close(self):
        self.stop_event.set()
        with self._vi_condition:
            self._vi_condition.notify_all()
        if self.vi_admission_worker is not None and self.vi_admission_worker.ident is not None:
            self.vi_admission_worker.join(3)
            if self.vi_admission_worker.is_alive():
                raise RuntimeError("VI admission worker remains owned; replacement refused")
        with self.lock:
            self._pending_vi = None
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
                          vi_owner_contentions=self.vi_owner_contentions,
                          vi_deferred=self.vi_deferred, vi_deferred_replaced=self.vi_deferred_replaced,
                          vi_deferred_rejected=self.vi_deferred_rejected,
                          vi_deferred_pending=int(self._pending_vi is not None), vi_deferred_capacity=1,
                          vi_admission_delay_seconds=self.vi_admission_delay_seconds,
                          vi_admission_delay_max_seconds=self.vi_admission_delay_max_seconds,
                          vi_age_seconds=None if self.last_vi_receipt is None else max(0, self.clock() - self.last_vi_receipt),
                          vi_seen_age_seconds=None if self.last_vi_seen is None else max(0, self.clock() - self.last_vi_seen),
                          vi_initialize_exclusion_active=(self.last_vi_seen is not None
                              and self.clock() - self.last_vi_seen < VI_QUIET_SECONDS),
                          ingress_endpoint="{0}:{1}".format(*self.ingress_address),
                          ingress_handler_limit_rejections=(0 if self.server is None
                              else self.server.handler_limit_rejections),
                          vi_state_not_proof_of_card_release=True)
        return result
