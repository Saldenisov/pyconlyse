"""Device request parsing, authorization errors and mutation validation."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _env_bool(name, default=False):
        value = api.os.environ.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


    def _query_bool(name, default=False):
        value = api.request.args.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


    def _maybe_require_auth():
        if api._env_bool("PYCONLYSE_PRODUCTION", False) or api._env_bool(
            "PYCONLYSE_ENFORCE_DEVICE_AUTH", False
        ):
            api.verify_jwt_in_request()


    def _hardware_payload():
        """Return the JSON object used for an authorized hardware mutation."""
        data = api.request.get_json(silent=True)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return None
        return data


    def _invalid_hardware_payload():
        return api.jsonify({'error': 'JSON request body must be an object', 'success': False}), 400


    def _authorization_error_response(exc):
        return api.jsonify({'error': exc.message, 'success': False, 'code': exc.code}), exc.status_code


    def _mutation_payload(required=()):
        data = api._hardware_payload()
        if data is None or not data:
            return None
        if any(name not in data for name in required):
            return None
        return data


    def _finite_number(value):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if api.math.isfinite(number) else None


    def _invalid_psp_acknowledgement():
        if api.authorization_required():
            return api.jsonify({
                'error': 'Hardware request is invalid',
                'success': False,
                'code': 'hardware_approval_invalid',
            }), 409
        return api.jsonify({'error': 'Acknowledgment payload is invalid', 'success': False}), 400


    def _command_variant(data, candidates):
        """Require one exact branch before authorization in an enforced mode."""
        selected = data.get('command_variant')
        if api.authorization_required():
            if not isinstance(selected, str) or selected not in candidates:
                return None
            return selected
        if selected is not None and (not isinstance(selected, str) or selected not in candidates):
            return None
        return selected


    def _parameter_write_plan(data):
        names = sorted(data)
        return (
            [{'name': name, 'value': data[name]} for name in names],
            names,
        )

    api._env_bool = _env_bool
    api._query_bool = _query_bool
    api._maybe_require_auth = _maybe_require_auth
    api._hardware_payload = _hardware_payload
    api._invalid_hardware_payload = _invalid_hardware_payload
    api._authorization_error_response = _authorization_error_response
    api._mutation_payload = _mutation_payload
    api._finite_number = _finite_number
    api._invalid_psp_acknowledgement = _invalid_psp_acknowledgement
    api._command_variant = _command_variant
    api._parameter_write_plan = _parameter_write_plan
