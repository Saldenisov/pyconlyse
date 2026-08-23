# auth.py
import json
import os
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from math import ceil

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from werkzeug.security import check_password_hash, generate_password_hash

auth = Blueprint('auth', __name__)


@dataclass(frozen=True)
class LoginRateLimitConfiguration:
    attempts: int
    window_seconds: int
    max_keys: int


_LOGIN_RATE_LIMIT_DEFAULT_ATTEMPTS = 5
_LOGIN_RATE_LIMIT_DEFAULT_WINDOW_SECONDS = 900
_LOGIN_RATE_LIMIT_DEFAULT_MAX_KEYS = 10_000
_LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 1_000
_LOGIN_RATE_LIMIT_MAX_WINDOW_SECONDS = 86_400
_LOGIN_RATE_LIMIT_MAX_KEYS = 100_000
_LOGIN_FAILURES = OrderedDict()
_LOGIN_FAILURES_LOCK = threading.Lock()
_monotonic = time.monotonic
_DUMMY_PASSWORD_HASH = generate_password_hash("pyconlyse-invalid-login-password")


def _positive_int_from_environment(name, default, maximum):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}")
    return value


def login_rate_limit_configuration():
    """Read bounded, single-process login throttling settings from the environment."""
    return LoginRateLimitConfiguration(
        attempts=_positive_int_from_environment(
            "PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS",
            _LOGIN_RATE_LIMIT_DEFAULT_ATTEMPTS,
            _LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        ),
        window_seconds=_positive_int_from_environment(
            "PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS",
            _LOGIN_RATE_LIMIT_DEFAULT_WINDOW_SECONDS,
            _LOGIN_RATE_LIMIT_MAX_WINDOW_SECONDS,
        ),
        max_keys=_positive_int_from_environment(
            "PYCONLYSE_LOGIN_RATE_LIMIT_MAX_KEYS",
            _LOGIN_RATE_LIMIT_DEFAULT_MAX_KEYS,
            _LOGIN_RATE_LIMIT_MAX_KEYS,
        ),
    )


def reset_login_rate_limiter():
    """Clear process-local limiter state; intended for tests and controlled restarts."""
    with _LOGIN_FAILURES_LOCK:
        _LOGIN_FAILURES.clear()


def _client_key():
    """Use client address only, so throttling never varies with supplied username."""
    address = request.remote_addr
    return address if isinstance(address, str) and address else "unknown"


def _prune_login_failures(now, configuration):
    cutoff = now - configuration.window_seconds
    for key, failures in tuple(_LOGIN_FAILURES.items()):
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            del _LOGIN_FAILURES[key]


def _retry_after(failures, now, configuration):
    return max(1, ceil(configuration.window_seconds - (now - failures[0])))


def _login_retry_after(client_key, configuration):
    now = _monotonic()
    with _LOGIN_FAILURES_LOCK:
        _prune_login_failures(now, configuration)
        failures = _LOGIN_FAILURES.get(client_key)
        if failures is not None:
            _LOGIN_FAILURES.move_to_end(client_key)
            if len(failures) >= configuration.attempts:
                return _retry_after(failures, now, configuration)
            return None
        if len(_LOGIN_FAILURES) >= configuration.max_keys:
            # Do not evict active client state: bounded-memory pressure fails closed.
            return configuration.window_seconds
    return None


def _record_login_failure(client_key, configuration):
    now = _monotonic()
    with _LOGIN_FAILURES_LOCK:
        _prune_login_failures(now, configuration)
        failures = _LOGIN_FAILURES.get(client_key)
        if failures is None:
            if len(_LOGIN_FAILURES) >= configuration.max_keys:
                return configuration.window_seconds
            failures = deque()
            _LOGIN_FAILURES[client_key] = failures
        else:
            _LOGIN_FAILURES.move_to_end(client_key)
        if len(failures) >= configuration.attempts:
            return _retry_after(failures, now, configuration)
        failures.append(now)
    return None


def _clear_login_failures(client_key):
    with _LOGIN_FAILURES_LOCK:
        _LOGIN_FAILURES.pop(client_key, None)


def _rate_limited_response(retry_after):
    response = jsonify({"msg": "Too many login attempts"})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def _is_supported_password_hash(password_hash):
    method, separator, remainder = password_hash.partition("$")
    salt, separator, encoded_hash = remainder.partition("$")
    return (
        bool(separator and salt and encoded_hash)
        and method.startswith(("scrypt:", "pbkdf2:"))
    )


def configured_users(required=False):
    """Return credentials configured through PYCONLYSE_AUTH_USERS."""
    login_rate_limit_configuration()
    raw_users = os.environ.get("PYCONLYSE_AUTH_USERS", "").strip()
    if not raw_users:
        if required:
            raise RuntimeError("PYCONLYSE_AUTH_USERS must define at least one user")
        return {}

    try:
        users = json.loads(raw_users)
    except json.JSONDecodeError as exc:
        raise RuntimeError("PYCONLYSE_AUTH_USERS must be a JSON object") from exc

    if not isinstance(users, dict) or not users:
        raise RuntimeError("PYCONLYSE_AUTH_USERS must define at least one user")
    if not all(
        isinstance(username, str) and isinstance(password_hash, str)
        for username, password_hash in users.items()
    ):
        raise RuntimeError("PYCONLYSE_AUTH_USERS must map usernames to password hashes")
    for password_hash in users.values():
        if not _is_supported_password_hash(password_hash):
            raise RuntimeError(
                "PYCONLYSE_AUTH_USERS must contain Werkzeug password hashes"
            )
        try:
            check_password_hash(password_hash, "configuration-validation")
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "PYCONLYSE_AUTH_USERS must contain Werkzeug password hashes"
            ) from exc
    return users

@auth.route('/api/login', methods=['POST'])
def login():
    # Support JSON or form-data input.
    if request.is_json:
        username = request.json.get("username", None)
        password = request.json.get("password", None)
    else:
        username = request.form.get("username", None)
        password = request.form.get("password", None)

    if (
        not isinstance(username, str)
        or not isinstance(password, str)
        or not username
        or not password
    ):
        return jsonify({"msg": "Missing username or password"}), 400

    try:
        configuration = login_rate_limit_configuration()
        users = configured_users()
    except RuntimeError:
        return jsonify({"msg": "Authentication is not configured"}), 503
    if not users:
        return jsonify({"msg": "Authentication is not configured"}), 503

    client_key = _client_key()
    retry_after = _login_retry_after(client_key, configuration)
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    password_hash = users.get(username, _DUMMY_PASSWORD_HASH)
    try:
        valid_password = check_password_hash(password_hash, password)
    except (TypeError, ValueError):
        return jsonify({"msg": "Authentication is not configured"}), 503
    if not valid_password:
        retry_after = _record_login_failure(client_key, configuration)
        if retry_after is not None:
            return _rate_limited_response(retry_after)
        return jsonify({"msg": "Bad username or password"}), 401

    _clear_login_failures(client_key)
    access_token = create_access_token(identity=username)
    response = jsonify({"login": True})
    set_access_cookies(response, access_token)
    return response

@auth.route('/api/logout', methods=['POST'])
def logout():
    response = jsonify({"logout": True})
    unset_jwt_cookies(response)
    return response

@auth.route('/api/status', methods=['GET'])
@jwt_required()
def status():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Hello {current_user}, welcome to Flask!"})
