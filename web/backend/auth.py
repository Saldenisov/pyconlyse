# auth.py
import json
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from werkzeug.security import check_password_hash

auth = Blueprint('auth', __name__)


def _is_supported_password_hash(password_hash):
    method, separator, remainder = password_hash.partition("$")
    salt, separator, encoded_hash = remainder.partition("$")
    return (
        bool(separator and salt and encoded_hash)
        and method.startswith(("scrypt:", "pbkdf2:"))
    )


def configured_users(required=False):
    """Return credentials configured through PYCONLYSE_AUTH_USERS."""
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
        users = configured_users()
    except RuntimeError:
        return jsonify({"msg": "Authentication is not configured"}), 503
    if not users:
        return jsonify({"msg": "Authentication is not configured"}), 503

    password_hash = users.get(username)
    try:
        valid_password = password_hash is not None and check_password_hash(
            password_hash, password
        )
    except (TypeError, ValueError):
        return jsonify({"msg": "Authentication is not configured"}), 503
    if not valid_password:
        return jsonify({"msg": "Bad username or password"}), 401

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
