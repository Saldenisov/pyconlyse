"""Implementation for list_devices and related operations."""


def _bind_device_api_parts_list_devices(api):
    """Bind implementation to the owning module and its runtime state."""

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

    list_devices.__module__ = api.__name__
    list_devices.__qualname__ = "list_devices"

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

    control_server.__module__ = api.__name__
    control_server.__qualname__ = "control_server"

    def get_device_info(device_name):
        """Get detailed device information"""
        try:
            include_properties = api._query_bool('include_properties', True)
            include_attributes = api._query_bool('include_attributes', True)
            include_commands = api._query_bool('include_commands', True)

            info = api.DeviceManager.get_device_summary(device_name)
            device = api.DeviceManager.get_device(device_name)

            if include_properties:
                try:
                    info['properties'] = api.DeviceManager.get_device_properties(device_name)
                except Exception as e:
                    info['properties_error'] = str(e)

            if include_attributes:
                try:
                    info['attributes'] = api.DeviceManager.get_device_attributes(device)
                except Exception as e:
                    info['attributes_error'] = str(e)

            if include_commands:
                try:
                    info['commands'] = api.DeviceManager.get_device_commands(device)
                except Exception as e:
                    info['commands_error'] = str(e)

            return api.jsonify({'device_info': info, 'success': True})
        except Exception as e:
            return api.jsonify({
                'device_info': {
                    'name': device_name,
                    'connected': False,
                    'error': str(e),
                    'timestamp': api.datetime.now().isoformat()
                },
                'error': str(e),
                'success': False
            }), 500

    get_device_info.__module__ = api.__name__
    get_device_info.__qualname__ = "get_device_info"

    def get_device_summary(device_name):
        """Get fast device summary for lazy UI loading."""
        try:
            summary = api.DeviceManager.get_device_summary(device_name)
            return api.jsonify({'device_info': summary, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_device_summary.__module__ = api.__name__
    get_device_summary.__qualname__ = "get_device_summary"

    def get_device_commands(device_name):
        """Get device command list and input/output metadata."""
        try:
            device = api.DeviceManager.get_device(device_name)
            commands = api.DeviceManager.get_device_commands(device)
            return api.jsonify({'commands': commands, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_device_commands.__module__ = api.__name__
    get_device_commands.__qualname__ = "get_device_commands"

    def get_device_attributes(device_name):
        """Get all device attributes"""
        try:
            device = api.DeviceManager.get_device(device_name)
            attributes = api.DeviceManager.get_device_attributes(device)

            return api.jsonify({'attributes': attributes, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_device_attributes.__module__ = api.__name__
    get_device_attributes.__qualname__ = "get_device_attributes"

    def handle_attribute(device_name, attr_name):
        """Read or write a specific attribute"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                attr = device.read_attribute(attr_name)
                return api.jsonify({
                    'attribute': attr_name,
                    'value': api.make_json_safe(attr.value) if hasattr(attr, 'value') else None,
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                    'success': True
                })

            elif api.request.method == 'POST':
                api._maybe_require_auth()
                data = api._hardware_payload()
                if data is None:
                    return api._invalid_hardware_payload()
                if 'value' not in data:
                    return api.jsonify({'error': 'No value provided', 'success': False}), 400
                value = data['value']

                if value is None:
                    return api.jsonify({'error': 'No value provided', 'success': False}), 400

                blocked = api.require_http_hardware(
                    action='write',
                    targets=[{'device': str(device_name), 'command': 'write_attribute'}],
                    args={'attribute': str(attr_name), 'value': value},
                    route_id='device.attribute',
                    wrapper_fields={'value'},
                )
                if blocked is not None:
                    return blocked

                device = api.DeviceManager.get_device(device_name)
                device.write_attribute(attr_name, value)
                # Read back the attribute to confirm
                attr = device.read_attribute(attr_name)

                return api.jsonify({
                    'attribute': attr_name,
                    'value': api.make_json_safe(attr.value) if hasattr(attr, 'value') else None,
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                    'success': True
                })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    handle_attribute.__module__ = api.__name__
    handle_attribute.__qualname__ = "handle_attribute"

    def execute_command(device_name, command_name):
        """Execute a device command"""
        try:
            api._maybe_require_auth()
            data = api._hardware_payload()
            if data is None:
                return api._invalid_hardware_payload()
            args = data.get('args')
            blocked = api.require_http_hardware(
                action='execute',
                targets=[{'device': str(device_name), 'command': str(command_name)}],
                args=args,
                route_id='device.command',
                wrapper_fields={'args'},
            )
            if blocked is not None:
                return blocked

            def run_command():
                device = api.DeviceManager.get_device(device_name)
                if args is not None:
                    return device, device.command_inout(command_name, args)
                return device, device.command_inout(command_name)

            device, result = api._with_device_retry(device_name, run_command)

            # DS_Netio_pdu can return "success" even when hardware state does not change.
            # For set_channels_states, verify readback and surface mismatch as an API error.
            verified_states = None
            if str(command_name).lower() == "set_channels_states":
                requested_states = api._coerce_binary_state_args(args)
                if requested_states is not None:
                    matched, observed_states = api._wait_for_pdu_states(device, requested_states)
                    if not matched:
                        return api.jsonify({
                            'error': (
                                f"Command {command_name} executed, but readback states do not "
                                "match requested values."
                            ),
                            'command': command_name,
                            'requested_states': requested_states,
                            'observed_states': observed_states,
                            'success': False
                        }), 409
                    verified_states = observed_states

            return api.jsonify({
                'command': command_name,
                'result': api.make_json_safe(result),
                'verified_states': verified_states,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            api.traceback.print_exc()
            return api.jsonify({'error': str(e), 'traceback': api.traceback.format_exc(), 'success': False}), 500

    execute_command.__module__ = api.__name__
    execute_command.__qualname__ = "execute_command"

    def get_device_state(device_name):
        """Get device state and status"""
        try:
            def read_state():
                device = api.DeviceManager.get_device(device_name)
                return device, str(device.state()), device.status()

            device, state, status = api._with_device_retry(device_name, read_state)
            return api.jsonify({
                'device': device_name,
                'state': state,
                'status': status,
                'timestamp': api.datetime.now().isoformat(),
                'success': True
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_device_state.__module__ = api.__name__
    get_device_state.__qualname__ = "get_device_state"

    def get_device_properties(device_name):
        """Get raw Tango device properties as a flat JSON object."""
        try:
            properties = api.DeviceManager.get_device_properties(device_name)

            properties['success'] = True
            return api.jsonify(properties)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_device_properties.__module__ = api.__name__
    get_device_properties.__qualname__ = "get_device_properties"

    return {
        "list_devices": list_devices,
        "control_server": control_server,
        "get_device_info": get_device_info,
        "get_device_summary": get_device_summary,
        "get_device_commands": get_device_commands,
        "get_device_attributes": get_device_attributes,
        "handle_attribute": handle_attribute,
        "execute_command": execute_command,
        "get_device_state": get_device_state,
        "get_device_properties": get_device_properties,
    }
