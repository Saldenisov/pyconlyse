"""Bounded loopback-only VI XML ingress; no standalone GUI or relay owner."""
import socketserver
import struct
import time
import threading

from .protocol import recv_exact, send_message
from .shared_state import MAX_XML_BYTES
from .telemetry_relay import DeadlineSocket


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != "127.0.0.1":
            return
        bounded = DeadlineSocket(self.request, time.monotonic() + 2)
        try:
            size = struct.unpack("!I", recv_exact(bounded, 4))[0]
            if not 1 <= size <= MAX_XML_BYTES:
                raise ValueError("invalid snapshot XML frame length")
            result = self.server.store.ingest(recv_exact(bounded, size), self.client_address[0])
            reply = dict(id="shared-state", ok=True, result=result)
        except Exception as error:
            with self.server.store.lock:
                self.server.store.rejected += 1
                self.server.store.last_error = str(error)
            reply = dict(id="shared-state", ok=False,
                         error=dict(code="snapshot_rejected", message=str(error)))
        try:
            send_message(bounded, reply, MAX_XML_BYTES)
        except Exception:
            pass  # No claim that the VI received the local acknowledgement.


class SharedStateServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = False

    def __init__(self, address, store):
        if address[0] != "127.0.0.1":
            raise ValueError("shared-state ingress must be IPv4 loopback")
        self.store = store
        self._slots = threading.BoundedSemaphore(4)
        self._handlers = threading.Condition()
        self._active_handlers = 0
        self._closing_handlers = False
        self.handler_limit_rejections = 0
        socketserver.TCPServer.__init__(self, address, _Handler)

    def process_request(self, request, address):
        if not self._slots.acquire(False):
            self.handler_limit_rejections += 1
            # Do not wait for the publication lock to report overload; the
            # server-level counter remains visible even during contention.
            if self.store.lock.acquire(False):
                try:
                    self.store.rejected += 1
                    self.store.last_error = "VI_INGRESS_HANDLER_LIMIT"
                finally:
                    self.store.lock.release()
            self.shutdown_request(request)
            return
        with self._handlers:
            if self._closing_handlers:
                self._slots.release()
                self.shutdown_request(request)
                return
            self._active_handlers += 1  # Include scheduled but not started threads.
        try:
            socketserver.ThreadingMixIn.process_request(self, request, address)
        except Exception:
            self._slots.release()
            with self._handlers:
                self._active_handlers -= 1
                self._handlers.notify_all()
            raise

    def process_request_thread(self, request, address):
        try:
            socketserver.ThreadingMixIn.process_request_thread(self, request, address)
        finally:
            self._slots.release()
            with self._handlers:
                self._active_handlers -= 1
                self._handlers.notify_all()

    def server_close(self):
        with self._handlers:
            self._closing_handlers = True
        socketserver.TCPServer.server_close(self)
        # Python 3.4 ThreadingMixIn does not join its non-daemon handlers.
        deadline = time.monotonic() + 3
        with self._handlers:
            while self._active_handlers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("VI handlers still owned; ingress shutdown unfinished")
                self._handlers.wait(remaining)
