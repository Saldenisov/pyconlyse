import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parents[2] / "web" / "backend"


@pytest.fixture
def auth_module(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    module = importlib.import_module("auth")
    module.reset_login_rate_limiter()
    yield module
    module.reset_login_rate_limiter()
    sys.modules.pop("auth", None)


@pytest.fixture
def auth_client(auth_module, monkeypatch):
    monkeypatch.setenv(
        "PYCONLYSE_AUTH_USERS",
        '{"known-user": "' + generate_password_hash("correct-password") + '"}',
    )
    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_CSRF_PROTECT=False,
    )
    JWTManager(app)
    app.register_blueprint(auth_module.auth)
    return app.test_client()


def _login(client, username, password, address="198.51.100.17"):
    return client.post(
        "/api/login",
        json={"username": username, "password": password},
        environ_overrides={"REMOTE_ADDR": address},
    )


def test_login_limit_blocks_repeated_failures_without_username_enumeration(
    auth_client, monkeypatch
):
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "30")

    unknown_user = _login(auth_client, "unknown-user", "wrong-password")
    known_user = _login(auth_client, "known-user", "wrong-password")
    blocked = _login(auth_client, "another-user", "wrong-password")

    assert unknown_user.status_code == known_user.status_code == 401
    assert unknown_user.get_json() == known_user.get_json() == {
        "msg": "Bad username or password"
    }
    assert blocked.status_code == 429
    assert blocked.get_json() == {"msg": "Too many login attempts"}
    assert blocked.headers["Retry-After"] == "30"


def test_successful_login_clears_prior_failures(auth_client, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS", "3")

    assert _login(auth_client, "known-user", "wrong-password").status_code == 401
    assert _login(auth_client, "unknown-user", "wrong-password").status_code == 401
    assert _login(auth_client, "known-user", "correct-password").status_code == 200
    assert _login(auth_client, "known-user", "wrong-password").status_code == 401
    assert _login(auth_client, "known-user", "wrong-password").status_code == 401


def test_expired_failures_are_pruned_using_monotonic_time(
    auth_client, auth_module, monkeypatch
):
    clock = [100.0]
    monkeypatch.setattr(auth_module, "_monotonic", lambda: clock[0])
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS", "1")
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "10")

    assert _login(auth_client, "known-user", "wrong-password").status_code == 401
    assert _login(auth_client, "known-user", "wrong-password").status_code == 429
    clock[0] += 10
    assert _login(auth_client, "known-user", "wrong-password").status_code == 401


def test_limiter_state_is_bounded_and_fails_closed_at_capacity(auth_module):
    configuration = auth_module.LoginRateLimitConfiguration(
        attempts=3, window_seconds=60, max_keys=1
    )

    assert auth_module._record_login_failure("first-client", configuration) is None
    assert auth_module._login_retry_after("second-client", configuration) == 60
    assert list(auth_module._LOGIN_FAILURES) == ["first-client"]


def test_limiter_records_failures_atomically_under_concurrency(auth_module):
    configuration = auth_module.LoginRateLimitConfiguration(
        attempts=3, window_seconds=60, max_keys=10
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: auth_module._record_login_failure(
                    "same-client", configuration
                ),
                range(8),
            )
        )

    assert results.count(None) == 3
    assert all(result is None or result >= 1 for result in results)
    assert len(auth_module._LOGIN_FAILURES["same-client"]) == 3


@pytest.mark.parametrize("value", ("0", "not-a-number", "1001"))
def test_rate_limit_configuration_rejects_invalid_attempt_limits(
    auth_module, monkeypatch, value
):
    monkeypatch.setenv("PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS", value)

    with pytest.raises(RuntimeError, match="PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS"):
        auth_module.login_rate_limit_configuration()
