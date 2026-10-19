"""Python 3.4 HTTP facade: signed named intents only, no raw I/O routes."""
from __future__ import print_function

import re
import socket
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .supervision_runtime import Rejected
from .supervision_wire import MAX_BYTES, RequestGuard, json_bytes, response_mac, strict_json


class SupervisionHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "ELYSE-ACQ-Simulation/1"

    def setup(self):
        self.request.settimeout(5)
        BaseHTTPRequestHandler.setup(self)

    def log_message(self, format_string, *args):
        pass  # Never log authentication headers. Lifecycle has its own durable journal.

    def _reply(self, status, value, nonce=""):
        body = json_bytes(dict(schema_version=1, execution_allowed=False,
                               hardware_writes=False, physical_status="NOT_EXECUTED", **value))
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-ACQ-Signature", response_mac(self.server.guard.key, self.command, self.path, nonce, status, body))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        if self.headers.get("Transfer-Encoding") is not None:
            raise ValueError("Transfer-Encoding not supported")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) > 1:
            raise ValueError("Duplicate Content-Length")
        length = lengths[0] if lengths else "0"
        if not re.match(r"^[0-9]{1,8}\Z", length):
            raise ValueError("Invalid Content-Length")
        size = int(length)
        if size > MAX_BYTES:
            raise ValueError("Request body exceeds 65536 bytes")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Incomplete request body")
        if self.command == "GET" and raw:
            raise ValueError("GET body not allowed")
        return raw

    def _header(self, name):
        values = self.headers.get_all(name, [])
        if len(values) != 1:
            raise ValueError("Missing or duplicate authentication header")
        return values[0]

    def _handle(self):
        nonce = ""
        try:
            raw = self._body()
            try:
                nonce = self._header("X-ACQ-Nonce")
                self.server.guard.verify(self.command, self.path,
                                         self._header("X-ACQ-Timestamp"), nonce,
                                         self._header("X-ACQ-Signature"), raw)
            except ValueError:
                self._reply(401, dict(error="ACQ authentication rejected", accepted=False), nonce)
                return
            runtime = self.server.runtime
            if self.command == "GET" and self.path == "/v1/state":
                self._reply(200, dict(result=runtime.read_state()), nonce)
                return
            match = re.match(r"^/v1/(intents|trace)/([A-Za-z0-9_-]{1,128})\Z", self.path)
            if self.command == "GET" and match:
                method = runtime.read_intent if match.group(1) == "intents" else runtime.trace
                self._reply(200, dict(result=method(match.group(2))), nonce)
                return
            if self.command == "POST" and self.path == "/v1/intents":
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("application/json required")
                data = strict_json(raw)
                if type(data) is not dict or set(data) != {"intent_id", "procedure", "expected_revision", "session_id"}:
                    raise ValueError("Required fields: intent_id, procedure, expected_revision, session_id")
                if any(not isinstance(data[key], str) or not 1 <= len(data[key]) <= 128 for key in data):
                    raise ValueError("Intent fields must be bounded nonempty strings")
                receipt = runtime.submit_procedure(**data)
                self._reply(200, dict(result=receipt), nonce)
                return
            self._reply(404, dict(error="Unknown ACQ route", accepted=False), nonce)
        except Rejected as error:
            self._reply(409, dict(error=str(error), accepted=False), nonce)
        except KeyError:
            self._reply(404, dict(error="Unknown ACQ intent", accepted=False), nonce)
        except (ValueError, UnicodeError, RuntimeError) as error:
            self._reply(400, dict(error=str(error), accepted=False), nonce)
        except (socket.timeout, OSError):
            return  # Connection outcome is unknown to the caller; never retry here.
        except Exception:
            self._reply(503, dict(error="ACQ service unavailable"), nonce)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()


class SupervisionServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 16

    def __init__(self, address, runtime, key):
        if address[0] not in ("127.0.0.1", "10.20.30.10"):
            raise ValueError("Bind explicitly to loopback or the ACQ interface 10.20.30.10")
        self.runtime = runtime
        self.guard = RequestGuard(key)
        self._slots = threading.BoundedSemaphore(32)
        HTTPServer.__init__(self, address, SupervisionHandler)

    def process_request(self, request, address):
        if not self._slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            socketserver.ThreadingMixIn.process_request(self, request, address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            socketserver.ThreadingMixIn.process_request_thread(self, request, address)
        finally:
            self._slots.release()
