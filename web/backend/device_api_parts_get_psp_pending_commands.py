"""Implementation for get_psp_pending_commands and related operations."""


def _bind_device_api_parts_get_psp_pending_commands(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_psp_pending_commands(device_name):
        """Read pending outbound commands queued for LabVIEW bridge."""
        try:
            if api._query_bool('pop', False):
                return api.jsonify({
                    'error': 'pop=true is disabled; use a guarded mutation endpoint',
                    'success': False,
                }), 400
            device = api.DeviceManager.get_device(device_name)
            commands = api._list_device_commands_lower(device)
            limit = max(1, int(api.request.args.get('limit', 200)))

            cmd_name = commands.get('get_pending_commands_json')
            if not cmd_name:
                return api.jsonify({'error': 'Device does not support pending command queue', 'success': False}), 400

            raw = device.command_inout(cmd_name, limit)
            payload = api._safe_json_loads(raw, default={})
            if not isinstance(payload, dict):
                payload = {}

            items = payload.get('items', [])
            if not isinstance(items, list):
                items = []
            pending_count = api._as_int(payload.get('pending_count'), len(items))

            return api.jsonify({
                'device': device_name,
                'pending_count': pending_count,
                'items': api.make_json_safe(items),
                'popped': False,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_psp_pending_commands.__module__ = api.__name__
    get_psp_pending_commands.__qualname__ = "get_psp_pending_commands"

    def acknowledge_psp_command(device_name):
        """Store LabVIEW execution acknowledgment for one queued command."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload()
            if data is None or set(data) - api._PSP_ACK_FIELDS:
                return api._invalid_psp_acknowledgement()
            if (
                ('id' in data and (isinstance(data['id'], bool) or not isinstance(data['id'], (str, int))))
                or ('command' in data and (not isinstance(data['command'], str) or not data['command'].strip()))
                or ('ok' in data and type(data['ok']) is not bool)
                or any(name in data and not isinstance(data[name], str) for name in ('status', 'error', 'message', 'timestamp'))
            ):
                return api._invalid_psp_acknowledgement()
            command_variant = api._command_variant(data, api._PSP_ACK_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api._invalid_psp_acknowledgement()
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            acknowledgement = {key: data[key] for key in api._PSP_ACK_FIELDS - {'command_variant'} if key in data}
            blocked = api.require_http_hardware(
                action='acknowledge',
                targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in api._PSP_ACK_COMMANDS],
                args={'command_variant': command_variant or 'legacy_autodetect', 'acknowledgement': acknowledgement},
                route_id='psp.ack', wrapper_fields=api._PSP_ACK_FIELDS,
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)
            if command_variant is not None:
                cmd_name = command_variant
            else:
                commands = api._list_device_commands_lower(device)
                cmd_name = commands.get('acknowledge_command_json')
            if not cmd_name:
                return api.jsonify({'error': 'Device does not support command acknowledgments', 'success': False}), 400
            raw = device.command_inout(cmd_name, api.json.dumps(acknowledgement))
            payload = api._safe_json_loads(raw, default={})
            if not isinstance(payload, dict):
                payload = {'raw': api.make_json_safe(raw)}

            return api.jsonify({'device': device_name, **api.make_json_safe(payload), 'success': True})
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    acknowledge_psp_command.__module__ = api.__name__
    acknowledge_psp_command.__qualname__ = "acknowledge_psp_command"

    def get_daqmx_latest(device_name):
        """Get latest DAQmx/PSP data payload and normalized channel list."""
        try:
            device = api.DeviceManager.get_device(device_name)
            payload = api._read_daqmx_latest_payload(device)
            channels = api._normalize_daqmx_channels(payload)
            device_info = api._read_daqmx_device_info(device)

            return api.jsonify({
                'device': device_name,
                'state': str(device.state()),
                'latest': payload,
                'channels': channels,
                'channel_count': len(channels),
                'device_info': device_info,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_daqmx_latest.__module__ = api.__name__
    get_daqmx_latest.__qualname__ = "get_daqmx_latest"

    def get_daqmx_history(device_name):
        """Get DAQmx history if the device supports get_history_json(seconds)."""
        try:
            device = api.DeviceManager.get_device(device_name)
            seconds = float(api.request.args.get('seconds', 10.0))
            commands = api._list_device_commands_lower(device)
            cmd = commands.get('get_history_json')
            if not cmd:
                return api.jsonify({
                    'error': 'History is not supported by this device',
                    'success': False,
                }), 400

            raw = device.command_inout(cmd, seconds)
            history = api._safe_json_loads(raw, default=[])
            if not isinstance(history, list):
                history = []

            return api.jsonify({
                'device': device_name,
                'seconds': seconds,
                'history': history,
                'sample_count': len(history),
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_daqmx_history.__module__ = api.__name__
    get_daqmx_history.__qualname__ = "get_daqmx_history"

    def write_daqmx_channel(device_name):
        """Write one channel/variable value via DAQmx/PSP write command."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload()
            if data is None:
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            channel_fields = [name for name in ('channel', 'name', 'variable') if data.get(name) not in (None, '')]
            if len(channel_fields) != 1:
                return api.jsonify({'error': 'exactly one channel, name, or variable is required', 'success': False}), 400
            channel = data[channel_fields[0]]
            value = data.get('value')

            if channel in (None, ''):
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            if value is None:
                return api.jsonify({'error': 'value is required', 'success': False}), 400
            if not isinstance(channel, str) or not channel.strip():
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            command_variant = api._command_variant(data, api._DAQMX_WRITE_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            blocked = api.require_http_hardware(
                action='write',
                targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in api._DAQMX_WRITE_COMMANDS],
                args={'channel_selector': channel_fields[0], 'channel': channel.strip(), 'value': api._to_scalar_value(value), 'command_variant': command_variant or 'legacy_autodetect'},
                route_id='daqmx.write', wrapper_fields={'channel', 'name', 'variable', 'value', 'command_variant'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            result = api._write_daqmx_channel(device, channel, value, command_variant=command_variant)
            return api.jsonify({
                'device': device_name,
                'channel': str(channel),
                'value': api._to_scalar_value(value),
                'result': api.make_json_safe(result),
                'success': True,
            })
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    write_daqmx_channel.__module__ = api.__name__
    write_daqmx_channel.__qualname__ = "write_daqmx_channel"

    def reset_daqmx_counter(device_name):
        """Reset one counter exposed by the direct physical-card DAQmx server."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload(required=('channel',))
            if data is None or set(data) - {'channel', 'command_variant'}:
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            channel = data.get('channel')
            if not isinstance(channel, str) or not channel.strip():
                return api.jsonify({'error': 'channel is required', 'success': False}), 400

            command_variant = api._command_variant(data, api._DAQMX_RESET_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            command_name = command_variant or 'reset_counter'
            blocked = api.require_http_hardware(
                action='reset',
                targets=[{'device': str(device_name), 'command': command_name}],
                args={'channel': channel.strip(), 'command_variant': command_name},
                route_id='daqmx.reset',
                wrapper_fields={'channel', 'command_variant'},
            )
            if blocked is not None:
                return blocked

            device = api.DeviceManager.get_device(device_name)
            commands = api._list_device_commands_lower(device)
            resolved_command = commands.get(command_name.lower())
            if not resolved_command:
                return api.jsonify({
                    'error': 'Device does not support counter reset',
                    'success': False,
                }), 400
            result = device.command_inout(resolved_command, channel.strip())
            return api.jsonify({
                'device': device_name,
                'channel': channel.strip(),
                'result': api.make_json_safe(result),
                'success': True,
            })
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    reset_daqmx_counter.__module__ = api.__name__
    reset_daqmx_counter.__qualname__ = "reset_daqmx_counter"

    def list_cameras():
        """Get list of all available camera devices - fast query from Tango DB"""
        try:
            db = api.tango_gateway.create_database()

            # Query Tango DB for camera device classes directly (much faster!)
            camera_classes = ['DS_Basler_camera', 'DS_ANDOR_CCD', 'DS_AVANTES_CCD']
            camera_list = []

            for dev_class in camera_classes:
                try:
                    # Get all devices of this class from Tango DB
                    device_list = db.get_device_name('*', dev_class)

                    for device_name in device_list:
                        try:
                            device = api.tango_gateway.create_device_proxy(device_name)
                            state = str(device.state())

                            camera_info = {
                                'name': device_name,
                                'state': state,
                                'class': dev_class,
                                'available': True
                            }

                            # Try to get camera-specific info (non-blocking)
                            try:
                                camera_info['serial_number'] = str(device.read_attribute('camera_serial_number').value)
                            except:
                                pass

                            try:
                                camera_info['model_name'] = str(device.read_attribute('camera_model_name').value)
                            except:
                                pass

                            try:
                                camera_info['friendly_name'] = str(device.read_attribute('device_friendly_name').value)
                            except:
                                pass

                            camera_list.append(camera_info)
                        except Exception as e:
                            # Device exists in DB but may not be running
                            camera_list.append({
                                'name': device_name,
                                'state': 'UNKNOWN',
                                'class': dev_class,
                                'available': False,
                                'error': str(e)
                            })
                except Exception as e:
                    # Class not found or other error
                    print(f"No devices found for class {dev_class}: {e}")

            return api.jsonify({'cameras': camera_list, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    list_cameras.__module__ = api.__name__
    list_cameras.__qualname__ = "list_cameras"

    def get_camera_info(device_name):
        """Get detailed camera information"""
        try:
            device = api.DeviceManager.get_device(device_name)

            info = {
                'name': device_name,
                'state': str(device.state()),
                'status': device.status(),
            }

            # Camera-specific attributes
            camera_attrs = [
                'camera_serial_number', 'camera_model_name', 'device_friendly_name',
                'exposure_time', 'exposure_min', 'exposure_max',
                'gain', 'gain_min', 'gain_max',
                'width', 'width_min', 'width_max',
                'height', 'height_min', 'height_max',
                'offsetX', 'offsetY',
                'format_pixel', 'framerate', 'isgrabbing',
                'binning_horizontal', 'binning_vertical',
                'trigger_mode', 'trigger_delay',
                'center_gravity_threshold',
                'cg', 'number_kinetics', 'track_count',
                'wavelengths_axis', 'temperature_current',
                'temperature_target', 'temperature_status',
                'cooler_on', 'linked_spectrograph_device'
            ]

            for attr_name in camera_attrs:
                try:
                    attr = device.read_attribute(attr_name)
                    info[attr_name] = api.make_json_safe(attr.value)
                except:
                    pass

            return api.jsonify({'camera_info': info, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_camera_info.__module__ = api.__name__
    get_camera_info.__qualname__ = "get_camera_info"

    def handle_camera_parameters(device_name):
        """Get or set camera parameters"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                parameters = {}
                param_names = ['exposure_time', 'gain', 'width', 'height', 'offsetX', 'offsetY',
                              'format_pixel', 'trigger_mode', 'trigger_delay', 'binning_horizontal', 'binning_vertical',
                              'number_kinetics', 'center_gravity_threshold']

                for param in param_names:
                    try:
                        attr = device.read_attribute(param)
                        parameters[param] = api.make_json_safe(attr.value)
                    except:
                        pass

                return api.jsonify({'parameters': parameters, 'success': True})

            elif api.request.method == 'POST':
                api._maybe_require_auth()
                data = api._mutation_payload()
                if data is None or set(data) - api._CAMERA_PARAMETER_NAMES:
                    return api.jsonify({'error': 'Camera parameter batch is empty or contains unsupported attributes', 'success': False}), 400
                writes, parameter_names = api._parameter_write_plan(data)
                blocked = api.require_http_hardware(
                    action='write_parameters',
                    targets=[{'device': str(device_name), 'command': 'write_attribute'} for _ in parameter_names],
                    args={'writes': writes}, route_id='camera.parameters', wrapper_fields=api._CAMERA_PARAMETER_NAMES,
                )
                if blocked is not None:
                    return blocked
                device = api.DeviceManager.get_device(device_name)
                results = {}

                for param_name in parameter_names:
                    param_value = data[param_name]
                    try:
                        device.write_attribute(param_name, param_value)
                        # Read back to confirm
                        attr = device.read_attribute(param_name)
                        results[param_name] = {'success': True, 'value': api.make_json_safe(attr.value)}
                    except Exception as e:
                        results[param_name] = {'success': False, 'error': str(e)}

                return api.jsonify({'results': results, 'success': True})

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    handle_camera_parameters.__module__ = api.__name__
    handle_camera_parameters.__qualname__ = "handle_camera_parameters"

    def handle_camera_grabbing(device_name):
        """Control camera grabbing (start/stop)"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                is_grabbing = api._read_camera_is_grabbing(device)
                return api.jsonify({
                    'grabbing': is_grabbing,
                    'success': True
                })

            elif api.request.method == 'POST':
                api._maybe_require_auth()
                data = api._mutation_payload(('action',))
                if data is None or set(data) - {'action', 'command_variant'} or not isinstance(data.get('action'), str):
                    return api.jsonify({'error': 'Invalid action. Use "start" or "stop"', 'success': False}), 400
                action = data.get('action')  # 'start' or 'stop'
                if action not in api._CAMERA_GRAB_COMMANDS:
                    return api.jsonify({'error': 'Invalid action. Use "start" or "stop"', 'success': False}), 400
                candidates = api._CAMERA_GRAB_COMMANDS[action]
                command_variant = api._command_variant(data, candidates)
                if api.authorization_required() and command_variant is None:
                    return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
                if command_variant is None and data.get('command_variant') is not None:
                    return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
                blocked = api.require_http_hardware(
                    action=action,
                    targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in candidates],
                    args={'action': action, 'command_variant': command_variant or 'legacy_autodetect'},
                    route_id='camera.grabbing', wrapper_fields={'action', 'command_variant'},
                )
                if blocked is not None:
                    return blocked
                # Image polling and acquisition commands share one DeviceProxy.
                # Serialize the command plus readback so an image request cannot
                # restart acquisition between StopGrabbing and confirmation.
                with api.DeviceManager.operation_lock(device_name):
                    device = api.DeviceManager.get_device(device_name)
                    powered_on = False
                    if action == 'start':
                        try:
                            camera_state = str(device.state()).upper().rsplit('.', 1)[-1]
                        except Exception:
                            camera_state = 'UNKNOWN'
                        if camera_state == 'OFF':
                            power_command = api._resolve_command_name(
                                device, ('turn_on', 'TurnOn', 'on')
                            )
                            api._with_tango_retry(
                                lambda: device.command_inout(power_command),
                                attempts=3,
                                delay=0.35,
                            )
                            powered_on = True
                    command_name = command_variant or api._resolve_command_name(
                        device, candidates
                    )
                    api._with_tango_retry(
                        lambda: device.command_inout(command_name),
                        attempts=3,
                        delay=0.35,
                    )
                    expected_grabbing = action == 'start'
                    message = f'Grabbing {action} command sent ({command_name})'

                    # Confirm status with short polling to avoid stale immediate readback.
                    is_grabbing, state_confirmed = api._wait_for_camera_grabbing(
                        device,
                        expected_state=expected_grabbing,
                    )

                return api.jsonify({
                    'message': message,
                    'grabbing': is_grabbing,
                    'expected_grabbing': expected_grabbing,
                    'state_confirmed': state_confirmed,
                    'powered_on': powered_on,
                    'success': True
                })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    handle_camera_grabbing.__module__ = api.__name__
    handle_camera_grabbing.__qualname__ = "handle_camera_grabbing"

    return {
        "get_psp_pending_commands": get_psp_pending_commands,
        "acknowledge_psp_command": acknowledge_psp_command,
        "get_daqmx_latest": get_daqmx_latest,
        "get_daqmx_history": get_daqmx_history,
        "write_daqmx_channel": write_daqmx_channel,
        "reset_daqmx_counter": reset_daqmx_counter,
        "list_cameras": list_cameras,
        "get_camera_info": get_camera_info,
        "handle_camera_parameters": handle_camera_parameters,
        "handle_camera_grabbing": handle_camera_grabbing,
    }
