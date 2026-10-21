"""Bounded loopback-only VI XML ingress; no standalone GUI or relay owner."""
import socketserver
import struct
import time

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
        socketserver.TCPServer.__init__(self, address, _Handler)
