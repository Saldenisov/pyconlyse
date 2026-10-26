"""Authenticated read-only runtime endpoint. No remote NI/control operations."""
import hashlib
import hmac
import json
import threading

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
except ImportError:
    raise RuntimeError("Python 3.4 or newer required")


def request_signature(key, path, nonce):
    if path not in ("/status", "/snapshot"):
        raise ValueError("Unsupported read path")
    if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
        raise ValueError("Invalid nonce")
    return hmac.new(key, ("ACQ-RUNTIME-READ-1\nGET\n" + path + "\n" + nonce).encode("ascii"),
                    hashlib.sha256).hexdigest()


def response_signature(key, nonce, body):
    return hmac.new(key, b"ACQ-RUNTIME-RESPONSE-1\n" + nonce.encode("ascii") + b"\n" + body,
                    hashlib.sha256).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        BaseHTTPRequestHandler.setup(self)
        self.connection.settimeout(2.0)

    def log_message(self, *args):
        pass  # No request log, telemetry file or SQLite.

    def _reply(self, code, body):
        encoded = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        if code == 200:
            self.send_header("X-ACQ-Response-Signature", response_signature(
                self.server.key, self.headers["X-ACQ-Nonce"], encoded))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.client_address[0] not in self.server.allowed_peers:
            self._reply(403, dict(error="peer_not_permitted"))
            return
        if self.path not in ("/status", "/snapshot"):
            self._reply(404, dict(error="unknown_read_path"))
            return
        try:
            expected = request_signature(self.server.key, self.path,
                                         self.headers.get("X-ACQ-Nonce", ""))
        except ValueError:
            self._reply(401, dict(error="authentication_required"))
            return
        try:
            authenticated = hmac.compare_digest(expected, self.headers.get("X-ACQ-Signature", ""))
        except TypeError:
            authenticated = False
        if not authenticated:
            self._reply(401, dict(error="authentication_required"))
            return
        if self.client_address[0] == "10.20.30.202":
            self.server.runtime.note_everest_read()
        body = self.server.runtime.snapshot()
        if self.path == "/status":
            body.pop("latest", None)
        self._reply(200, body)

    def _no_control(self):
        self._reply(405, dict(error="remote_control_disabled"))

    do_POST = do_PUT = do_DELETE = do_PATCH = _no_control


class RuntimeHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 4

    def __init__(self, address, runtime, key):
        if address[0] not in ("127.0.0.1", "10.20.30.10", "10.20.30.2"):
            raise ValueError("Bind must be loopback or explicit XP interface")
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("A shared key of at least 32 bytes is required")
        self.runtime = runtime
        self.key = key
        self.allowed_peers = ("127.0.0.1", "10.20.30.202")
        self._slots = threading.BoundedSemaphore(4)
        HTTPServer.__init__(self, address, _Handler)

    def process_request(self, request, address):
        if not self._slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            ThreadingMixIn.process_request(self, request, address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            ThreadingMixIn.process_request_thread(self, request, address)
        finally:
            self._slots.release()
