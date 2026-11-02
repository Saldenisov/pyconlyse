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
from .telemetry_diagnostics import TelemetryDiagnostics

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
        self.diagnostics = TelemetryDiagnostics(session_id=getattr(runtime, '_identity', {}).get('session_id'))
        self.ingress_loop_failures = 0
        self.ingress_loop_error = ''
        self.ingress_retrying = False
        self._last_health = None
        self._last_checkpoint = None
        if packet_transform is not None and not callable(packet_transform):
            raise TypeError("Trusted local telemetry transform required")
        self.packet_transform = packet_transform

    def assert_initialize_allowed(self):
        # Called with the runtime lock BEFORE the NI owner is woken.
        with self.lock:
            if self.last_vi_seen is not None and self.clock() - self.last_vi_seen < VI_QUIET_SECONDS:
                raise RuntimeError("LabVIEW telemetry is still arriving; stop Acquisition VI and confirm card release locally")

    def _enqueue(self, packet, age=0, projection=None, received_at=None, received_utc=None):
        began = self.clock()
        encoded = (validate_standard_packet(packet) if packet["producer_kind"] == "python_acquisition"
                   else validate_snapshot_packet(packet))
        source_age = (max(0, self.clock() - received_at) if received_at is not None
                      else age + max(0, self.clock() - began))
        if self.packet_transform is not None:
            transformed_at = self.clock()
            encoded = self.packet_transform(packet, source_age, projection)
            source_age = max(0, self.clock() - transformed_at)  # Per-bank ages already carry source_age.
        self.outbox.enqueue(encoded, received_utc or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            age_seconds=source_age)
        self.sequence = packet["sequence"]
        self.error = ""

    def ingest(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI snapshot ingestion requires IPv4 loopback")
        # Parsing is driver-free and outside the owner lock; recheck after it.
        received_at = self.clock()
        received_utc = datetime.datetime.now(datetime.timezone.utc)
        records = decode_snapshot_xml(raw, self.xml_encoding)
        with self.lock:
            self.last_vi_seen = self.clock()
            if not self.runtime._lock.acquire(False):
                raise ValueError("OWNER_STATE_BUSY_VI_NOT_ADMITTED")
            try:
                # Capture the admission decision atomically with lifecycle.
                # Never retain the owner lock during encoding or outbox work.
                value = self.view.snapshot()
                if self.stop_event.is_set() or not value.get("telemetry_bridge_mode"):
                    self.last_error = "VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS"
                    raise ValueError(self.last_error)
            finally:
                self.runtime._lock.release()
            # Initialize takes owner -> publication lock and checks last_vi_seen.
            # We only TRY owner while holding publication: no reverse wait or
            # deadlock. An Initialize racing encoding still fails its VI fence.
            packet = standard_packet(value, self.sequence + 1, now=received_utc)
            packet.update(producer_kind="copied_acquisition", source_site=BRIDGE_SITE)
            packet["data"].update(capture_kind="sequential_local_controls",
                                  timestamp_origin="xp_receipt_not_card_sample", banks=records)
            self._enqueue(packet, projection=value, received_at=received_at,
                          received_utc=received_utc.isoformat())
            self.last_vi_receipt = received_at
            self.vi_accepted += 1
            self.mode, self.last_error, self.owner_state_current = "LABVIEW_BRIDGE", "", True
            # Polling must not erase this VI image with an IDLE boundary.
            self.identity = self._identity(value)
            return dict(accepted=True, bank_count=27, sequence=self.sequence,
                        hardware_writes=False, acknowledged_on="xp_ram_not_everest")

    @staticmethod
    def _identity(value):
        return telemetry_identity(value)

    def publish_once(self):
        self._report_health()
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
        self.server.timeout = .1
        self.ingress_worker = threading.Thread(target=self._ingress_loop,
                                               name="ACQ-VI-loopback-ingress")
        self.ingress_worker.daemon = True
        try:
            self.diagnostics.start()
            self.diagnostics.emit('TELEMETRY_STARTED', ingress='{0}:{1}'.format(*self.ingress_address))
            self.ingress_worker.start()
            StandardTelemetryPublisher.start(self)
        except Exception:
            self.close()
            raise

    def _ingress_loop(self):
        # One existing bound socket, one listener thread. A transient listener
        # exception cannot silently kill ingress; retry never starts NI or a
        # second process. handle_request has a short timeout, so shutdown does
        # not race a serve_forever restart or wait on its private stop flag.
        delay = .1
        while not self.stop_event.is_set():
            try:
                self.server.handle_request()
                with self.lock:
                    self.ingress_retrying = False
                delay = .1
            except Exception as error:
                with self.lock:
                    self.ingress_loop_failures += 1
                    self.ingress_loop_error = type(error).__name__ + ': ' + str(error)[:300]
                    self.ingress_retrying = True
                self.diagnostics.emit('INGRESS_LOOP_FAILURE', throttle=5,
                                      reason=self.ingress_loop_error)
                if self.stop_event.wait(delay):
                    break
                delay = min(5, delay * 2)

    def _report_health(self):
        value = self.status()
        now = self.clock()
        health = value['transport_health']
        if health != self._last_health or self._last_checkpoint is None or now - self._last_checkpoint >= 30:
            self.diagnostics.emit('TRANSPORT_HEALTH', health=health,
                source_mode=value['source_mode'], vi_accepted=value['vi_accepted'],
                vi_rejected=value['vi_rejected'], vi_seen_age_seconds=value['vi_seen_age_seconds'],
                everest_acknowledged=value.get('everest_acknowledged'),
                ingress_loop_failures=value['ingress_loop_failures'])
            self._last_health, self._last_checkpoint = health, now

    def close(self):
        self.stop_event.set()
        if self.server is not None:
            if self.ingress_worker is not None and self.ingress_worker.is_alive():
                self.ingress_worker.join(3)
                if self.ingress_worker.is_alive():
                    raise RuntimeError("VI ingress remains owned; replacement refused")
            self.server.server_close()
            self.server = None
        try:
            StandardTelemetryPublisher.close(self)
        finally:
            self.diagnostics.emit('TELEMETRY_CLOSED')
            self.diagnostics.close()

    def status(self):
        result = StandardTelemetryPublisher.status(self)
        with self.lock:
            result.update(source_mode=self.mode, owner_state_current=self.owner_state_current,
                          vi_accepted=self.vi_accepted, vi_rejected=self.rejected, vi_ingress_error=self.last_error,
                          vi_age_seconds=None if self.last_vi_receipt is None else max(0, self.clock() - self.last_vi_receipt),
                          vi_seen_age_seconds=None if self.last_vi_seen is None else max(0, self.clock() - self.last_vi_seen),
                          vi_initialize_exclusion_active=(self.last_vi_seen is not None
                              and self.clock() - self.last_vi_seen < VI_QUIET_SECONDS),
                          ingress_endpoint="{0}:{1}".format(*self.ingress_address),
                          ingress_handler_limit_rejections=(0 if self.server is None
                              else self.server.handler_limit_rejections),
                          vi_state_not_proof_of_card_release=True)
            result.update(ingress_worker_alive=bool(self.ingress_worker and self.ingress_worker.is_alive()),
                          publisher_worker_alive=bool(self.worker and self.worker.is_alive()),
                          relay_worker_alive=bool(self.relay._thread and self.relay._thread.is_alive()),
                          ingress_loop_failures=self.ingress_loop_failures,
                          ingress_loop_error=self.ingress_loop_error,
                          ingress_retrying=self.ingress_retrying,
                          ingress_statistics={} if self.server is None else self.server.statistics())
            if self.stop_event.is_set():
                health = 'STOPPED'
            elif self.ingress_worker is not None and not result['ingress_worker_alive']:
                health = 'INGRESS_THREAD_STOPPED'
            elif self.worker is not None and not result['publisher_worker_alive']:
                health = 'PUBLISHER_THREAD_STOPPED'
            elif self.relay._thread is not None and not result['relay_worker_alive']:
                health = 'RELAY_THREAD_STOPPED'
            elif self.ingress_retrying:
                health = 'INGRESS_RETRYING'
            elif self.mode != 'LABVIEW_BRIDGE':
                health = 'NATIVE_OR_TRANSITION'
            elif result['vi_seen_age_seconds'] is None:
                health = 'VI_INPUT_REJECTED' if result['ingress_statistics'].get('xml_frames_seen') else 'WAITING_FOR_VI'
            elif result['vi_seen_age_seconds'] >= VI_QUIET_SECONDS:
                health = 'VI_SOURCE_SILENT'
            elif result['vi_age_seconds'] is None:
                health = 'VI_ADMISSION_BLOCKED'
            elif result['vi_age_seconds'] >= VI_QUIET_SECONDS:
                health = 'VI_SNAPSHOT_DELAYED'
            elif self.relay._thread is not None and result.get('last_error'):
                health = 'EVEREST_DELIVERY_ERROR'
            else:
                health = 'RECEIVING_VI'
            result['transport_health'] = health
            result['diagnostics'] = self.diagnostics.snapshot()
        return result
