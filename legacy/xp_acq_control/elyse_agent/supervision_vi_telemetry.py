"""SuperVision VI/native telemetry in one application/publisher, Python 3.4.

Counter-only XML and legacy27 XML use 127.0.0.1:8766. Typed observations
use 127.0.0.1:8768, four-byte big-endian length then strict UTF-8 JSON or the
versioned fixed native camera cluster. Native
LabVIEW producers still require authoring/qualification; no VI is generated.
Counter memory, opaque C12 String and raw images retain independent ages.
"""
import copy
import base64
import datetime
import hashlib
import json
import socketserver
import struct
import threading
import time

from .federation_wire import (finite, hex_id, owner_frame, MAX_VIDEO_RAW_BYTES,
                              validate_counter_part, validate_video_frame)
from .orchestrator_publisher import OwnerTelemetryPublisher
from .protocol import recv_exact, send_message
from .shared_state import decode_supervision_snapshot_xml
from .shared_state_receiver import SharedStateServer
from .standard_banks import standard_packet, schemas, packet_age_seconds
from .telemetry_relay import DeadlineSocket, canonical


PUBLICATION = "ELYSE_SUPERVISION_VI_OBSERVATION"
VI_ADDRESS = ("127.0.0.1", 8768)
MAX_VI_BYTES = 900 * 1024
MAX_VI_SESSIONS = 64
BINARY_CAMERA_MAGIC = b"ELYSE_SUP_CAM_BIN"
BINARY_CAMERA_PREFIX = struct.pack("!I", len(BINARY_CAMERA_MAGIC)) + BINARY_CAMERA_MAGIC
BINARY_CAMERA_HEADER_BYTES = len(BINARY_CAMERA_PREFIX) + 2 + 3 * 16 + 4 * 4 + 2 * 4
MAX_BINARY_CAMERA_BYTES = BINARY_CAMERA_HEADER_BYTES + MAX_VIDEO_RAW_BYTES
LABVIEW_UNIX_OFFSET = 2082844800
FRACTION_SCALE = 1 << 64


def _binary_camera_header(raw, total_size):
    """Validate fixed geometry before reading/allocating an image payload.

Native qualification must prove FlattenToString big-endian data string,
included String/2D-array sizes, no type descriptor and no cluster padding.
"""
    if (type(raw) is not bytes or len(raw) != BINARY_CAMERA_HEADER_BYTES
            or type(total_size) is not int or not BINARY_CAMERA_HEADER_BYTES < total_size <= MAX_BINARY_CAMERA_BYTES
            or not raw.startswith(BINARY_CAMERA_PREFIX)):
        raise ValueError("Invalid native camera cluster size or magic")
    offset = len(BINARY_CAMERA_PREFIX)
    version = struct.unpack_from("!H", raw, offset)[0]
    if version != 1:
        raise ValueError("Unknown native camera cluster version")
    offset += 2
    stamps = []
    for unused in range(3):
        encoded = raw[offset:offset + 16]
        seconds, fraction = struct.unpack("!qQ", encoded)
        if seconds == 0 and fraction == 0:
            raise ValueError("Native camera epochs/observation must be explicit nonzero timestamps")
        stamps.append((seconds, fraction, encoded))
        offset += 16
    frame_count, channel, copy_elapsed_ms, observed_tick_ms, rows, columns = struct.unpack_from("!IIIIii", raw, offset)
    if (not 0 <= channel <= 3 or not 1 <= rows <= MAX_VIDEO_RAW_BYTES
            or not 1 <= columns <= MAX_VIDEO_RAW_BYTES or rows * columns > MAX_VIDEO_RAW_BYTES
            or total_size != BINARY_CAMERA_HEADER_BYTES + rows * columns):
        raise ValueError("Invalid native U8 geometry/channel or trailing image bytes")
    fixed = [(seconds << 64) + fraction for seconds, fraction, unused in stamps]
    if not fixed[0] <= fixed[1] <= fixed[2]:
        raise ValueError("Native run/capture/observation clock order regressed")
    return dict(stamps=stamps, fixed=fixed, frame_count=frame_count, channel=channel,
                copy_elapsed_ms=copy_elapsed_ms, observed_tick_ms=observed_tick_ms, rows=rows, columns=columns)


def _windows_tick_count():
    # This is a local read-only OS clock, not an NI call. No API is loaded on
    # module import. Never replace an unknown native clock with receipt time.
    import ctypes
    if not hasattr(ctypes, "windll"):
        raise ValueError("Win32 camera tick clock is not available on this host")
    function = ctypes.windll.kernel32.GetTickCount
    function.argtypes, function.restype = [], ctypes.c_uint32
    return int(function())


def decode_vi_camera_binary(raw, now_seconds=None, now_ticks=None):
    """Normalize a bounded native owned-byte observation into unchanged JSON.

Run/capture IDs preserve exact native Timestamp128 bytes. Age includes VI queue
    and loopback transfer on this SAME XP host. Wall and Win32 tick ages must
    BOTH be current; the conservative maximum prevents wall-clock rollback
    from freshening an old queued frame. Future/stale/unknown clocks fail
closed; neither new receipt time nor a repeated FrameCount freshens an image.
"""
    if type(raw) is not bytes or not BINARY_CAMERA_HEADER_BYTES < len(raw) <= MAX_BINARY_CAMERA_BYTES:
        raise ValueError("Bounded native U8 camera cluster required")
    header = _binary_camera_header(raw[:BINARY_CAMERA_HEADER_BYTES], len(raw))
    now = time.time() if now_seconds is None else now_seconds
    if not finite(now):
        raise ValueError("Known finite same-host camera clock required")
    run, capture, observed = header["stamps"]
    now_whole = int(now // 1)
    age = ((now_whole + LABVIEW_UNIX_OFFSET - observed[0])
           + (now - now_whole) - observed[1] / FRACTION_SCALE)
    if not 0 <= age < 2:
        raise ValueError("Native camera observation is stale or in the future; same-host clock not qualified")
    ticks = _windows_tick_count() if now_ticks is None else now_ticks
    if type(ticks) is not int or not 0 <= ticks <= 4294967295:
        raise ValueError("Known unsigned Win32 camera tick clock required")
    tick_age = ((ticks - header["observed_tick_ms"]) & 4294967295) / 1000.
    if not 0 <= tick_age < 2:
        raise ValueError("Native camera monotonic age is stale/future or its tick clock is not qualified")
    age = max(age, tick_age)
    sequence = ((header["fixed"][2] - header["fixed"][0]) * 1000000) // FRACTION_SCALE + 1
    if not 1 <= sequence <= 9007199254740991:
        raise ValueError("Native camera observation sequence is outside the source-run bound")
    copy_elapsed = header["copy_elapsed_ms"] / 1000.
    if copy_elapsed > age:
        raise ValueError("Native camera copy duration exceeds its source age")
    try:
        observed_utc = (datetime.datetime(1904, 1, 1, tzinfo=datetime.timezone.utc)
            + datetime.timedelta(seconds=observed[0], microseconds=(observed[1] * 1000000) // FRACTION_SCALE)).isoformat()
    except (OverflowError, ValueError):
        raise ValueError("Native camera observation timestamp outside supported UTC range")
    source = run[2].hex() if hasattr(run[2], "hex") else ''.join('{:02x}'.format(value) for value in bytearray(run[2]))
    capture_id = (capture[2].hex() if hasattr(capture[2], "hex")
                  else ''.join('{:02x}'.format(value) for value in bytearray(capture[2])))
    value = dict(schema_version=1, publication=PUBLICATION, source_session_id=source,
        sequence=sequence, source_running=True, counter_part=None,
        video_frame=dict(source="labview_supervision_ni1409", source_session_id=source,
            simulated=False, sequence=header["frame_count"] + 1,
            sequence_interpretation="software grab observation, not hardware frame counter",
            capture_session_id=capture_id, observed_utc=observed_utc,
            sample_elapsed_seconds=copy_elapsed, source_age_seconds=age,
            width=header["columns"], height=header["rows"], pixel_type="U8",
            encoding="base64_raw_row_major", data=base64.b64encode(raw[BINARY_CAMERA_HEADER_BYTES:]).decode("ascii"),
            channel=header["channel"], processing="raw_grab_before_legacy_interlace_bcg_profiles",
            hardware_acknowledged=False))
    validate_vi_observation(value)
    return value


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
            prefix = recv_exact(bounded, min(size, len(BINARY_CAMERA_PREFIX)))
            if prefix == BINARY_CAMERA_PREFIX:
                if not BINARY_CAMERA_HEADER_BYTES < size <= MAX_BINARY_CAMERA_BYTES:
                    raise ValueError("Native camera frame exceeds bounded payload")
                header = prefix + recv_exact(bounded, BINARY_CAMERA_HEADER_BYTES - len(prefix))
                _binary_camera_header(header, size)  # Reject bad dimensions before reading pixels.
                raw = header + recv_exact(bounded, size - BINARY_CAMERA_HEADER_BYTES)
            else:
                raw = prefix + recv_exact(bounded, size - len(prefix))
            result = self.server.store.ingest_observation(raw, self.client_address[0])
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
                 vi_address=VI_ADDRESS, wall_clock=None, tick_clock=None, **options):
        if role != "supervision" or vi_address != VI_ADDRESS:
            raise ValueError("Fixed SuperVision role and loopback typed ingress required")
        OwnerTelemetryPublisher.__init__(self, runtime, address, key, period, role, **options)
        self.wall_clock = wall_clock or time.time
        self.tick_clock = tick_clock or _windows_tick_count
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
        records = decode_supervision_snapshot_xml(raw, self.xml_encoding)
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
                return dict(accepted=True, bank_count=len(records), forwarded_owner="supervision",
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
        observation = (decode_vi_camera_binary(raw, self.wall_clock(), self.tick_clock())
                       if type(raw) is bytes and raw.startswith(BINARY_CAMERA_PREFIX) else decode_vi_observation(raw))
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
        # This object exists only for explicitly enabled telemetry. Delivery
        # errors/ACK counters describe link health separately; they must not
        # make the GUI mistake an instantiated publisher for disabled config.
        result = dict(OwnerTelemetryPublisher.status(self), enabled=True)
        with self.lock:
            result.update(vi_typed_endpoint="127.0.0.1:8768", vi_typed_accepted=self.typed_accepted,
                vi_typed_duplicates=self.typed_duplicates, vi_source_session_id=self._typed_session,
                vi_source_sequence=self._typed_sequence,
                vi_typed_age_seconds=None if self._last_typed_receipt is None else max(0., self.clock() - self._last_typed_receipt),
                vi_producer_qualification="native_helper_not_authored_or_qualified",
                vi_xml_counter_timestamp_origin="local_receipt_observed_control_memory")
        return result
