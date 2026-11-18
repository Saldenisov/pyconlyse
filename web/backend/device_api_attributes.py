"""Generic Tango device inspection, attributes and commands."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
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


    def get_device_summary(device_name):
        """Get fast device summary for lazy UI loading."""
        try:
            summary = api.DeviceManager.get_device_summary(device_name)
            return api.jsonify({'device_info': summary, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_device_commands(device_name):
        """Get device command list and input/output metadata."""
        try:
            device = api.DeviceManager.get_device(device_name)
            commands = api.DeviceManager.get_device_commands(device)
            return api.jsonify({'commands': commands, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_device_attributes(device_name):
        """Get all device attributes"""
        try:
            device = api.DeviceManager.get_device(device_name)
            attributes = api.DeviceManager.get_device_attributes(device)

            return api.jsonify({'attributes': attributes, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def handle_attribute(device_name, attr_name):
        """Read or write a specific attribute"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                attr = device.read_attribute(attr_name)
                return api.jsonify({
                    'attribute': attr_name,
                    'value': attr.value if hasattr(attr, 'value') else None,
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
                    'value': attr.value if hasattr(attr, 'value') else None,
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                    'success': True
                })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


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
                'result': result,
                'verified_states': verified_states,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            api.traceback.print_exc()
            return api.jsonify({'error': str(e), 'traceback': api.traceback.format_exc(), 'success': False}), 500


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


    def get_device_properties(device_name):
        """Get raw Tango device properties as a flat JSON object."""
        try:
            properties = api.DeviceManager.get_device_properties(device_name)

            properties['success'] = True
            return api.jsonify(properties)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    api.get_device_info = get_device_info
    api.get_device_summary = get_device_summary
    api.get_device_commands = get_device_commands
    api.get_device_attributes = get_device_attributes
    api.handle_attribute = handle_attribute
    api.execute_command = execute_command
    api.get_device_state = get_device_state
    api.get_device_properties = get_device_properties
