"""Loopback-only JSON/static server. No execution, raw-channel, or network-device API."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from .application import OfflineSupervision
from .shadow import InvalidPreview, canonical_json
from .store import AuditIntegrityError, IdempotencyConflict


STATIC_FILES = {"/": ("index.html", "text/html; charset=utf-8"),
                "/index.html": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                "/shadow.js": ("shadow.js", "application/javascript; charset=utf-8"),
                "/magnet-registry.js": ("magnet-registry.js", "application/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8")}


def strict_json(raw: bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)


class OfflineHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: OfflineSupervision, static_root: Path):
        if address[0] != "127.0.0.1":
            raise ValueError("Offline service must bind 127.0.0.1; not deployable to the accelerator LAN")
        self.app = app
        self.static_root = static_root
        super().__init__(address, OfflineHandler)
        self.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}
        self.allowed_origins = {f"http://{host}" for host in self.allowed_hosts}


class OfflineHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args) -> None:
        pass

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, body: dict) -> None:
        self._send(status, canonical_json(body).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": code, "message": message, "execution_allowed": False})

    def _safe_host(self) -> bool:
        if self.headers.get_all("Host", []) != [self.headers.get("Host")]:
            self._error(403, "HOST_DENIED", "Single explicit loopback host required")
            return False
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self._error(403, "HOST_DENIED", "Loopback host required")
            return False
        return True

    def do_GET(self) -> None:
        if not self._safe_host():
            return
        path = urlsplit(self.path)
        if path.scheme or path.netloc or path.query or path.fragment:
            self._error(404, "NOT_FOUND", "Endpoint not available")
            return
        try:
            if path.path == "/api/supervision/snapshot":
                self._json(200, self.server.app.snapshot(now=datetime.now(timezone.utc)))
            elif path.path == "/api/shadow/history":
                self._json(200, {"execution_allowed": False, "records": self.server.app.journal.history()})
            elif path.path in STATIC_FILES:
                name, mime = STATIC_FILES[path.path]
                content = (self.server.static_root / name).read_bytes()
                if name == "index.html":
                    content = content.replace(b'<html lang="fr">', b'<html lang="fr" data-offline-api="true">', 1)
                self._send(200, content, mime)
            elif path.path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._error(404, "NOT_FOUND", "Endpoint not available")
        except AuditIntegrityError:
            self._error(503, "JOURNAL_INTEGRITY_FAILED", "Journal data preserved; manual investigation required")
        except (OSError, ValueError, sqlite3.Error):
            self._error(503, "OFFLINE_SERVICE_UNAVAILABLE", "Local evidence or service data unavailable")

    def do_POST(self) -> None:
        if not self._safe_host():
            return
        if self.path != "/api/shadow/current-preview":
            self._error(404, "NOT_FOUND", "Only offline current preview is supported")
            return
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or (origins and origins[0] not in self.server.allowed_origins):
            self._error(403, "ORIGIN_DENIED", "Same-origin local analysis required")
            return
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            self._error(403, "FETCH_SITE_DENIED", "Cross-site preview denied")
            return
        if len(self.headers.get_all("Content-Type", [])) != 1 or self.headers.get_content_type() != "application/json":
            self._error(415, "JSON_REQUIRED", "application/json required")
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding") is not None:
                raise ValueError("Single explicit body length required")
            length = int(lengths[0])
            if not 1 <= length <= 16384:
                self._error(413, "BODY_TOO_LARGE", "Bounded nonempty JSON required")
                return
            self.connection.settimeout(5)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete JSON body")
            body = strict_json(raw)
            result = self.server.app.preview(body, now=datetime.now(timezone.utc))
            self._json(200, result)
        except IdempotencyConflict as error:
            self._error(409, "IDEMPOTENCY_CONFLICT", str(error))
        except (InvalidPreview, ValueError, UnicodeError, RecursionError, TimeoutError) as error:
            self._error(400, "INVALID_PREVIEW", str(error))
        except AuditIntegrityError:
            self._error(503, "JOURNAL_INTEGRITY_FAILED", "Journal data preserved; no action executed")
        except (OSError, sqlite3.Error):
            self._error(503, "OFFLINE_SERVICE_UNAVAILABLE", "Local journal unavailable; no action executed")

    def do_OPTIONS(self) -> None:
        self._error(405, "METHOD_DENIED", "Cross-origin preview is not supported")

    def do_PUT(self) -> None:
        self._error(405, "METHOD_DENIED", "No execution or update endpoint exists")

    do_DELETE = do_PUT
    do_PATCH = do_PUT
