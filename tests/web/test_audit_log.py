import importlib
import json
import sqlite3
import sys
from pathlib import Path

from flask import Blueprint, Flask, jsonify
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_admin_role_is_placed_in_jwt_and_mutation_is_audited(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.sqlite3"
    account = {
        "sad": {
            "password_hash": generate_password_hash("a-secure-test-password"),
            "roles": ["admin"],
        }
    }
    monkeypatch.setenv("PYCONLYSE_AUTH_USERS", json.dumps(account))
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    monkeypatch.setenv("PYCONLYSE_AUDIT_DB_PATH", str(audit_path))

    auth_module = importlib.import_module("auth")
    audit_module = importlib.import_module("audit_log")
    mutation_module = importlib.import_module("mutation_auth")

    app = Flask(__name__)
    app.config.update(
        JWT_SECRET_KEY="test-secret",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_CSRF_PROTECT=False,
    )
    JWTManager(app)
    audit_module.install_audit_log(app)
    app.register_blueprint(auth_module.auth)

    protected = Blueprint("protected_audit_test", __name__)
    mutation_module.install_mutation_auth(protected)

    @protected.post("/api/test-change")
    def change():
        return jsonify({"success": True})

    app.register_blueprint(protected)
    client = app.test_client()
    assert (
        client.post(
            "/api/login", json={"username": "sad", "password": "a-secure-test-password"}
        ).status_code
        == 200
    )
    status = client.get("/api/status").get_json()
    assert status == {"authenticated": True, "username": "sad", "roles": ["admin"]}

    assert client.post("/api/test-change", json={"value": 12}).status_code == 200
    with sqlite3.connect(str(audit_path)) as connection:
        row = connection.execute(
            """
            SELECT subject, roles_json, method, path, request_json, status_code,
                   response_json, outcome, duration_ms, entry_version,
                   previous_hash, entry_hash
            FROM audit_event
            """
        ).fetchone()

    assert row[:6] == (
        "sad",
        '["admin"]',
        "POST",
        "/api/test-change",
        '{"value":12}',
        200,
    )
    assert row[6] == '{"success":true}'
    assert row[7] == "success"
    assert row[8] >= 0
    assert row[9] == 2
    assert row[10] == "0" * 64
    assert len(row[11]) == 64

    with app.test_request_context("/socket.io", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        audit_module.record_websocket_mutation(
            subject="sad",
            roles=["admin"],
            device="manip/test/1",
            command="heartbeat",
            args=None,
            status_code=200,
            result="alive",
        )
        audit_module.record_websocket_mutation(
            subject="sad",
            roles=["admin"],
            device="manip/test/1",
            command="set_value",
            args=[1, 2],
            status_code=200,
            result={"accepted": True},
        )
    with sqlite3.connect(str(audit_path)) as connection:
        rows = connection.execute(
            "SELECT command, response_json FROM audit_event ORDER BY sequence"
        ).fetchall()
    assert rows == [(None, '{"success":true}'), ("set_value", '{"accepted":true}')]


def test_accounts_can_be_loaded_from_external_file(monkeypatch, tmp_path):
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "sad": {
                    "password_hash": generate_password_hash("test-password"),
                    "roles": ["admin"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("PYCONLYSE_AUTH_USERS", raising=False)
    monkeypatch.setenv("PYCONLYSE_AUTH_USERS_FILE", str(users_file.resolve()))
    auth_module = importlib.import_module("auth")

    accounts = auth_module.configured_accounts(required=True)

    assert accounts["sad"]["roles"] == ["admin"]
