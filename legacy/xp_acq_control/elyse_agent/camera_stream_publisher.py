"""Optional independent camera path for the one SuperVision host, Python3.4.

VI/native-owner admission only appends bounded immutable descriptors. Decode/admission
and compression/network execute on separate workers, without NI or publisher
locks. No listener, thread, connection or hardware operation occurs on import.
"""
import base64
from collections import deque
import copy
import math
import threading
import time

from .camera_stream import CameraFrameQueue, CameraFrameAdmission, CameraFrameSender, validate_frame
from .federation_wire import validate_video_frame


def validate_camera_stream_configuration(value):
    if value is None:
        return None
    if type(value) is not dict or type(value.get('enabled')) is not bool:
        raise ValueError('Explicit camera_stream enabled policy required')
    fields = {'enabled', 'source_mode', 'host', 'port', 'every_n', 'capacity', 'max_bytes',
              'max_channels', 'timeout_seconds', 'retry_seconds'}
    if set(value) - fields:
        raise ValueError('Unknown independent camera configuration field')
    if not value['enabled']:
        return None
    if (set(value) != fields or value['source_mode'] not in ('LABVIEW_BRIDGE', 'VI_OR_NATIVE') or value['host'] != '10.20.30.202'
            or type(value['port']) is not int or not 1024 <= value['port'] <= 65535 or value['port'] == 8767
            or type(value['every_n']) is not int or value['every_n'] not in (1, 2)
            or type(value['capacity']) is not int or not 1 <= value['capacity'] <= 128
            or type(value['max_bytes']) is not int or not 524288 <= value['max_bytes'] <= 64 * 1024 * 1024
            or type(value['max_channels']) is not int or not 1 <= value['max_channels'] <= 4):
        raise ValueError('Bounded explicit Everest camera destination/rate/FIFO required')
    for name, high in (('timeout_seconds', 5), ('retry_seconds', 60)):
        item = value[name]
        if type(item) not in (int, float) or not math.isfinite(item) or not .01 <= item <= high:
            raise ValueError('Bounded camera transport time required: ' + name)
    return copy.deepcopy(value)


class CameraStreamPublisher(object):
    def __init__(self, configuration, key, clock=None, sender_factory=None):
        config = validate_camera_stream_configuration(configuration)
        if config is None:
            raise ValueError('Enabled independent camera configuration required')
        self.config, self.clock = config, clock or time.monotonic
        self.queue = CameraFrameQueue(config['capacity'], config['max_bytes'], clock=self.clock)
        self.admission = CameraFrameAdmission(self.queue, every_n=config['every_n'], max_channels=config['max_channels'])
        self.sender = (sender_factory or CameraFrameSender)(self.queue, (config['host'], config['port']), key,
            timeout=config['timeout_seconds'], retry_seconds=config['retry_seconds'])
        self.lock = threading.Lock()
        self.staging = deque()
        self.staging_bytes = self.received = self.staging_rejected = self.errors = 0
        self.native_received = 0
        self.python_received = 0
        self.last_error = ''
        self.wake, self.stop = threading.Event(), threading.Event()
        self.worker = None

    def submit_video(self, video, received_at):
        """O(1) descriptor append: no base64/JSON decode, compression or network."""
        return self._submit(video, received_at, False)

    def submit_native_video(self, video, received_at):
        """Only the validated native decoder supplies this internal byte form."""
        if video is not None and type(video.get('data')) is not bytes:
            raise ValueError('Native staging requires immutable owned pixels')
        return self._submit(video, received_at, True)

    def submit_python_video(self, video, owner_session_id, received_at):
        """Retained native owner's immutable IPC sample; no driver/network call."""
        from .runtime_identity import valid_hex
        if (self.config['source_mode'] != 'VI_OR_NATIVE'
                or not valid_hex(owner_session_id, 32)
                or type(video) is not dict or video.get('source') != 'python_supervision_ni1409'):
            raise ValueError('Explicit current Python camera owner required')
        return self._submit(video, received_at, False, owner_session_id)

    def _submit(self, video, received_at, native_pixels, owner_session_id=None):
        if video is None:
            return False
        # Caller validated the JSON schema or fixed native header/clocks.
        # Pixel bytes and scalar/string fields are immutable.
        descriptor = dict(video)
        size = len(descriptor['data'])
        with self.lock:
            if (self.stop.is_set() or len(self.staging) >= self.config['capacity']
                    or self.staging_bytes + size > self.config['max_bytes']):
                self.staging_rejected += 1
                return False
            self.staging.append((descriptor, received_at, size, native_pixels, owner_session_id))
            self.staging_bytes += size
            self.received += 1
            self.native_received += int(native_pixels)
            self.python_received += int(owner_session_id is not None)
            self.wake.set()
            return True

    def process_once(self):
        with self.lock:
            if not self.staging:
                self.wake.clear()
                return False
            video, at, size, native_pixels, owner_session_id = self.staging.popleft()
            self.staging_bytes -= size
            if not self.staging:
                self.wake.clear()
        try:
            expected = ('python_supervision_ni1409' if owner_session_id is not None
                        else 'labview_supervision_ni1409')
            if video['source'] != expected:
                raise ValueError('Camera source does not match its admitted owner')
            metadata = {name: video[name] for name in ('capture_session_id',
                'sequence', 'observed_utc', 'width', 'height', 'channel', 'source_age_seconds')}
            metadata['source_session_id'] = owner_session_id or video['source_session_id']
            metadata['source_age_seconds'] += max(0., self.clock() - at)
            if native_pixels:
                pixels = video['data']
                validate_frame(metadata, pixels)
            else:
                validate_video_frame(video)
                pixels = base64.b64decode(video['data'].encode('ascii'), validate=True)
            self.admission.offer(metadata, pixels)
            with self.lock:
                self.last_error = ''
        except Exception as error:
            with self.lock:
                self.errors += 1
                self.last_error = type(error).__name__ + ': ' + str(error)[:180]
        return True

    def _run(self):
        while not self.stop.is_set():
            if not self.process_once():
                self.wake.wait(.1)

    def start(self):
        if self.worker is not None or self.stop.is_set():
            raise RuntimeError('Independent camera publisher cannot start twice')
        self.worker = threading.Thread(target=self._run, name='supervision-camera-admission')
        self.worker.daemon = True
        try:
            self.sender.start()
            self.worker.start()
        except Exception:
            self.close()
            raise

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.worker is not None and self.worker.is_alive():
            self.worker.join(3)
        sender_closed = self.sender.close()
        return (self.worker is None or not self.worker.is_alive()) and sender_closed

    def status(self):
        with self.lock:
            staging = dict(pending=len(self.staging), pending_bytes=self.staging_bytes,
                accepted=self.received, rejected_new=self.staging_rejected,
                native_pixels_accepted=self.native_received,
                python_frames_accepted=self.python_received,
                errors=self.errors, last_error=self.last_error,
                oldest_age_seconds=None if not self.staging else max(0., self.clock() - self.staging[0][1]))
        return dict(enabled=True, transport='independent_binary_camera_v2',
            destination='{}:{}'.format(self.config['host'], self.config['port']),
            source_admission=self.admission.status(), staging=staging, fifo=self.queue.status(),
            compression_level=self.sender.compression_level,
            last_encode_seconds=self.sender.last_encode_seconds,
            sender_error=self.sender.last_error, receiver_session_id=self.sender.receiver_id,
            receiver_session_changes=self.sender.receiver_changes,
            started=self.worker is not None, durable=False, images_archived=False,
            local_ack_semantics='Local VI/native staging is separate from authenticated Everest RAM ACK')
