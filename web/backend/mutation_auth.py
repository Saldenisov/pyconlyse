"""Blueprint-level authentication for HTTP requests that can change state.

This guard is process-local configuration: it relies on Flask-JWT-Extended for
token and CSRF validation.  It protects unsafe methods in production, while
local development remains opt-in through PYCONLYSE_ENFORCE_DEVICE_AUTH.
"""

import os

from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError

UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def mutation_auth_required():
    """Require auth in production, or when local device auth is explicitly enabled."""
    return _env_bool("PYCONLYSE_PRODUCTION", False) or _env_bool(
        "PYCONLYSE_ENFORCE_DEVICE_AUTH", False
    )


def install_mutation_auth(blueprint, protected_get_endpoints=()):
    """Guard unsafe requests.

    GET, HEAD, and OPTIONS remain public unless their endpoint is explicitly named.
    """
    protected_endpoints = {
        f"{blueprint.name}.{endpoint}" for endpoint in protected_get_endpoints
    }

    @blueprint.before_request
    def require_mutation_authentication():
        if not mutation_auth_required():
            return None
        if (
            request.method in UNSAFE_HTTP_METHODS
            or request.endpoint in protected_endpoints
        ):
            try:
                verify_jwt_in_request()
            except (JWTExtendedException, PyJWTError):
                # Blueprint-wide Exception handlers must not convert JWT/CSRF
                # rejection into a 500 response or execute a mutable handler.
                return (
                    jsonify({"msg": "Missing or invalid authentication credentials"}),
                    401,
                )
        return None
