"""Centre/mode preferences and read-only diagnostics; no motion dispatcher."""
import json
from flask import Blueprint, jsonify, request

from mutation_auth import install_mutation_auth
from supervision_diagnostics import ObservationConflict, RevisionConflict


def create_diagnostics_api(service):
    api = Blueprint('supervision_diagnostics_api', __name__, url_prefix='/api/elyse/supervision/diagnostics')
    install_mutation_auth(api, protected_get_endpoints=('get_diagnostics',))

    @api.after_request
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def failure(error):
        if isinstance(error, (RevisionConflict, ObservationConflict)):
            return jsonify(schema_version=1, error=str(error), execution_allowed=False, hardware_writes=False), 409
        if isinstance(error, ValueError):
            return jsonify(schema_version=1, error=str(error), execution_allowed=False, hardware_writes=False), 400
        return jsonify(schema_version=1, error='Diagnostics PostgreSQL state unavailable',
                       execution_allowed=False, hardware_writes=False), 503

    @api.get('')
    def get_diagnostics():
        try:
            if set(request.args) - {'camera_id'} or len(request.args.getlist('camera_id')) > 1:
                raise ValueError('At most one camera_id required')
            return jsonify(service.snapshot(request.args.get('camera_id')))
        except Exception as error:
            return failure(error)

    def body():
        if request.content_length is not None and request.content_length > 2048:
            raise ValueError('Bounded diagnostics request required')
        # The existing authenticated audit hook reads/caches JSON first.
        # Respect that cache instead of reading its now-exhausted stream.
        raw = request.get_data(cache=True) if hasattr(request, '_cached_data') else request.stream.read(2049)
        if not raw or len(raw) > 2048:
            raise ValueError('Bounded diagnostics request required')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ValueError('JSON object required')
        if type(value) is not dict:
            raise ValueError('JSON object required')
        return value

    @api.post('/reference')
    def save_reference():
        try:
            return jsonify(service.save_reference(body()))
        except Exception as error:
            return failure(error)

    @api.post('/mode')
    def set_mode():
        try:
            return jsonify(service.set_mode(body()))
        except Exception as error:
            return failure(error)

    return api
