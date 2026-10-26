"""Explicit loopback console possession, without a JWT account or qualification.

The caller supplies existing CSRF protection and current capability checks.
No key is generated here. Approvals authorize one exact server-normalized
intent and are consumed before dispatch; they are not physical safety proof.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import urlsplit


SUBJECT = "local-console"
DEFAULT_ORIGIN = "http://127.0.0.1:5000"
INTENT_FIELDS = ("operation", "value", "session_id", "expected_revision", "device", "method", "route")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TABLE = "acq_local_console_approvals"


class LocalConsoleError(RuntimeError):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def _forbidden(message):
    return LocalConsoleError(403, "local_console_forbidden", message)


def _invalid(message="Local console approval is invalid, expired or already used"):
    return LocalConsoleError(409, "hardware_approval_invalid", message)


def _origin(settings):
    value = settings.get("ACQ_LOCAL_CONSOLE_ORIGIN", DEFAULT_ORIGIN)
    try:
        if type(value) is not str or not value:
            raise ValueError()
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
        authority = "[::1]" if host == "::1" else "127.0.0.1"
        if port is not None:
            authority += ":" + str(port)
        if (parsed.scheme not in ("http", "https") or host not in ("127.0.0.1", "::1")
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment
                or (port is not None and not 1 <= port <= 65535)
                or value != parsed.scheme + "://" + authority):
            raise ValueError()
    except (ValueError, TypeError):
        raise _forbidden("Local console origin must be an explicit literal loopback origin") from None
    return value, authority


def local_subject(request, settings, auth_required, require_origin=True):
    """Return only the fixed server subject for an explicitly enabled context.

    Forwarded headers and client identity fields never establish locality.
    Set require_origin=False only for a read endpoint: normal GET may omit it.
    """
    if settings.get("ACQ_LOCAL_CONSOLE_ENABLED") is not True or auth_required is not False:
        return None
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return None
    origin, host = _origin(settings)
    headers = request.headers
    if headers.get("Host") != host:
        raise _forbidden("Local console Host does not match the configured origin")
    supplied = headers.get("Origin")
    if (require_origin is not False and supplied != origin) or (supplied is not None and supplied != origin):
        raise _forbidden("Local console requires the exact configured browser Origin")
    return SUBJECT


def is_local_context(request, settings, auth_required, require_origin=False):
    return local_subject(request, settings, auth_required, require_origin=require_origin) == SUBJECT


def _json_tree(value, depth=0):
    if depth > 32:
        raise ValueError()
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_tree(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_tree(item, depth + 1)
        return
    raise ValueError()


def _canonical_intent(intent):
    try:
        if type(intent) is not dict or set(intent) != set(INTENT_FIELDS):
            raise ValueError()
        for field in ("operation", "device", "method", "route"):
            if type(intent[field]) is not str or not 0 < len(intent[field]) <= 256:
                raise ValueError()
        if (intent["method"] != "POST" or type(intent["session_id"]) is not str
                or _HEX32.fullmatch(intent["session_id"]) is None
                or type(intent["expected_revision"]) is not int
                or not 0 <= intent["expected_revision"] <= 2**53 - 1):
            raise ValueError()
        _json_tree(intent)
        result = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        if len(result) > 65536:
            raise ValueError()
        return result
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise LocalConsoleError(400, "local_console_intent_invalid", "Exact normalized local console intent required") from None


def _settings(settings, subject, clock):
    if settings.get("ACQ_LOCAL_CONSOLE_ENABLED") is not True or subject != SUBJECT:
        raise _forbidden("Explicit local console context required")
    _origin(settings)
    try:
        ttl = settings.get("ACQ_LOCAL_CONSOLE_TTL_SECONDS", 30)
        now = clock()
        if (type(ttl) not in (int, float) or not math.isfinite(ttl) or not 0 < ttl <= 60
                or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or now + ttl <= now):
            raise ValueError()
        key_path = Path(settings["ACQ_LOCAL_CONSOLE_KEY_FILE"])
        db_path = Path(settings["ACQ_LOCAL_CONSOLE_DB_FILE"])
        if (not key_path.is_absolute() or not db_path.is_absolute()
                or key_path.is_symlink() or db_path.is_symlink()
                or key_path.resolve() == db_path.resolve() or not db_path.parent.is_dir()):
            raise ValueError()
        before = key_path.stat()
        if not stat.S_ISREG(before.st_mode) or not 32 <= before.st_size <= 65536:
            raise ValueError()
        descriptor = os.open(str(key_path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode)
                    or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
                raise ValueError()
            key = stream.read(65537)
        if not 32 <= len(key) <= 65536:
            raise ValueError()
    except (OSError, KeyError, ValueError, TypeError, OverflowError):
        raise LocalConsoleError(503, "local_console_unavailable", "Provisioned local console key and persistent database required") from None
    return key, str(db_path), float(now), float(ttl)


def _signature(key, row):
    # Signing used/consumed_at also prevents a simple used-bit reset in SQLite.
    payload = json.dumps([1] + list(row), separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hmac.new(key, payload.encode("ascii"), hashlib.sha256).hexdigest()


def _database(path):
    db = None
    try:
        db = sqlite3.connect(path, timeout=3, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS " + _TABLE + " ("
            "nonce_hash TEXT PRIMARY KEY, subject TEXT NOT NULL, intent TEXT NOT NULL, "
            "issued_at REAL NOT NULL, expires_at REAL NOT NULL, used INTEGER NOT NULL, "
            "consumed_at REAL, mac TEXT NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        return db
    except sqlite3.Error:
        if db is not None:
            db.close()
        raise LocalConsoleError(503, "local_console_unavailable", "Local console approval storage unavailable") from None


def issue_approval(intent, subject, settings, clock=time.time):
    canonical = _canonical_intent(intent)
    key, path, now, ttl = _settings(settings, subject, clock)
    nonce = secrets.token_hex(32)
    row = (hashlib.sha256(nonce.encode("ascii")).hexdigest(), subject, canonical, now, now + ttl, 0, None)
    db = _database(path)
    try:
        db.execute("INSERT INTO " + _TABLE + " VALUES (?,?,?,?,?,?,?,?)", row + (_signature(key, row),))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise LocalConsoleError(503, "local_console_unavailable", "Local console approval could not be stored") from None
    finally:
        db.close()
    return nonce


def consume_approval(intent, subject, nonce, settings, clock=time.time):
    canonical = _canonical_intent(intent)
    key, path, now, ttl = _settings(settings, subject, clock)
    if nonce is None:
        raise LocalConsoleError(428, "hardware_approval_required", "Local console approval required")
    if type(nonce) is not str or _HEX64.fullmatch(nonce) is None:
        raise _invalid()
    nonce_hash = hashlib.sha256(nonce.encode("ascii")).hexdigest()
    db = _database(path)
    try:
        row = db.execute("SELECT nonce_hash,subject,intent,issued_at,expires_at,used,consumed_at,mac FROM "
                         + _TABLE + " WHERE nonce_hash=?", (nonce_hash,)).fetchone()
        try:
            if (row is None or type(row[7]) is not str or not hmac.compare_digest(row[7], _signature(key, row[:7]))
                    or row[1] != subject or row[2] != canonical or row[5] != 0 or row[6] is not None
                    or not row[3] <= now < row[4] or not 0 < row[4] - row[3] <= 60):
                raise _invalid()
        except (ValueError, TypeError, OverflowError):
            raise _invalid() from None
        consumed = row[:5] + (1, now)
        db.execute("UPDATE " + _TABLE + " SET used=1,consumed_at=?,mac=? WHERE nonce_hash=? AND used=0",
                   (now, _signature(key, consumed), nonce_hash))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise LocalConsoleError(503, "local_console_unavailable", "Local console approval could not be consumed") from None
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
    return True
