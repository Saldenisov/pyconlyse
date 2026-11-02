"""Bounded live-camera latest values, Python 3.4; no NI or socket operations.

Keep one waiting image per channel and one immutable in-flight retry. Transport
IDs are assigned on peek, so replacing waiting images never breaks signed ACK
continuity. Source frame IDs remain unchanged. Old images are never replayed
after a newer one merely because the producer becomes idle.
"""
from collections import OrderedDict
import copy
import threading
import time
import uuid

from .camera_stream import MAX_SEQUENCE, validate_frame


class LatestCameraFrameQueue(object):
    def __init__(self, capacity=2, max_bytes=64 * 1024 * 1024, clock=None):
        if (type(capacity) is not int or not 1 <= capacity <= 4
                or type(max_bytes) is not int or max_bytes < 1):
            raise ValueError('Bounded positive latest-channel and byte capacities required')
        self.capacity, self.max_bytes = capacity, max_bytes
        self.clock = clock or time.monotonic
        self.stream_id = uuid.uuid4().hex
        self.changed, self.lock = threading.Event(), threading.Lock()
        self.waiting = OrderedDict()
        self.inflight, self.next_message = None, 1
        self.pending_bytes = self.accepted = self.rejected = self.acknowledged = 0
        self.replaced = 0

    def enqueue(self, metadata, pixels):
        validate_frame(metadata, pixels)
        frozen = copy.deepcopy(metadata)
        with self.lock:
            inflight_bytes = 0 if self.inflight is None else len(self.inflight[2])
            if (inflight_bytes + len(pixels) > self.max_bytes
                    or self.next_message > MAX_SEQUENCE):
                self.rejected += 1
                return False
            channel = frozen['channel']
            prior = self.waiting.pop(channel, None)
            if prior is not None:
                self.pending_bytes -= len(prior[1])
                self.replaced += 1
            while (len(self.waiting) >= self.capacity
                   or self.pending_bytes + len(pixels) > self.max_bytes):
                unused, prior = self.waiting.popitem(last=False)
                self.pending_bytes -= len(prior[1])
                self.replaced += 1
            self.waiting[channel] = (frozen, pixels, self.clock())
            self.pending_bytes += len(pixels)
            self.accepted += 1
            self.changed.set()
            return True

    def peek(self):
        with self.lock:
            if self.inflight is None:
                if not self.waiting:
                    self.changed.clear()
                    return None
                unused, item = self.waiting.popitem(last=False)
                self.inflight = (self.next_message,) + item
            message, metadata, pixels, received = self.inflight
            aged = dict(metadata, source_age_seconds=metadata['source_age_seconds']
                        + max(0., self.clock() - received))
            return message, aged, pixels

    def acknowledge(self, message):
        with self.lock:
            if self.inflight is None or type(message) is not int or message != self.inflight[0]:
                raise ValueError('Camera ACK does not match in-flight latest frame')
            self.pending_bytes -= len(self.inflight[2])
            self.inflight = None
            self.next_message += 1
            self.acknowledged += 1
            if not self.waiting:
                self.changed.clear()

    def status(self):
        with self.lock:
            return dict(stream_id=self.stream_id, pending=len(self.waiting) + int(self.inflight is not None),
                pending_latest=len(self.waiting), inflight=int(self.inflight is not None),
                pending_bytes=self.pending_bytes, capacity=self.capacity + 1,
                pending_channel_capacity=self.capacity, max_bytes=self.max_bytes,
                accepted=self.accepted, rejected_new=self.rejected, acknowledged=self.acknowledged,
                replaced_pending=self.replaced, delivery_policy='latest',
                overflow_policy='replace_pending_latest_per_channel_preserve_inflight',
                transport_ids_assigned='on_send', durable=False)
