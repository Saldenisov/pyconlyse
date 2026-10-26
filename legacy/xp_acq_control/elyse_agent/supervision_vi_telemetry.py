"""SuperVision VI/native telemetry in one application/publisher, Python 3.4.

Existing 27-control XML stays on 127.0.0.1:8766. Optional typed observations
use 127.0.0.1:8768, four-byte big-endian length then strict UTF-8 JSON. Native
LabVIEW producers still require authoring/qualification; no VI is generated.
Counter memory, opaque C12 String and raw images retain independent ages.
"""
import copy
import hashlib
import json
import socketserver
import struct
import threading
import time

from .federation_wire import (hex_id, owner_frame,
                              validate_counter_part, validate_video_frame)
from .orchestrator_publisher import OwnerTelemetryPublisher
from .protocol import recv_exact, send_message
from .shared_state import decode_snapshot_xml
from .shared_state_receiver import SharedStateServer
from .standard_banks import standard_packet, schemas, packet_age_seconds
from .telemetry_relay import DeadlineSocket, canonical


PUBLICATION = "ELYSE_SUPERVISION_VI_OBSERVATION"
VI_ADDRESS = ("127.0.0.1", 8768)
MAX_VI_BYTES = 900 * 1024
MAX_VI_SESSIONS = 64


def validate_vi_observation(value):
    if (type(value) is not dict or set(value) != {"schema_version", "publication",
            "source_session_id", "sequence", "source_running", "counter_part", "video_frame"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["publication"] != PUBLICATION or not hex_id(value["source_session_id"])
            or type(value["sequence"]) is not int or not 1 <= value["sequence"] <= 9007199254740991
            or value["source_running"] is not True
            or value["counter_part"] is None and value["video_frame"] is None):
        raise ValueError("Exact running SuperVision VI observation required")
    counter, video = value["counter_part"], value["video_frame"]
    validate_counter_part(counter)
    if counter is not None and counter["source"] != "observed_labview_control_memory":
        raise ValueError("VI counter values are observed control memory, not acknowledged hardware")
    validate_video_frame(video)
    if video is not None and (video["source"] != "labview_supervision_ni1409"
            or video["source_session_id"] != value["source_session_id"]):
        raise ValueError("VI camera must name the current source-run session")
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    if len(raw) > MAX_VI_BYTES:
        raise ValueError("SuperVision VI observation exceeds bounded frame size")
    return raw


def decode_vi_observation(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_VI_BYTES:
        raise ValueError("Bounded UTF-8 SuperVision VI JSON required")
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate VI observation field")
            result[key] = item
        return result
    def nonfinite(unused):
        raise ValueError("Nonfinite VI observation value")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    validate_vi_observation(value)
    return value


class _TypedHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != "127.0.0.1":
            return
        bounded = DeadlineSocket(self.request, time.monotonic() + 2)
        try:
            size = struct.unpack("!I", recv_exact(bounded, 4))[0]
            if not 1 <= size <= MAX_VI_BYTES:
                raise ValueError("Invalid SuperVision VI frame length")
            result = self.server.store.ingest_observation(recv_exact(bounded, size), self.client_address[0])
            reply = dict(id="supervision-vi", ok=True, result=result)
        except Exception as error:
            with self.server.store.lock:
                self.server.store.rejected += 1
                self.server.store.last_error = str(error)[:300]
            reply = dict(id="supervision-vi", ok=False,
                error=dict(code="snapshot_rejected", message=str(error)[:300]))
        try:
            send_message(bounded, reply, 16384)
        except Exception:
            pass  # A local RAM ACK does not imply receipt or Everest durability.


class SupervisionVIServer(SharedStateServer):
    """Reuse bounded four-handler lifecycle without modifying Acquisition XML."""
    def __init__(self, address, publisher):
        if address[0] != "127.0.0.1":
            raise ValueError("SuperVision VI ingress must be IPv4 loopback")
        self.store = publisher
        self._slots = threading.BoundedSemaphore(4)
        self._handlers = threading.Condition()
        self._active_handlers, self._closing_handlers = 0, False
        self.handler_limit_rejections = 0
        socketserver.TCPServer.__init__(self, address, _TypedHandler)


class SupervisionTelemetryPublisher(OwnerTelemetryPublisher):
    def __init__(self, runtime, address, key, period=.2, role="supervision",
                 vi_address=VI_ADDRESS, **options):
        if role != "supervision" or vi_address != VI_ADDRESS:
            raise ValueError("Fixed SuperVision role and loopback typed ingress required")
        OwnerTelemetryPublisher.__init__(self, runtime, address, key, period, role, **options)
        self.vi_address, self.vi_server, self.vi_worker = vi_address, None, None
        self._vi_counter = self._vi_string = self._vi_video = None
        self._typed_session, self._typed_sequence, self._typed_digest = None, 0, None
        self._retired_sources = set()
        self._retired_captures = set()
        self._last_typed_receipt = None
        self._video_identity_sent, self._bridge_video_sent_at = None, None
        self._bridge_generation, self._published_generation = 0, -1
        self._native_video_sent_at = None
        self.typed_accepted, self.typed_duplicates = 0, 0

    def _aged(self, item):
        if item is None:
            return None
        value, received = item
        value = copy.deepcopy(value)
        value["source_age_seconds"] += max(0., self.clock() - received)
        return value

    def _transform(self, packet, age, projection):
        if packet["producer_kind"] != "copied_acquisition":
            # Native callbacks were captured under the runtime lock before
            # this publisher lock. No card/runtime callback is made here.
            records = {row["publication"]: dict(copy.deepcopy(row), source_age_seconds=age)
                       for row in packet["data"]["banks"] if row["publication"] == "C12NI1409"}
            counter, video = projection.get("_supervision_counter_part"), None
            if self._native_video_sent_at is None or self.clock() - self._native_video_sent_at >= 1.:
                video = projection.get("_supervision_video_frame")
                if video is not None:
                    video = copy.deepcopy(video)
                    video.pop("age_seconds", None)
                    video.pop("owner_session_id", None)
                    self._native_video_sent_at = self.clock()
            mode = "PYTHON_NATIVE" if projection.get("resource_count") else "UNAVAILABLE"
            return json.dumps(owner_frame("supervision", packet["session_id"], packet["sequence"], records,
                mode, counter_part=counter, video_frame=video), allow_nan=False, separators=(",", ":"))
        records = {}
        record = self._aged(self._vi_string)
        if record is not None:
            records["C12NI1409"] = record
        video = None
        if self._vi_video is not None:
            candidate = self._aged(self._vi_video)
            identity = (candidate["source_session_id"], candidate["capture_session_id"], candidate["sequence"])
            if (identity != self._video_identity_sent and (self._bridge_video_sent_at is None
                    or self.clock() - self._bridge_video_sent_at >= 1.)):
                video = candidate
                self._video_identity_sent, self._bridge_video_sent_at = identity, self.clock()
        frame = owner_frame("supervision", packet["session_id"], packet["sequence"], records,
            "LABVIEW_BRIDGE", self._aged(self._vi_counter), video_frame=video,
            source_identity=(dict(source="labview_supervision_typed_local", session_id=self._typed_session,
                sequence=self._typed_sequence) if self._typed_session is not None else None))
        return json.dumps(frame, allow_nan=False, separators=(",", ":"))

    def _publish_bridge(self, value):
        packet = standard_packet(value, self.sequence + 1)
        packet["producer_kind"] = "copied_acquisition"
        packet["data"].update(capture_kind="sequential_local_controls",
                               timestamp_origin="xp_receipt_not_card_sample")
        self._enqueue(packet, projection=value)
        self._published_generation = self._bridge_generation
        self.identity = self._identity(value)
        self.mode, self.owner_state_current = "LABVIEW_BRIDGE", True

    def _admit(self):
        # Same lock/order as local Initialize; neither path waits for a driver.
        if not self.runtime._lock.acquire(False):
            raise ValueError("OWNER_STATE_BUSY_VI_NOT_ADMITTED")
        try:
            value = self.view.snapshot()
            if self.stop_event.is_set() or value.get("telemetry_bridge_mode") is not True:
                raise ValueError("VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS")
            return value
        except Exception:
            self.runtime._lock.release()
            raise

    def ingest(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI snapshot ingestion requires IPv4 loopback")
        records = decode_snapshot_xml(raw, self.xml_encoding)
        with self.lock:
            self.last_vi_seen = self.clock()
        value = self._admit()
        try:
            with self.lock:
                stamp = self.clock()
                string, counter = None, None
                for record in records:
                    if record["publication"] == "C12NI1409":
                        string = dict(copy.deepcopy(record), source_age_seconds=0.)
                        if record.get("error", {}).get("status") is True:
                            error = copy.deepcopy(record["error"])
                            error["source"] = error["source"] or "LABVIEW_CONTROL_READ_FAILED"
                            string.update(data=None, lv_type=copy.deepcopy(schemas()["C12NI1409"]), error=error)
                    elif record["publication"] == "C1011NI6602":
                        values = record.get("data")
                        if record.get("error", {}).get("status") is False and isinstance(values, list) and len(values) == 33:
                            counter = dict(values=values[16:32], source_age_seconds=0.,
                                source="observed_labview_control_memory", selector=values[32],
                                pending_selector=values[32] != -1)
                            validate_counter_part(counter)
                # Validate source types before replacing any retained image.
                owner_frame("supervision", value["session_id"], self.sequence + 1,
                    {"C12NI1409": string} if string is not None else {}, "LABVIEW_BRIDGE", counter)
                self._vi_string = (string, stamp) if string is not None else None
                self._vi_counter = (counter, stamp) if counter is not None else None
                self._bridge_generation += 1
                self._publish_bridge(value)
                self.vi_accepted += 1
                self.last_vi_receipt, self.last_error = stamp, ""
                return dict(accepted=True, bank_count=27, forwarded_owner="supervision",
                    sequence=self.sequence, hardware_writes=False, acknowledged_on="xp_ram_not_everest")
        finally:
            self.runtime._lock.release()

    def _retain_video(self, video, stamp):
        candidate = copy.deepcopy(video)
        capture = (candidate["source_session_id"], candidate["capture_session_id"])
        if capture in self._retired_captures:
            raise ValueError("Retired VI camera capture cannot return")
        prior = self._aged(self._vi_video)
        if prior is not None:
            previous = (prior["source_session_id"], prior["capture_session_id"])
            if capture == previous:
                if candidate["sequence"] < prior["sequence"]:
                    raise ValueError("VI camera frame sequence regressed")
                if candidate["sequence"] == prior["sequence"]:
                    identity, old = copy.deepcopy(candidate), copy.deepcopy(prior)
                    identity.pop("source_age_seconds")
                    old.pop("source_age_seconds")
                    if identity != old:
                        raise ValueError("VI camera identity reused with different bytes or metadata")
                    candidate["source_age_seconds"] = max(candidate["source_age_seconds"], prior["source_age_seconds"])
            else:
                if len(self._retired_captures) >= MAX_VI_SESSIONS:
                    raise ValueError("VI camera replay-state capacity reached")
                if candidate["source_age_seconds"] >= 2:
                    return self._vi_video
                self._retired_captures.add(previous)
        return (candidate, stamp)

    def ingest_observation(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI observation ingestion requires IPv4 loopback")
        observation = decode_vi_observation(raw)
        with self.lock:
            self.last_vi_seen = self.clock()
        value = self._admit()
        try:
            with self.lock:
                session, sequence = observation["source_session_id"], observation["sequence"]
                immutable = copy.deepcopy(observation)
                for name in ("counter_part", "video_frame"):
                    if immutable[name] is not None:
                        immutable[name].pop("source_age_seconds")
                digest = hashlib.sha256(canonical(immutable)).hexdigest()
                duplicate = session == self._typed_session and sequence == self._typed_sequence
                if session in self._retired_sources or session == self._typed_session and sequence < self._typed_sequence:
                    raise ValueError("Retired or regressed VI source observation")
                if duplicate:
                    if digest != self._typed_digest:
                        raise ValueError("VI observation identity reused with different data")
                    self.typed_duplicates += 1
                else:
                    if session != self._typed_session:
                        if not any(observation[name] is not None and observation[name]["source_age_seconds"] < 2
                                   for name in ("counter_part", "video_frame")):
                            raise ValueError("New VI source requires a current independent observation")
                        if len(self._retired_sources) >= MAX_VI_SESSIONS:
                            raise ValueError("VI source replay-state capacity reached")
                        if self._typed_session is not None:
                            self._retired_sources.add(self._typed_session)
                        self._vi_counter = self._vi_string = self._vi_video = None
                    stamp = self.clock()
                    video = (self._retain_video(observation["video_frame"], stamp)
                             if observation["video_frame"] is not None else self._vi_video)
                    if observation["counter_part"] is not None:
                        self._vi_counter = (copy.deepcopy(observation["counter_part"]), stamp)
                    self._vi_video = video
                    self._typed_session, self._typed_sequence, self._typed_digest = session, sequence, digest
                    self._bridge_generation += 1
                    self._publish_bridge(value)
                    self.typed_accepted += 1
                self._last_typed_receipt, self.last_vi_receipt, self.last_error = self.clock(), self.clock(), ""
                return dict(accepted=True, duplicate=duplicate, source_session_id=session,
                    source_sequence=sequence, sequence=self.sequence, hardware_writes=False,
                    acknowledged_on="xp_ram_not_everest")
        finally:
            self.runtime._lock.release()

    def note_native_transition(self):
        with self.lock:
            if self._typed_session is not None:
                if len(self._retired_sources) >= MAX_VI_SESSIONS:
                    raise RuntimeError("VI replay-state capacity reached; native transition refused")
                self._retired_sources.add(self._typed_session)
            self._vi_counter = self._vi_string = self._vi_video = None
            self._typed_session, self._typed_sequence, self._typed_digest = None, 0, None
            self._last_typed_receipt = None
            self._retired_captures = set()  # Retired source boots already fence their captures.
            self._video_identity_sent, self._bridge_video_sent_at = None, None
            self._bridge_generation += 1

    def assert_initialize_allowed(self):
        OwnerTelemetryPublisher.assert_initialize_allowed(self)
        with self.lock:
            if self._typed_session is not None and len(self._retired_sources) >= MAX_VI_SESSIONS:
                raise RuntimeError("VI replay-state capacity reached; native transition refused")

    def publish_once(self):
        with self.lock:
            generation, bridge_generation = self.sequence, self._bridge_generation
        if not self.runtime._lock.acquire(False):
            return False  # Lock contention cannot freshen a cached observation.
        try:
            value = self.view.snapshot()
            bridge = value.get("telemetry_bridge_mode") is True
            if not bridge:
                value["_supervision_counter_part"] = self.runtime.counter_memory_part()
                value["_supervision_video_frame"] = self.runtime.video_frame_snapshot()
        finally:
            self.runtime._lock.release()
        # Base64/JSON projection and outbox copies never hold the runtime lock.
        with self.lock:
            if generation != self.sequence or bridge_generation != self._bridge_generation:
                return False  # New ingress or a native admission invalidated capture.
            if not bridge:
                identity = self._identity(value)
                if identity == self.identity:
                    return False
                packet = standard_packet(value, self.sequence + 1)
                self._enqueue(packet, packet_age_seconds(value, packet), value)
                self.identity = identity
                self.mode = "PYTHON_NATIVE" if value.get("resource_count") else "TRANSITION_OR_FAULT"
                self.owner_state_current = value.get("telemetry_view_current") is True
                return True
            candidate = self._aged(self._vi_video)
            image_pending = (candidate is not None and
                (candidate["source_session_id"], candidate["capture_session_id"], candidate["sequence"]) != self._video_identity_sent
                and (self._bridge_video_sent_at is None or self.clock() - self._bridge_video_sent_at >= 1.))
            if (self._identity(value) == self.identity and self._published_generation == self._bridge_generation
                    and not image_pending):
                return False
            self._publish_bridge(value)
            return True

    def start(self):
        if self.vi_server is not None or self.stop_event.is_set():
            raise RuntimeError("SuperVision telemetry cannot start twice")
        self.vi_server = SupervisionVIServer(self.vi_address, self)
        self.vi_worker = threading.Thread(target=lambda: self.vi_server.serve_forever(poll_interval=.1),
                                          name="SUPERVISION-VI-typed-ingress")
        self.vi_worker.daemon = True
        try:
            self.vi_worker.start()
            OwnerTelemetryPublisher.start(self)
        except Exception:
            self.close()
            raise

    def close(self):
        self.stop_event.set()
        if self.vi_server is not None:
            if self.vi_worker is not None and self.vi_worker.is_alive():
                self.vi_server.shutdown()
                self.vi_worker.join(3)
                if self.vi_worker.is_alive():
                    raise RuntimeError("SuperVision typed ingress remains owned")
            self.vi_server.server_close()
            self.vi_server = None
        OwnerTelemetryPublisher.close(self)

    def status(self):
        result = OwnerTelemetryPublisher.status(self)
        with self.lock:
            result.update(vi_typed_endpoint="127.0.0.1:8768", vi_typed_accepted=self.typed_accepted,
                vi_typed_duplicates=self.typed_duplicates, vi_source_session_id=self._typed_session,
                vi_source_sequence=self._typed_sequence,
                vi_typed_age_seconds=None if self._last_typed_receipt is None else max(0., self.clock() - self._last_typed_receipt),
                vi_producer_qualification="native_helper_not_authored_or_qualified",
                vi_xml_counter_timestamp_origin="local_receipt_observed_control_memory")
        return result
