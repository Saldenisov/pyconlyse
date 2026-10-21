"""Authenticated HTTP adapter; command admission has its own worker."""
import hmac
import json

from .acquisition_http import RuntimeHTTPServer, _Handler
from .command_protocol import MAX_COMMAND_BYTES, command_signature, strict_json
from .runtime_identity import valid_hex
from .command_dispatch import CommandDispatcher

class _ControlHandler(_Handler):
    def _reply(self, code, body):
        # All replies, including refused/failed commands, are authenticated.
        # The old reader uses its unchanged response-signature domain.
        if self.command != "POST":
            if code == 200 and self.path == "/snapshot" and "control" in body:
                body["control"]["lease"] = self.server.runtime.broker.snapshot(issue_lease=True)["lease"]
            return _Handler._reply(self, code, body)
        from .acquisition_http import response_signature
        encoded = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        for name, value in (("Content-Type", "application/json"), ("Content-Length", str(len(encoded))),
                            ("Cache-Control", "no-store"), ("Connection", "close")):
            self.send_header(name, value)
        nonce = self.headers.get("X-ACQ-Nonce", "")
        if valid_hex(nonce, 32) and self.server.command_key is not None:
            self.send_header("X-ACQ-Response-Signature", response_signature(self.server.command_key, nonce, encoded))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.client_address[0] not in self.server.allowed_peers:
            return self._reply(403, dict(error="peer_not_permitted"))
        if self.path != "/commands":
            return self._reply(404, dict(error="unknown_command_path"))
        if self.server.command_key is None or not self.server.runtime.broker.enabled:
            return self._reply(403, dict(error="remote_control_disabled"))
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if (len(lengths) != 1 or not lengths[0].isdigit() or self.headers.get("Transfer-Encoding")
                    or self.headers.get("Content-Type") != "application/json"):
                raise ValueError("Exact bounded JSON framing required")
            length = int(lengths[0])
            if not 0 < length <= MAX_COMMAND_BYTES:
                raise ValueError("Command body exceeds limit")
            body = self.rfile.read(length)
            expected = command_signature(self.server.command_key, self.headers.get("X-ACQ-Nonce", ""), body)
            if len(body) != length or not hmac.compare_digest(expected, self.headers.get("X-ACQ-Signature", "")):
                return self._reply(401, dict(error="command_authentication_required"))
            envelope = strict_json(body)
            if type(envelope) is not dict or set(envelope) != {"request", "lease"}:
                raise ValueError("Exact transport envelope required")
            result = self.server.dispatcher.submit(envelope["request"], envelope["lease"])
            self._reply(200, result)
        except (ValueError, TypeError, RuntimeError) as error:
            self._reply(409, dict(error=str(error)[:300], hardware_acknowledged=False))


class ControlHTTPServer(RuntimeHTTPServer):
    def __init__(self, address, runtime, read_key, command_key=None):
        if runtime.broker.enabled and (not isinstance(command_key, bytes) or len(command_key) < 32
                                       or command_key == read_key):
            raise ValueError("Separate command key of at least 32 bytes required")
        RuntimeHTTPServer.__init__(self, address, runtime, read_key)
        self.command_key = command_key
        self.RequestHandlerClass = _ControlHandler
        self.dispatcher = CommandDispatcher(runtime.broker)
        try:
            self.dispatcher.start()
        except Exception:
            RuntimeHTTPServer.server_close(self)
            raise

    def server_close(self):
        # Retain ownership if an admitted request has not returned. Never
        # replace a blocked worker or replay its command on another thread.
        if hasattr(self, 'dispatcher'):
            self.dispatcher.close()
        RuntimeHTTPServer.server_close(self)
