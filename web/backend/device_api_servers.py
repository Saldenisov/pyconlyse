"""device api servers operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _catalog_device_state(device_name):
        """Read state through the existing DeviceManager cache without retries."""
        return str(api.DeviceManager.get_device(device_name).state())


    def _get_starter_devices():
        db = api.tango_gateway.create_database()
        devices = list(db.get_device_exported("*"))
        return [device_name for device_name in devices if str(device_name).startswith("tango/admin/")]


    def _get_starter_server_lists(starter_name):
        starter = api.tango_gateway.create_device_proxy(starter_name)
        # True includes every server managed by this Starter, not only controlled ones.
        running = set(starter.command_inout('DevGetRunningServers', True))
        stopped = set(starter.command_inout('DevGetStopServers', True))
        return starter, running, stopped


    def _wait_for_starter_server(starter_name, server_name, timeout_s=12.0):
        """Wait until Starter reports a server as running after a control command."""
        deadline = api.time.monotonic() + max(0.0, float(timeout_s))
        while True:
            _, running, stopped = api._get_starter_server_lists(starter_name)
            if server_name in running or api.time.monotonic() >= deadline:
                return running, stopped
            api.time.sleep(0.5)


    def _find_starter_for_server(server_name, allow_db_host_fallback=False):
        for starter_name in api._get_starter_devices():
            try:
                starter, running, stopped = api._get_starter_server_lists(starter_name)
            except Exception:
                continue
            if server_name in running or server_name in stopped:
                return starter_name, starter, running, stopped

        if allow_db_host_fallback:
            try:
                server_info = api.tango_gateway.create_database().get_server_info(server_name)
                host = str(getattr(server_info, "host", "")).strip().lower()
                if host:
                    short_host = host.split(".", 1)[0]
                    starter_name = next(
                        (
                            str(candidate)
                            for candidate in api._get_starter_devices()
                            if str(candidate).rsplit("/", 1)[-1].lower()
                            in {host, short_host}
                        ),
                        f"tango/admin/{short_host}",
                    )
                    starter, running, stopped = api._get_starter_server_lists(starter_name)
                    return starter_name, starter, running, stopped
            except Exception:
                pass

        raise Exception(f"No Starter manages server {server_name}")


    def _is_already_running_error(exc):
        text = str(exc).lower()
        return 'already_running' in text or 'already running' in text


    def _resolve_server_name(device_name):
        db = api.tango_gateway.create_database()
        try:
            return api.DeviceManager.get_device(device_name).info().server_id
        except Exception:
            info = db.get_device_info(device_name)
            server_name = getattr(info, 'ds_full_name', None) or getattr(info, 'server', None)
            if not server_name:
                raise Exception(f"Could not resolve server for device {device_name}")
        return str(server_name)


    def _tail_log_text(value, line_limit=240, char_limit=60000):
        """Bound a Starter log response before returning it to a browser client."""
        text = str(value or "").replace("\r\n", "\n")
        truncated = len(text) > char_limit
        if truncated:
            text = text[-char_limit:]

        lines = text.splitlines()
        if len(lines) > line_limit:
            truncated = True
            lines = lines[-line_limit:]
        return "\n".join(lines), truncated


    def _read_starter_log(starter, log_name):
        """Read a log captured by Tango Starter without making any equipment call."""
        try:
            text, truncated = api._tail_log_text(starter.command_inout("DevReadLog", log_name))
            return {
                "available": True,
                "text": text,
                "truncated": truncated,
                "error": "",
            }
        except Exception as exc:
            return {
                "available": False,
                "text": "",
                "truncated": False,
                "error": str(exc),
            }


    def _read_device_diagnostics(device_name):
        """Return state, status, and common server-reported error attributes."""
        result = {
            "name": device_name,
            "available": False,
            "state": "UNREACHABLE",
            "status": "",
            "error_attributes": {},
            "error": "",
        }
        try:
            def read_diagnostics():
                device = api.DeviceManager.get_device(device_name)
                try:
                    attr_names = {str(name).lower(): str(name) for name in device.get_attribute_list()}
                except Exception:
                    attr_names = {}

                error_attributes = {}
                for candidate in (
                    "last_error",
                    "error",
                    "error_message",
                    "fault_recovery_status",
                    "connection_status",
                    "controller_connection_status",
                    "power_dependency_status",
                    "hardware_connection_state",
                    "initialization_state",
                    "hardware_lifecycle_status",
                ):
                    attr_name = attr_names.get(candidate)
                    if not attr_name:
                        continue
                    try:
                        value = api.make_json_safe(device.read_attribute(attr_name).value)
                    except Exception as exc:
                        value = {"error": str(exc)}
                    error_attributes[attr_name] = value
                return str(device.state()), str(device.status()), error_attributes

            state, status, error_attributes = api._with_device_retry(device_name, read_diagnostics)
            result.update({
                "available": True,
                "state": state,
                "status": status,
                "error_attributes": error_attributes,
            })
        except Exception as exc:
            result["error"] = str(exc)
        return result


    def get_server_diagnostics(server_name):
        """Read-only operational diagnostics for one Tango server and its device."""
        try:
            device_name = str(api.request.args.get("device_name", "")).strip()
            if not device_name:
                return api.jsonify({"success": False, "error": "device_name is required"}), 400

            device = api._read_device_diagnostics(device_name)
            starter_name = ""
            running = set()
            stopped = set()
            starter_error = ""
            server_log = {"available": False, "text": "", "truncated": False, "error": ""}
            starter_log = {"available": False, "text": "", "truncated": False, "error": ""}

            try:
                starter_name, starter, running, stopped = api._find_starter_for_server(
                    server_name,
                    allow_db_host_fallback=True,
                )
                server_log = api._read_starter_log(starter, server_name)
                starter_log = api._read_starter_log(starter, "Starter")
            except Exception as exc:
                starter_error = str(exc)
                server_log["error"] = starter_error
                starter_log["error"] = starter_error

            capture_note = ""
            if not server_log["available"]:
                capture_note = "Tango Starter log is unavailable. "
                if starter_error:
                    capture_note += "Starter could not be contacted."
                else:
                    capture_note += "The server may be writing only to its terminal window."

            return api.jsonify({
                "success": True,
                "server_name": server_name,
                "starter": starter_name,
                "running": server_name in running,
                "stopped": server_name in stopped,
                "starter_error": starter_error,
                "device": device,
                "server_log": server_log,
                "starter_log": starter_log,
                "capture_note": capture_note,
                "timestamp": api.datetime.now().isoformat(),
            })
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 500


    def _collect_device_list(probe_state, include_dserver, include_admin):
        """Compatibility facade for the shared read-only snapshot collector."""
        return api._device_snapshot_service.collect(probe_state, include_dserver, include_admin)


    def _refresh_device_list_cache(cache_key):
        """Compatibility facade for a shared snapshot cache refresh."""
        return api._device_snapshot_service.refresh(cache_key)


    def _schedule_device_list_refresh(cache_key):
        """Compatibility facade for one-flight shared snapshot refreshes."""
        return api._device_snapshot_service.schedule_refresh(cache_key)


    def start_device_snapshot_monitor(interval_s=10.0):
        """Keep the dashboard snapshot warm while the web backend is running."""
        return api._device_snapshot_service.start_monitor(interval_s)


    def list_devices():
        """Get list of all available devices"""
        try:
            probe_state = api._query_bool('probe_state', False)
            include_dserver = api._query_bool('include_dserver', True)
            include_admin = api._query_bool('include_admin', False)
            refresh = api._query_bool('refresh', False)
            stale_ok = api._query_bool('stale_ok', False)
            cache_ttl_s = float(api.os.environ.get('PYCONLYSE_DEVICE_LIST_CACHE_TTL', '4.0'))
            snapshot = api._device_snapshot_service.get_snapshot(
                probe_state,
                include_dserver,
                include_admin,
                refresh=refresh,
                stale_ok=stale_ok,
                cache_ttl_s=cache_ttl_s,
                schedule_refresh=api._schedule_device_list_refresh,
            )
            return api.jsonify({**snapshot, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def control_server():
        """Control a device server through its Starter."""
        try:
            api._maybe_require_auth()
            data = api._hardware_payload()
            if data is None:
                return api._invalid_hardware_payload()
            raw_action = data.get('action', '')
            action = raw_action.strip().lower() if isinstance(raw_action, str) else ''
            server_name = data.get('server_name')
            device_name = data.get('device_name')

            if action not in {'start', 'restart', 'hard_kill'}:
                return api.jsonify({'error': 'Unsupported action', 'success': False}), 400

            if api.authorization_required() and not server_name:
                return api.jsonify({'error': 'server_name is required', 'success': False}), 400
            if not server_name and device_name:
                server_name = api._resolve_server_name(str(device_name))

            if not isinstance(server_name, str) or not server_name.strip():
                return api.jsonify({'error': 'server_name or device_name is required', 'success': False}), 400

            server_name = server_name.strip()
            trusted_starter = None
            if api.authorization_required():
                config = api.authorization_config_from_environment()
                trusted_starter = api.trusted_starter_for_server(
                    api.load_policy(config.policy_path, strict=True), server_name
                )
            target_commands = {
                'start': ('DevStart',),
                'hard_kill': ('HardKillServer',),
                'restart': ('DevStop', 'DevStart'),
            }[action]
            blocked = api.require_http_hardware(
                action=action,
                targets=[{'device': trusted_starter or server_name, 'command': command} for command in target_commands],
                args={'action': action, 'server_name': server_name},
                route_id='server.control',
                wrapper_fields={'action', 'server_name'},
            )
            if blocked is not None:
                return blocked

            if trusted_starter is not None:
                starter_name = trusted_starter
                starter, running_before, stopped_before = api._get_starter_server_lists(starter_name)
            else:
                starter_name, starter, running_before, stopped_before = api._find_starter_for_server(server_name)

            if action == 'start':
                try:
                    starter.command_inout('DevStart', server_name)
                except Exception as exc:
                    if not api._is_already_running_error(exc):
                        raise
            elif action == 'hard_kill':
                starter.command_inout('HardKillServer', server_name)
                api.time.sleep(2)
            elif action == 'restart':
                try:
                    starter.command_inout('DevStop', server_name)
                    api.time.sleep(2)
                except Exception:
                    pass
                try:
                    starter.command_inout('DevStart', server_name)
                except Exception as exc:
                    if not api._is_already_running_error(exc):
                        raise

            if action in {'start', 'restart'}:
                running_after, stopped_after = api._wait_for_starter_server(starter_name, server_name)
            else:
                _, running_after, stopped_after = api._get_starter_server_lists(starter_name)

            running = server_name in running_after
            stopped = server_name in stopped_after
            if action in {'start', 'restart'} and not running:
                return api.jsonify({
                    'success': False,
                    'action': action,
                    'server_name': server_name,
                    'starter': starter_name,
                    'running': False,
                    'stopped': stopped,
                    'error': (
                        f'{server_name} did not register with {starter_name} within 12 seconds. '
                        'Check the server console and hardware power.'
                    ),
                }), 503

            # Preserve the last snapshot for clients, then refresh it in the background.
            api._schedule_device_list_refresh((True, True, True))

            return api.jsonify({
                'success': True,
                'action': action,
                'server_name': server_name,
                'starter': starter_name,
                'running': running,
                'stopped': stopped,
                'running_count': len(running_after),
                'stopped_count': len(stopped_after),
            })
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    api._catalog_device_state = _catalog_device_state
    api._get_starter_devices = _get_starter_devices
    api._get_starter_server_lists = _get_starter_server_lists
    api._wait_for_starter_server = _wait_for_starter_server
    api._find_starter_for_server = _find_starter_for_server
    api._is_already_running_error = _is_already_running_error
    api._resolve_server_name = _resolve_server_name
    api._tail_log_text = _tail_log_text
    api._read_starter_log = _read_starter_log
    api._read_device_diagnostics = _read_device_diagnostics
    api.get_server_diagnostics = get_server_diagnostics
    api._collect_device_list = _collect_device_list
    api._refresh_device_list_cache = _refresh_device_list_cache
    api._schedule_device_list_refresh = _schedule_device_list_refresh
    api.start_device_snapshot_monitor = start_device_snapshot_monitor
    api.list_devices = list_devices
    api.control_server = control_server
