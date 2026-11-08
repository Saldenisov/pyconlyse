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
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from werkzeug.security import check_password_hash, generate_password_hash

auth = Blueprint("auth", __name__)
_REPOSITORY_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MAX_AUTH_USERS_BYTES = 1024 * 1024


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
    return bool(separator and salt and encoded_hash) and method.startswith(
        ("scrypt:", "pbkdf2:")
    )


def _normalise_account(username, value):
    """Return one validated account while accepting the legacy hash format."""
    if isinstance(value, str):
        password_hash = value
        roles = []
    elif isinstance(value, dict) and set(value) == {"password_hash", "roles"}:
        password_hash = value.get("password_hash")
        roles = value.get("roles")
        if (
            not isinstance(roles, list)
            or not all(isinstance(role, str) and role.strip() for role in roles)
            or len(set(roles)) != len(roles)
        ):
            raise RuntimeError(
                f"PYCONLYSE_AUTH_USERS roles for {username!r} must be unique strings"
            )
        roles = [role.strip() for role in roles]
    else:
        raise RuntimeError(
            "PYCONLYSE_AUTH_USERS values must be password hashes or account objects"
        )

    if not isinstance(password_hash, str) or not _is_supported_password_hash(
        password_hash
    ):
        raise RuntimeError("PYCONLYSE_AUTH_USERS must contain Werkzeug password hashes")
    try:
        check_password_hash(password_hash, "configuration-validation")
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "PYCONLYSE_AUTH_USERS must contain Werkzeug password hashes"
        ) from exc
    return {"password_hash": password_hash, "roles": roles}


def _configured_accounts_json():
    raw_users = os.environ.get("PYCONLYSE_AUTH_USERS", "").strip()
    users_file = os.environ.get("PYCONLYSE_AUTH_USERS_FILE", "").strip()
    if raw_users and users_file:
        raise RuntimeError(
            "Set only one of PYCONLYSE_AUTH_USERS or PYCONLYSE_AUTH_USERS_FILE"
        )
    if raw_users:
        return raw_users
    if not users_file:
        return ""

    path = os.path.realpath(users_file)
    if (
        not os.path.isabs(users_file)
        or not os.path.isfile(path)
        or os.path.islink(users_file)
    ):
        raise RuntimeError("PYCONLYSE_AUTH_USERS_FILE must be an absolute regular file")
    if os.environ.get("PYCONLYSE_PRODUCTION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }:
        try:
            inside_repository = (
                os.path.commonpath([path, _REPOSITORY_ROOT]) == _REPOSITORY_ROOT
            )
        except ValueError:
            inside_repository = False
        if inside_repository:
            raise RuntimeError(
                "PYCONLYSE_AUTH_USERS_FILE must be outside the repository in production"
            )
    try:
        size = os.path.getsize(path)
        if size > _MAX_AUTH_USERS_BYTES:
            raise RuntimeError("PYCONLYSE_AUTH_USERS_FILE is too large")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read(_MAX_AUTH_USERS_BYTES + 1)
    except OSError as exc:
        raise RuntimeError("PYCONLYSE_AUTH_USERS_FILE cannot be read") from exc


def configured_accounts(required=False):
    """Return validated accounts configured through PYCONLYSE_AUTH_USERS."""
    login_rate_limit_configuration()
    raw_users = _configured_accounts_json().strip()
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
    if not all(isinstance(username, str) and username.strip() for username in users):
        raise RuntimeError("PYCONLYSE_AUTH_USERS usernames must be non-empty strings")
    return {
        username: _normalise_account(username, value)
        for username, value in users.items()
    }


def configured_users(required=False):
    """Return the legacy username-to-password-hash view used by callers."""
    return {
        username: account["password_hash"]
        for username, account in configured_accounts(required=required).items()
    }


@auth.route("/api/login", methods=["POST"])
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
        accounts = configured_accounts()
    except RuntimeError:
        return jsonify({"msg": "Authentication is not configured"}), 503
    if not accounts:
        return jsonify({"msg": "Authentication is not configured"}), 503

    client_key = _client_key()
    retry_after = _login_retry_after(client_key, configuration)
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    account = accounts.get(username)
    password_hash = (
        account["password_hash"] if account is not None else _DUMMY_PASSWORD_HASH
    )
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
    roles = account["roles"]
    access_token = create_access_token(
        identity=username,
        additional_claims={"roles": roles},
    )
    response = jsonify({"login": True})
    set_access_cookies(response, access_token)
    return response


@auth.route("/api/logout", methods=["POST"])
def logout():
    response = jsonify({"logout": True})
    unset_jwt_cookies(response)
    return response


@auth.route("/api/status", methods=["GET"])
@jwt_required()
def status():
    current_user = get_jwt_identity()
    roles = get_jwt().get("roles", [])
    return jsonify({"authenticated": True, "username": current_user, "roles": roles})
