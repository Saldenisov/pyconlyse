"""Independent bounded binary camera FIFO/transport, CPython3.4 stdlib.

Explicit construction/start only. No NI, telemetry/SQL archive or Tango imports.
Producer never performs compression/network I/O. One consumer owns a persistent
connection and removes the FIFO head only after its authenticated matching ACK.
This is a transport component, not yet connected to the sampled native VI.
"""
from collections import deque
import copy
import datetime
import hashlib
import hmac
import json
import math
import socket
import struct
import threading
import time
import uuid
import zlib

from .protocol import recv_exact, recv_message, send_message
from .telemetry_relay import DeadlineSocket, canonical, sign
from .supervision_wire import validate_key


MAGIC = b'ELYSE_CAMERA_BINARY_2\x00'
MAX_RAW = 524288
MAX_METADATA = 4096
MAX_PAYLOAD = MAX_RAW + 1024  # zlib worst case at the admitted raw bound
MAX_SEQUENCE = 9007199254740991
FIELDS = {'capture_session_id', 'sequence', 'observed_utc', 'width', 'height',
          'channel', 'source_age_seconds'}


def _hex(value):
    return (type(value) is str and len(value) == 32
            and all(letter in '0123456789abcdef' for letter in value))


def _age(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_frame(metadata, pixels):
    if type(metadata) is not dict or set(metadata) not in (FIELDS, FIELDS | {'source_session_id'}):
        raise ValueError('Exact U8 camera metadata required')
    if 'source_session_id' in metadata and not _hex(metadata['source_session_id']):
        raise ValueError('Actual camera source-run identity required')
    if not _hex(metadata['capture_session_id']):
        raise ValueError('Capture session required')
    if type(metadata['sequence']) is not int or not 1 <= metadata['sequence'] <= MAX_SEQUENCE:
        raise ValueError('Positive source observation sequence required')
    if (type(metadata['width']) is not int or type(metadata['height']) is not int
            or metadata['width'] < 1 or metadata['height'] < 1
            or metadata['width'] * metadata['height'] > MAX_RAW):
        raise ValueError('Bounded positive image dimensions required')
    if type(metadata['channel']) is not int or not 0 <= metadata['channel'] <= 4294967295:
        raise ValueError('Actual unsigned channel metadata required')
    if not _age(metadata['source_age_seconds']):
        raise ValueError('Finite nonnegative image age required')
    if (type(metadata['observed_utc']) is not str or len(metadata['observed_utc']) > 64
            or not metadata['observed_utc'].endswith(('+00:00', 'Z'))):
        raise ValueError('UTC observation label required')
    label = metadata['observed_utc'].replace('Z', '+00:00')
    try:
        datetime.datetime.strptime(label, '%Y-%m-%dT%H:%M:%S.%f+00:00')
    except ValueError:
        datetime.datetime.strptime(label, '%Y-%m-%dT%H:%M:%S+00:00')
    if type(pixels) is not bytes or len(pixels) != metadata['width'] * metadata['height']:
        raise ValueError('Immutable owned U8 row-major bytes required')


def encode_frame(metadata, pixels, stream_id, message_id, nonce, key):
    validate_frame(metadata, pixels)
    if not _hex(stream_id) or not _hex(nonce) or type(message_id) is not int or not 1 <= message_id <= MAX_SEQUENCE:
        raise ValueError('Bounded stream identity required')
    payload = zlib.compress(pixels, 1)
    header = canonical(dict(frame=metadata, stream_id=stream_id, message_id=message_id,
                            nonce=nonce, codec='zlib_u8_v1'))
    if len(header) > MAX_METADATA or len(payload) > MAX_PAYLOAD:
        raise ValueError('Camera envelope exceeds bounded size')
    value = MAGIC + struct.pack('!II', len(header), len(payload)) + header + payload
    return value + hmac.new(validate_key(key), value, hashlib.sha256).digest()


def receive_frame(connection, key):
    prefix = recv_exact(connection, len(MAGIC) + 8)
    if prefix[:len(MAGIC)] != MAGIC:
        raise ValueError('Unknown camera stream')
    header_size, payload_size = struct.unpack('!II', prefix[-8:])
    if not 0 < header_size <= MAX_METADATA or not 0 < payload_size <= MAX_PAYLOAD:
        raise ValueError('Camera envelope exceeds bounded size')
    data = recv_exact(connection, header_size + payload_size)
    signature = recv_exact(connection, 32)
    if not hmac.compare_digest(signature, hmac.new(validate_key(key), prefix + data, hashlib.sha256).digest()):
        raise ValueError('Camera frame authentication failed')
    header = json.loads(data[:header_size].decode('ascii'))
    if (type(header) is not dict or set(header) != {'frame', 'stream_id', 'message_id', 'nonce', 'codec'}
            or header['codec'] != 'zlib_u8_v1' or not _hex(header['stream_id']) or not _hex(header['nonce'])
            or type(header['message_id']) is not int or not 1 <= header['message_id'] <= MAX_SEQUENCE):
        raise ValueError('Invalid camera stream header')
    unpacker = zlib.decompressobj()
    pixels = unpacker.decompress(data[header_size:], MAX_RAW + 1)
    if (len(pixels) > MAX_RAW or not unpacker.eof or unpacker.unused_data
            or unpacker.unconsumed_tail):
        raise ValueError('Invalid bounded camera compression')
    validate_frame(header['frame'], pixels)
    return header, pixels


class CameraFrameQueue(object):
    """No replacement, waits, compression, callbacks or I/O under producer lock."""
    def __init__(self, capacity=128, max_bytes=64 * 1024 * 1024, clock=None):
        if type(capacity) is not int or capacity < 1 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError('Positive frame and byte capacities required')
        self.capacity, self.max_bytes = capacity, max_bytes
        self.clock = clock or time.monotonic
        self.stream_id = uuid.uuid4().hex
        self.changed = threading.Event()
        self.lock = threading.Lock()
        self.frames = deque()
        self.pending_bytes = self.accepted = self.rejected = self.acknowledged = 0

    def enqueue(self, metadata, pixels):
        validate_frame(metadata, pixels)
        frozen = copy.deepcopy(metadata)
        with self.lock:
            if (len(self.frames) >= self.capacity or self.pending_bytes + len(pixels) > self.max_bytes
                    or self.accepted >= MAX_SEQUENCE):
                self.rejected += 1
                return False
            self.accepted += 1
            self.frames.append((self.accepted, frozen, pixels, self.clock()))
            self.pending_bytes += len(pixels)
            self.changed.set()
            return True

    def peek(self):
        with self.lock:
            if not self.frames:
                self.changed.clear()
                return None
            message, metadata, pixels, received = self.frames[0]
            aged = dict(metadata, source_age_seconds=metadata['source_age_seconds']
                        + max(0., self.clock() - received))
            return message, aged, pixels

    def acknowledge(self, message):
        with self.lock:
            if not self.frames or message != self.frames[0][0]:
                raise ValueError('Camera ACK does not match FIFO head')
            self.pending_bytes -= len(self.frames.popleft()[2])
            self.acknowledged += 1
            if not self.frames:
                self.changed.clear()

    def status(self):
        with self.lock:
            return dict(stream_id=self.stream_id, pending=len(self.frames), pending_bytes=self.pending_bytes,
                capacity=self.capacity, max_bytes=self.max_bytes, accepted=self.accepted,
                rejected_new=self.rejected, acknowledged=self.acknowledged,
                overflow_policy='reject_new_report_loss', durable=False)


class CameraFrameAdmission(object):
    """Explicit source-side full/half admission; never a browser display control.

    Select every first/second unique observation independently per actual
    channel and source/capture. Preserve original sequence and UTC. Duplicate
    or replayed observations do not advance phase. No sleeps or network I/O.
    Pixels are already owned here; this reduces transfer, not native copy work.
    """
    def __init__(self, queue, every_n=1, max_channels=4, max_retired_captures=64):
        if (type(every_n) is not int or every_n not in (1, 2)
                or type(max_channels) is not int or not 1 <= max_channels <= 4
                or type(max_retired_captures) is not int or not 1 <= max_retired_captures <= 64):
            raise ValueError('Explicit full/half rate and bounded channel/capture limits required')
        self.queue, self.every_n = queue, every_n
        self.max_channels, self.max_retired = max_channels, max_retired_captures
        self.lock, self.channels = threading.Lock(), {}
        self.observed = self.enqueued = self.decimated = self.duplicates = self.replays = self.queue_rejected = 0
        self.errors = 0

    @staticmethod
    def _stamp(label):
        value = label.replace('Z', '+00:00')
        try:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f+00:00')
        except ValueError:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S+00:00')

    def offer(self, metadata, pixels):
        try:
            frozen = copy.deepcopy(metadata)
            validate_frame(frozen, pixels)
            if 'source_session_id' not in frozen:
                raise ValueError('Source-side admission requires actual source_session_id')
            channel = frozen['channel']
            epoch = frozen['source_session_id'], frozen['capture_session_id']
            sequence, stamp = frozen['sequence'], self._stamp(frozen['observed_utc'])
        except Exception:
            with self.lock:
                self.errors += 1
            raise
        with self.lock:
            prior = self.channels.get(channel)
            if prior is None:
                if len(self.channels) >= self.max_channels:
                    self.errors += 1
                    raise ValueError('Source admission channel bound reached')
                prior = dict(epoch=epoch, sequence=0, phase=0, retired=set(), stamp=stamp)
                self.channels[channel] = prior
            elif epoch in prior['retired']:
                self.replays += 1
                return False
            elif epoch != prior['epoch']:
                if stamp < prior['stamp']:
                    self.replays += 1
                    return False
                if len(prior['retired']) >= self.max_retired:
                    self.errors += 1
                    raise ValueError('Source admission capture history bound reached')
                prior['retired'].add(prior['epoch'])
                prior.update(epoch=epoch, sequence=0, phase=0)
            if sequence <= prior['sequence']:
                if sequence == prior['sequence']:
                    self.duplicates += 1
                else:
                    self.replays += 1
                return False
            prior.update(sequence=sequence, stamp=stamp, phase=prior['phase'] + 1)
            self.observed += 1
            if (prior['phase'] - 1) % self.every_n:
                self.decimated += 1
                return False
            if not self.queue.enqueue(frozen, pixels):
                self.queue_rejected += 1
                return False
            self.enqueued += 1
            return True

    def status(self):
        with self.lock:
            return dict(every_n=self.every_n, channel_ids=sorted(self.channels),
                max_channels=self.max_channels, observed_unique=self.observed,
                enqueued=self.enqueued, intentional_decimated=self.decimated,
                duplicates=self.duplicates, replays=self.replays,
                queue_rejected=self.queue_rejected, errors=self.errors,
                rate_basis='Fraction of unique source observations; not a hardware frame-rate promise',
                modifies_source_frame_identity=False)


class CameraFrameSender(object):
    """One independently started worker, persistent TCP, no successful-send sleep."""
    def __init__(self, queue, address, key, timeout=2., retry_seconds=.1):
        if (type(address) is not tuple or len(address) != 2 or type(address[0]) is not str
                or not address[0] or type(address[1]) is not int or not 1 <= address[1] <= 65535
                or not 0 < timeout <= 10 or not 0 < retry_seconds <= 60):
            raise ValueError('Explicit bounded camera endpoint/deadlines required')
        self.queue, self.address, self.key = queue, address, validate_key(key)
        self.timeout, self.retry_seconds = timeout, retry_seconds
        self.stop_event, self.thread = threading.Event(), None
        self.connection, self.last_error = None, 'Not started'
        self.receiver_id, self.receiver_changes = None, 0

    def disconnect(self):
        connection, self.connection = self.connection, None
        if connection is not None:
            connection.close()

    def send_once(self):
        item = self.queue.peek()
        if item is None:
            return False
        message, metadata, pixels = item
        nonce = uuid.uuid4().hex
        # Compression and sockets run outside the queue's producer lock.
        payload = encode_frame(metadata, pixels, self.queue.stream_id, message, nonce, self.key)
        try:
            if self.connection is None:
                self.connection = socket.create_connection(self.address, timeout=self.timeout)
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            bounded = DeadlineSocket(self.connection, time.monotonic() + self.timeout)
            bounded.sendall(payload)
            reply = recv_message(bounded, MAX_METADATA)
            if (type(reply) is not dict or set(reply) != {'body', 'signature'}
                    or type(reply['body']) is not dict or not _hex(reply['body'].get('receiver_id'))):
                raise ValueError('Camera ACK authentication/identity failed')
            receiver_id = reply['body']['receiver_id']
            wanted = dict(stream_id=self.queue.stream_id, message_id=message, nonce=nonce,
                          accepted=True, receiver_id=receiver_id)
            if (reply['body'] != wanted
                    or type(reply['body'].get('message_id')) is not int
                    or reply['body'].get('accepted') is not True
                    or type(reply['signature']) is not str
                    or not hmac.compare_digest(reply['signature'], sign(self.key, 'ELYSE-CAMERA-ACK-2', wanted))):
                raise ValueError('Camera ACK authentication/identity failed')
            self.queue.acknowledge(message)
            if self.receiver_id is not None and self.receiver_id != receiver_id:
                self.receiver_changes += 1
            self.receiver_id = receiver_id
            self.last_error = ''
            return True
        except Exception:
            self.disconnect()
            raise

    def _run(self):
        try:
            while not self.stop_event.is_set():
                try:
                    if not self.send_once():
                        self.queue.changed.wait(.1)
                except Exception as error:
                    self.last_error = str(error)
                    self.stop_event.wait(self.retry_seconds)
        finally:
            self.disconnect()

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Camera sender already started')
        self.thread = threading.Thread(target=self._run, name='camera-frame-sender')
        self.thread.daemon = True
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.queue.changed.set()
        if self.thread is not None:
            self.thread.join(2 * self.timeout + 1)
        return self.thread is None or not self.thread.is_alive()


class CameraFrameReceiver(object):
    """Single authenticated stream admission. Callback never writes Acquisition DB.

    Caller owns the listener/peer allowlist and transaction deadlines. Admission
    state spans reconnects; duplicate retry is acknowledged without callback.
    Callback must return before ACK. State is RAM-only, not durable delivery.
    A new receiver can resume an existing stream at its first pending message;
    unknown prior ACK history is counted explicitly, never described as lossless
    delivery across receiver restart. Its signed epoch is visible to the sender.
    """
    def __init__(self, key, consume, with_envelope=False):
        if type(with_envelope) is not bool:
            raise ValueError('Explicit callback envelope mode required')
        self.key, self.consume = validate_key(key), consume
        self.with_envelope = with_envelope
        self.lock = threading.Lock()
        self.streams = {}
        self.receiver_id = uuid.uuid4().hex
        self.unknown_prefix_streams = 0
        self.accepted = self.duplicates = 0

    def receive_once(self, connection):
        header, pixels = receive_frame(connection, self.key)
        stream, message = header['stream_id'], header['message_id']
        identity = dict(header['frame'])
        identity.pop('source_age_seconds')  # retries legitimately accumulate age
        digest = hashlib.sha256(canonical(identity) + pixels).digest()
        with self.lock:
            prior = self.streams.get(stream)
            if prior is None and len(self.streams) >= 64:
                raise ValueError('Camera stream session bound reached')
            if prior is not None and message == prior[0]:
                if digest != prior[1]:
                    raise ValueError('Camera frame identity reused with different content')
                self.duplicates += 1
            else:
                if prior is not None and message != prior[0] + 1:
                    raise ValueError('Camera transport sequence discontinuity')
                if self.with_envelope:
                    self.consume(copy.deepcopy(header['frame']), pixels, dict(
                        stream_id=stream, message_id=message, receiver_id=self.receiver_id))
                else:
                    self.consume(copy.deepcopy(header['frame']), pixels)
                if prior is None and message != 1:
                    self.unknown_prefix_streams += 1
                self.streams[stream] = message, digest
                self.accepted += 1
        body = dict(stream_id=stream, message_id=message, nonce=header['nonce'], accepted=True,
                    receiver_id=self.receiver_id)
        send_message(connection, dict(body=body, signature=sign(self.key, 'ELYSE-CAMERA-ACK-2', body)), MAX_METADATA)
        return header
