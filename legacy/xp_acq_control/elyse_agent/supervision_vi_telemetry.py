"""SuperVision VI/native telemetry in one application/publisher, Python 3.4.

Counter-only XML and legacy27 XML use 127.0.0.1:8766. Typed observations
use 127.0.0.1:8768, four-byte big-endian length then strict UTF-8 JSON or the
versioned fixed native camera cluster. Native
LabVIEW producers still require authoring/qualification; no VI is generated.
Typed TCP connections accept ordered framed observations until EOF/idle/error;
each observation and its local ACK retain an independent absolute deadline.
Counter memory, opaque C12 String and raw images retain independent ages.
"""
import copy
import base64
import datetime
import hashlib
import json
import socket
import socketserver
import struct
import threading
import time

from .federation_wire import (finite, hex_id, owner_frame, MAX_VIDEO_RAW_BYTES,
                              validate_counter_part, validate_video_frame)
from .orchestrator_publisher import OwnerTelemetryPublisher
from .protocol import recv_exact, send_message
from .shared_state import decode_supervision_snapshot_xml, LatestSnapshotOutbox
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
# GetTickCount on XP has 10--16ms resolution. The native LV timer was measured
# 1--6ms ahead on this host. Admit only that bounded quantization window and
# charge its full uncertainty to age; do not extend the two-second deadline.
NATIVE_TICK_UNCERTAINTY_MS = 16
VI_IDLE_TIMEOUT_SECONDS = 2.
VI_FRAME_TIMEOUT_SECONDS = 2.


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
    if (not 0 <= channel <= 4294967295 or not 1 <= rows <= MAX_VIDEO_RAW_BYTES
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


def _decode_vi_camera_pixels(raw, now_seconds=None, now_ticks=None):
    """Validate native clocks/geometry and retain owned pixels without JSON.

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
    signed_ms = ((ticks - header["observed_tick_ms"] + 2147483648) & 4294967295) - 2147483648
    if signed_ms < -NATIVE_TICK_UNCERTAINTY_MS or signed_ms + NATIVE_TICK_UNCERTAINTY_MS >= 2000:
        raise ValueError("Native camera monotonic age is stale/future or its tick clock is not qualified: "
                         "delta_ms={}, wall_age_seconds={:.6f}, receiver_ticks={}, observed_ticks={}".format(
                             signed_ms, age, ticks, header["observed_tick_ms"]))
    age = max(age, signed_ms / 1000.) + NATIVE_TICK_UNCERTAINTY_MS / 1000.
    if age >= 2:
        raise ValueError('Native camera age plus timer uncertainty exceeds the two-second deadline')
    # FrameCount is the native growing identifier. Timestamps describe age,
    # never the delivery/replay order. Count resets are scoped by capture ID.
    sequence = header["frame_count"] + 1
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
            encoding="base64_raw_row_major", data=raw[BINARY_CAMERA_HEADER_BYTES:],
            channel=header["channel"], processing="raw_grab_before_legacy_interlace_bcg_profiles",
            hardware_acknowledged=False))
    return value


def decode_vi_camera_binary(raw, now_seconds=None, now_ticks=None):
    """Public legacy normalization retains its exact validated JSON schema."""
    value = _decode_vi_camera_pixels(raw, now_seconds, now_ticks)
    video = value['video_frame']
    video['data'] = base64.b64encode(video['data']).decode('ascii')
    validate_vi_observation(value)
    return value


def _observation_digest(observation):
    """Same identity for native bytes and their equivalent legacy JSON form."""
    immutable = copy.deepcopy(observation)
    pixels = b''
    for name in ('counter_part', 'video_frame'):
        part = immutable[name]
        if part is not None:
            part.pop('source_age_seconds')
            if name == 'video_frame':
                pixels = part.pop('data')
                if type(pixels) is str:
                    pixels = base64.b64decode(pixels.encode('ascii'), validate=True)
    return hashlib.sha256(canonical(immutable) + b'\x00' + hashlib.sha256(pixels).digest()).hexdigest()


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
    def _read_frame(self, bounded, header):
        """One framed observation; malformed framing cannot be resynchronized."""
        header += recv_exact(bounded, 4 - len(header))
        size = struct.unpack("!I", header)[0]
        if not 1 <= size <= MAX_VI_BYTES:
            raise ValueError("Invalid SuperVision VI frame length")
        prefix = recv_exact(bounded, min(size, len(BINARY_CAMERA_PREFIX)))
        if prefix != BINARY_CAMERA_PREFIX:
            return prefix + recv_exact(bounded, size - len(prefix))
        if not BINARY_CAMERA_HEADER_BYTES < size <= MAX_BINARY_CAMERA_BYTES:
            raise ValueError("Native camera frame exceeds bounded payload")
        header = prefix + recv_exact(bounded, BINARY_CAMERA_HEADER_BYTES - len(prefix))
        _binary_camera_header(header, size)  # Reject bad dimensions before reading pixels.
        return header + recv_exact(bounded, size - BINARY_CAMERA_HEADER_BYTES)

    def _rejection(self, error):
        with self.server.store.lock:
            self.server.store.rejected += 1
            self.server.store.last_error = str(error)[:300]
        return dict(id="supervision-vi", ok=False,
            error=dict(code="snapshot_rejected", message=str(error)[:300]))

    def _send_reply(self, bounded, reply):
        try:
            send_message(bounded, reply, 16384)
        except Exception:
            return False  # A local RAM ACK does not imply receipt or Everest durability.
        return True

    def handle(self):
        if self.client_address[0] != "127.0.0.1":
            return
        while not getattr(self.server, "_closing_handlers", False):
            # Old one-frame clients may close after their ACK. An idle/closed
            # connection has not submitted a new observation, so is not a loss.
            idle = DeadlineSocket(self.request, time.monotonic() + VI_IDLE_TIMEOUT_SECONDS)
            try:
                header = idle.recv(4)
            except (socket.timeout, OSError):
                return
            if not header or getattr(self.server, "_closing_handlers", False):
                return
            # Renew only at a frame boundary, never for each partial recv. Idle
            # time between frames must not consume the next frame's deadline.
            bounded = DeadlineSocket(self.request, time.monotonic() + VI_FRAME_TIMEOUT_SECONDS)
            try:
                raw = self._read_frame(bounded, header)
            except Exception as error:
                self._send_reply(bounded, self._rejection(error))
                return  # Unread payload bytes cannot become the next length.
            try:
                result = self.server.store.ingest_observation(raw, self.client_address[0])
                reply = dict(id="supervision-vi", ok=True, result=result)
            except Exception as error:
                # The complete frame was consumed: a rejected observation does
                # not corrupt the boundary of the following framed observation.
                reply = self._rejection(error)
            if not self._send_reply(bounded, reply):
                return


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

    def get_request(self):
        connection, address = socketserver.TCPServer.get_request(self)
        try:
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            connection.close()
            raise
        return connection, address


class _VideoDeliveryOutbox(LatestSnapshotOutbox):
    """Notify only after matching ACK; release the queue lock before callback."""
    def __init__(self, on_delivered, **options):
        LatestSnapshotOutbox.__init__(self, **options)
        self.on_delivered = on_delivered

    def acknowledge(self, relay_id, message_id):
        with self._lock:
            packet = json.loads(self._inflight[1]) if self._inflight is not None else None
            LatestSnapshotOutbox.acknowledge(self, relay_id, message_id)
        self.on_delivered(packet)


class SupervisionTelemetryPublisher(OwnerTelemetryPublisher):
    def __init__(self, runtime, address, key, period=.2, role="supervision",
                 vi_address=VI_ADDRESS, wall_clock=None, tick_clock=None,
                 camera_stream_configuration=None, **options):
        if role != "supervision" or vi_address != VI_ADDRESS:
            raise ValueError("Fixed SuperVision role and loopback typed ingress required")
        OwnerTelemetryPublisher.__init__(self, runtime, address, key, period, role, **options)
        self.wall_clock = wall_clock or time.time
        self.tick_clock = tick_clock or _windows_tick_count
        self.vi_address, self.vi_server, self.vi_worker = vi_address, None, None
        self._vi_counter = self._vi_string = self._vi_video = None
        self._typed_session, self._typed_sequence, self._typed_digest = None, 0, None
        self._native_observations = {}
        self._retired_sources = set()
        self._retired_captures = set()
        self._last_typed_receipt = None
        self._video_identity_sent, self._bridge_video_sent_at = None, None
        self._bridge_generation, self._published_generation = 0, -1
        self._native_video_sent_at = None
        self.typed_accepted, self.typed_duplicates = 0, 0
        self.outbox = _VideoDeliveryOutbox(self._video_delivered, clock=self.clock,
                                         max_encoded_bytes=900 * 1024)
        self.relay.outbox = self.outbox  # No relay thread has started yet.
        self.camera_stream = None
        self._stream_videos, self._stream_retired = {}, {}
        self._stream_stale_capture_skipped = 0
        if camera_stream_configuration is not None:
            from .camera_stream_publisher import CameraStreamPublisher, validate_camera_stream_configuration
            stream_config = validate_camera_stream_configuration(camera_stream_configuration)
            if stream_config is not None:
                self.camera_stream = CameraStreamPublisher(stream_config, key, clock=self.clock)

    @property
    def independent_native_video(self):
        return bool(self.camera_stream is not None
                    and self.camera_stream.config['source_mode'] == 'VI_OR_NATIVE')

    def offer_native_video(self, video):
        """Private runtime-owned append, never a public/VI ingress operation."""
        if not self.independent_native_video:
            return False
        return self.camera_stream.submit_python_video(video, self.runtime._identity['session_id'], self.clock())

    def _video_delivered(self, packet):
        video = packet.get("video_frame")
        if video is None:
            return
        with self.lock:
            if packet["source_mode"] == "LABVIEW_BRIDGE":
                if video["source_session_id"] != self._typed_session:
                    return  # An ACK from a retired VI cannot suppress its successor.
                self._video_identity_sent = (video["source_session_id"],
                    video["capture_session_id"], video["sequence"])
                self._bridge_video_sent_at = self.clock()
            elif packet["source_mode"] == "PYTHON_NATIVE" and self._typed_session is None:
                self._native_video_sent_at = self.clock()

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
            if not self.independent_native_video and (self._native_video_sent_at is None
                    or self.clock() - self._native_video_sent_at >= 1.):
                video = projection.get("_supervision_video_frame")
                if video is not None:
                    video = copy.deepcopy(video)
                    video.pop("age_seconds", None)
                    video.pop("owner_session_id", None)
            mode = "PYTHON_NATIVE" if projection.get("resource_count") else "UNAVAILABLE"
            return json.dumps(owner_frame("supervision", packet["session_id"], packet["sequence"], records,
                mode, counter_part=counter, video_frame=video), allow_nan=False, separators=(",", ":"))
        frame = self._bridge_frame(packet['session_id'], packet['sequence'])
        return json.dumps(frame, allow_nan=False, separators=(",", ":"))

    def _bridge_frame(self, session_id, sequence):
        """The existing SuperVision wire contains its own bank and counter only."""
        records = {}
        record = self._aged(self._vi_string)
        if record is not None:
            records["C12NI1409"] = record
        video = None
        if self.camera_stream is None and self._vi_video is not None:
            candidate = self._aged(self._vi_video)
            identity = (candidate["source_session_id"], candidate["capture_session_id"], candidate["sequence"])
            if (identity != self._video_identity_sent and (self._bridge_video_sent_at is None
                    or self.clock() - self._bridge_video_sent_at >= 1.)):
                video = candidate
                # Pending snapshots can be replaced before transport selects
                # one. Keep the current image eligible until a matching ACK;
                # enqueueing alone must not spend the one-second video budget.
        return owner_frame("supervision", session_id, sequence, records,
            "LABVIEW_BRIDGE", self._aged(self._vi_counter), video_frame=video,
            source_identity=(dict(source="labview_supervision_typed_local", session_id=self._typed_session,
                sequence=self._typed_sequence) if self._typed_session is not None else None))

    def _publish_bridge(self, value):
        if self.camera_stream is not None:
            frame = self._bridge_frame(value['session_id'], self.sequence + 1)
            self.outbox.enqueue(json.dumps(frame, allow_nan=False, separators=(',', ':')),
                datetime.datetime.now(datetime.timezone.utc).isoformat())
            self.sequence, self.error = frame['sequence'], ''
        else:
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

    def _retain_stream_video(self, video, stamp):
        """Separate channel replay state; camera2 must not retire camera1."""
        channel = video['channel']
        if channel not in self._stream_videos and len(self._stream_videos) >= self.camera_stream.config['max_channels']:
            raise ValueError('Independent VI camera channel bound reached')
        candidate = copy.deepcopy(video)
        capture = candidate['source_session_id'], candidate['capture_session_id']
        retired = self._stream_retired.setdefault(channel, set())
        if capture in retired:
            raise ValueError('Retired independent VI camera capture cannot return')
        prior = self._aged(self._stream_videos.get(channel))
        if prior is not None:
            previous = prior['source_session_id'], prior['capture_session_id']
            if capture == previous:
                if candidate['sequence'] < prior['sequence']:
                    raise ValueError('Independent VI camera sequence regressed')
                if candidate['sequence'] == prior['sequence']:
                    before, after = dict(prior), dict(candidate)
                    before.pop('source_age_seconds')
                    after.pop('source_age_seconds')
                    if before != after:
                        raise ValueError('Independent VI camera identity reused with different data')
                    return False
            else:
                if len(retired) >= MAX_VI_SESSIONS:
                    raise ValueError('Independent VI camera replay history bound reached')
                if candidate['source_age_seconds'] >= 2:
                    self._stream_stale_capture_skipped += 1
                    return False
                retired.add(previous)
        self._stream_videos[channel] = candidate, stamp
        return True

    def ingest_observation(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("VI observation ingestion requires IPv4 loopback")
        native = type(raw) is bytes and raw.startswith(BINARY_CAMERA_PREFIX)
        native_pixels = native and self.camera_stream is not None
        if native:
            decode = _decode_vi_camera_pixels if native_pixels else decode_vi_camera_binary
            observation = decode(raw, self.wall_clock(), self.tick_clock())
        else:
            observation = decode_vi_observation(raw)
        decoded_at = self.clock()
        # Canonical image hashing is outside runtime/publisher admission locks.
        digest = _observation_digest(observation)
        with self.lock:
            self.last_vi_seen = self.clock()
        value = self._admit()
        try:
            with self.lock:
                session, sequence = observation["source_session_id"], observation["sequence"]
                staged = None
                duplicate = session == self._typed_session and sequence == self._typed_sequence
                if native:
                    video = observation['video_frame']
                    native_identity = (session, video['capture_session_id'], sequence)
                    prior_native = self._native_observations.get(video['channel'])
                    same_capture = prior_native is not None and prior_native[:2] == native_identity[:2]
                    duplicate = same_capture and prior_native[2] == sequence
                    if same_capture and sequence < prior_native[2]:
                        raise ValueError('Native camera FrameCount regressed within capture')
                    if video['channel'] not in self._native_observations and len(self._native_observations) >= 4:
                        raise ValueError('Native camera replay channel bound reached')
                if session in self._retired_sources or (not native and session == self._typed_session
                                                        and sequence < self._typed_sequence):
                    raise ValueError("Retired or regressed VI source observation")
                if duplicate:
                    previous_digest = prior_native[3] if native else self._typed_digest
                    if digest != previous_digest:
                        raise ValueError("VI observation identity reused with different data")
                    self.typed_duplicates += 1
                else:
                    new_source = session != self._typed_session
                    if new_source:
                        if not any(observation[name] is not None and observation[name]["source_age_seconds"] < 2
                                   for name in ("counter_part", "video_frame")):
                            raise ValueError("New VI source requires a current independent observation")
                        if len(self._retired_sources) >= MAX_VI_SESSIONS:
                            raise ValueError("VI source replay-state capacity reached")
                        if self._typed_session is not None:
                            self._retired_sources.add(self._typed_session)
                        self._vi_counter = self._vi_string = self._vi_video = None
                        self._stream_videos, self._stream_retired = {}, {}
                        self._native_observations = {}
                    stamp = self.clock()
                    stream_new = False
                    if self.camera_stream is not None:
                        if observation['video_frame'] is not None:
                            stream_new = self._retain_stream_video(observation['video_frame'], stamp)
                        video = None
                    else:
                        video = (self._retain_video(observation["video_frame"], stamp)
                                 if observation["video_frame"] is not None else self._vi_video)
                    if observation["counter_part"] is not None:
                        self._vi_counter = (copy.deepcopy(observation["counter_part"]), stamp)
                    self._vi_video = video
                    self._typed_session, self._typed_sequence, self._typed_digest = session, sequence, digest
                    if native:
                        self._native_observations[observation['video_frame']['channel']] = native_identity + (digest,)
                    self._bridge_generation += 1
                    # Independent camera RAM admission must not rebuild and
                    # validate all 27 banks for every image. The existing owner
                    # publisher observes the changed generation separately.
                    # Counter observations and first-source publication keep
                    # their synchronous metadata behavior.
                    if self.camera_stream is None or observation['counter_part'] is not None or new_source:
                        self._publish_bridge(value)
                    self.typed_accepted += 1
                    if stream_new:
                        # Only bounded immutable descriptor staging under these
                        # locks; decode/compression/socket work is independent.
                        submit = (self.camera_stream.submit_native_video if native_pixels
                                  else self.camera_stream.submit_video)
                        staged = submit(observation['video_frame'], decoded_at)
                self._last_typed_receipt, self.last_vi_receipt, self.last_error = self.clock(), self.clock(), ""
                result = dict(accepted=True, duplicate=duplicate, source_session_id=session,
                    source_sequence=sequence, sequence=self.sequence, hardware_writes=False,
                    acknowledged_on="xp_ram_not_everest")
                if self.camera_stream is not None:
                    result.update(independent_camera_enabled=True, independent_camera_staged=staged)
                return result
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
            self._native_observations = {}
            self._last_typed_receipt = None
            self._retired_captures = set()  # Retired source boots already fence their captures.
            self._stream_videos, self._stream_retired = {}, {}
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
                if not self.independent_native_video:
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
            if self.camera_stream is not None:
                self.camera_stream.start()
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
        if self.camera_stream is not None and not self.camera_stream.close():
            raise RuntimeError('Independent camera publisher remains owned')
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
        if self.camera_stream is not None:
            result.update(independent_camera=self.camera_stream.status(),
                independent_camera_source=('current_vi_or_python_owner' if self.independent_native_video
                                           else 'accepted_typed_labview_only'),
                independent_camera_stale_capture_skipped=self._stream_stale_capture_skipped,
                raw_video_transport=('independent_binary_camera_v2' if self.independent_native_video
                                     else 'independent_binary_camera_v2_for_vi'),
                raw_video_period_seconds=None,
                native_video_period_seconds=None if self.independent_native_video else 1.,
                native_video_transport=('independent_binary_camera_v2' if self.independent_native_video
                                        else 'unchanged_legacy_owner_video'))
        return result
