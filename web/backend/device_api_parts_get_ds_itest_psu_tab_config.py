"""Implementation for get_ds_itest_psu_tab_config and related operations."""


def _bind_device_api_parts_get_ds_itest_psu_tab_config(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_ds_itest_psu_tab_config(device_name):
        """Get tab configuration from Tango DB property 'tab_config'"""
        try:
            db = api.tango_gateway.create_database()

            # Default configuration
            default_config = {
                'V0': {'slots': [], 'defaults': {}, 'enabled': True},
                'VD2': {'slots': [], 'defaults': {}, 'enabled': True},
                'REF': {'slots': [], 'defaults': {}, 'enabled': True},
                'ALL': {'slots': [], 'defaults': {}, 'enabled': True}
            }
            key_aliases = {
                'V0': 'V0',
                'VD': 'V0',
                'VD2': 'VD2',
                'REF': 'REF',
                'RF': 'REF',
                'ALL': 'ALL',
            }

            try:
                # Read tab_config property from Tango DB
                # Expected format: JSON string like:
                # {
                #   "V0": {"slots": [1, 2, 3], "defaults": {"1": 0.5, "2": 1.0}},
                #   "VD2": {"slots": [4, 5], "defaults": {"4": 2.0}},
                #   "REF": {"slots": [6, 7, 8], "defaults": {"6": 0.1}}
                # }
                prop_values = db.get_device_property(device_name, 'tab_config')

                if 'tab_config' in prop_values and prop_values['tab_config']:
                    # Handle both single-line and multi-line property values
                    raw_value = prop_values['tab_config']
                    if isinstance(raw_value, (list, tuple)) or hasattr(raw_value, '__iter__'):
                        try:
                            # Multi-line property: join all lines (works for list, tuple, StdStringVector)
                            config_str = ''.join(line for line in raw_value)
                        except (TypeError, AttributeError):
                            config_str = str(raw_value)
                    else:
                        config_str = str(raw_value)

                    if config_str:
                        raw_config = api.json.loads(config_str)
                        normalized = {
                            tab_name: {
                                'slots': [],
                                'defaults': {},
                                'enabled': default_config[tab_name]['enabled'],
                            }
                            for tab_name in default_config
                        }

                        for raw_tab_name, tab_payload in raw_config.items():
                            canonical = key_aliases.get(str(raw_tab_name).upper())
                            if not canonical or not isinstance(tab_payload, dict):
                                continue

                            slots = []
                            for slot_id in tab_payload.get('slots', []):
                                parsed_slot = api._as_int(slot_id, None)
                                if parsed_slot is not None and parsed_slot not in slots:
                                    slots.append(parsed_slot)

                            defaults = {}
                            for slot_key, slot_value in (tab_payload.get('defaults', {}) or {}).items():
                                normalized_key = str(api._as_int(slot_key, slot_key))
                                defaults[normalized_key] = slot_value

                            normalized[canonical] = {
                                'slots': slots,
                                'defaults': defaults,
                                'enabled': bool(tab_payload.get('enabled', True)),
                            }

                        return api.jsonify({'tab_configs': normalized, 'success': True})
            except Exception as e:
                print(f"Warning: Could not read tab_config property: {e}")

            # Return default config if property doesn't exist or is invalid
            return api.jsonify({'tab_configs': default_config, 'success': True})

        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_ds_itest_psu_tab_config.__module__ = api.__name__
    get_ds_itest_psu_tab_config.__qualname__ = "get_ds_itest_psu_tab_config"

    def get_itest_all_slots(device_name):
        """Get all slot data for iTest PSU device"""
        try:
            device = api.DeviceManager.get_device(device_name)

            # Read all attributes
            ids = api.make_json_safe(device.read_attribute('ids').value)
            names = api.make_json_safe(device.read_attribute('names').value)
            states = api.make_json_safe(device.read_attribute('states').value)
            currents_setpoint = api.make_json_safe(device.read_attribute('currents_setpoint').value)
            currents_meas = api.make_json_safe(device.read_attribute('currents_meas').value)
            current_limits = api.make_json_safe(device.read_attribute('current_limits').value)

            return api.jsonify({
                'ids': ids,
                'names': names,
                'states': states,
                'currents_setpoint': currents_setpoint,
                'currents_meas': currents_meas,
                'current_limits': current_limits,
                'success': True
            })

        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_itest_all_slots.__module__ = api.__name__
    get_itest_all_slots.__qualname__ = "get_itest_all_slots"

    def set_itest_slot_output(device_name, slot_id):
        """Set output state for specific iTest PSU slot"""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload(('state',))
            if data is None or isinstance(data['state'], bool) or not isinstance(data['state'], int) or data['state'] not in (0, 1):
                return api.jsonify({'error': 'state must be 0 or 1', 'success': False}), 400
            state = int(data['state'])
            blocked = api.require_http_hardware(
                action='set_output',
                targets=[{'device': str(device_name), 'command': 'set_output_state'}],
                args={'slot_id': int(slot_id), 'state': state},
                route_id='itest.output', wrapper_fields={'state'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            # Use set_output_state command with [slot_id, state]
            device.command_inout('set_output_state', [int(slot_id), state])

            return api.jsonify({
                'slot_id': slot_id,
                'state': state,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    set_itest_slot_output.__module__ = api.__name__
    set_itest_slot_output.__qualname__ = "set_itest_slot_output"

    def set_ds_itest_psu_current(device_name, slot_id):
        """Set current for specific DS iTest PSU slot with limit validation"""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload(('current',))
            current_value = api._finite_number(data.get('current')) if data is not None else None
            if current_value is None:
                return api.jsonify({'error': 'current must be finite numeric', 'success': False}), 400
            blocked = api.require_http_hardware(
                action='set_current',
                targets=[{'device': str(device_name), 'command': 'set_current'}],
                args={'slot_id': int(slot_id), 'current': current_value},
                route_id='itest.current', wrapper_fields={'current'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            # Get slot array index for validation
            ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int
            try:
                array_idx = ids.index(slot_id)
            except ValueError:
                return api.jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404

            # Validate current limits before setting
            try:
                limits_array = list(device.read_attribute('current_limits').value)
                if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                    limits_idx = array_idx * 2
                    min_limit = float(limits_array[limits_idx])
                    max_limit = float(limits_array[limits_idx + 1])

                    if current_value < min_limit or current_value > max_limit:
                        return api.jsonify({
                            'error': f'Current value {current_value}A is outside limits [{min_limit}, {max_limit}]A for slot {slot_id}',
                            'limits': {'min': min_limit, 'max': max_limit},
                            'slot_id': slot_id,
                            'success': False
                        }), 400
            except Exception as e:
                print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")

            # Use set_current command with [slot_id, value] - slot_id is the real slot ID
            device.command_inout('set_current', [float(slot_id), current_value])

            # Read back the setpoint array to confirm
            currents_setpoint = list(device.read_attribute('currents_setpoint').value)

            try:
                actual_value = currents_setpoint[array_idx] if array_idx < len(currents_setpoint) else current_value
            except ValueError:
                # Slot ID not found, return the requested value
                actual_value = current_value

            return api.jsonify({
                'slot_id': slot_id,
                'current_setpoint': actual_value,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    set_ds_itest_psu_current.__module__ = api.__name__
    set_ds_itest_psu_current.__qualname__ = "set_ds_itest_psu_current"

    def set_ds_itest_psu_state(device_name, slot_id):
        """Set output state for specific DS iTest PSU slot"""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload(('enabled',))
            if data is None or type(data['enabled']) is not bool:
                return api.jsonify({'error': 'enabled must be boolean', 'success': False}), 400
            enabled = data['enabled']
            blocked = api.require_http_hardware(
                action='set_output',
                targets=[{'device': str(device_name), 'command': 'set_output_state'}],
                args={'slot_id': int(slot_id), 'enabled': enabled},
                route_id='itest.state', wrapper_fields={'enabled'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            # Use set_output_state command with [slot_id, state] - slot_id is the real slot ID
            device.command_inout('set_output_state', [int(slot_id), int(1 if enabled else 0)])

            # Read back the states array to confirm - need to find array index
            ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int
            states = list(device.read_attribute('states').value)

            try:
                array_idx = ids.index(slot_id)
                actual_state = bool(states[array_idx]) if array_idx < len(states) else enabled
            except ValueError:
                # Slot ID not found, return the requested state
                actual_state = enabled

            return api.jsonify({
                'slot_id': slot_id,
                'state': actual_state,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    set_ds_itest_psu_state.__module__ = api.__name__
    set_ds_itest_psu_state.__qualname__ = "set_ds_itest_psu_state"

    def handle_itest_current(device_name):
        """Handle iTest PSU current operations (legacy endpoint)"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                setpoint = device.read_attribute('CurrentSetpoint').value
                measured = device.read_attribute('MeasuredCurrent').value
                voltage = device.read_attribute('MeasuredVoltage').value

                # Try to get current limits if available
                limits = None
                try:
                    limits_array = device.read_attribute('current_limits').value
                    if limits_array and len(limits_array) >= 2:
                        # Assuming single channel device, take first pair
                        limits = {'min': float(limits_array[0]), 'max': float(limits_array[1])}
                except:
                    # Fallback to default limits if attribute doesn't exist
                    limits = {'min': -5.0, 'max': 15.0}

                return api.jsonify({
                    'current_setpoint': api.make_json_safe(setpoint),
                    'measured_current': api.make_json_safe(measured),
                    'measured_voltage': api.make_json_safe(voltage),
                    'current_limits': limits,
                    'success': True
                })

            elif api.request.method == 'POST':
                api._maybe_require_auth()
                data = api._mutation_payload(('action',))
                if data is None or not isinstance(data.get('action'), str):
                    return api.jsonify({'error': 'Unknown action', 'success': False}), 400
                action = data.get('action')
                value = data.get('value')
                commands = {
                    'set': 'write_attribute',
                    'inc_fine': 'IncCurrentFine',
                    'dec_fine': 'DecCurrentFine',
                    'inc_coarse': 'IncCurrentCoarse',
                    'dec_coarse': 'DecCurrentCoarse',
                }
                if action not in commands or (action == 'set' and api._finite_number(value) is None):
                    return api.jsonify({'error': 'Unknown action', 'success': False}), 400
                if api.authorization_required() and action != 'set':
                    return api.jsonify({
                        'error': 'Hardware action is not authorized',
                        'success': False,
                        'code': 'hardware_not_authorized',
                    }), 403
                if action == 'set':
                    value = api._finite_number(value)
                blocked = api.require_http_hardware(
                    action=action,
                    targets=[{'device': str(device_name), 'command': commands[action]}],
                    args={'action': action, 'value': value},
                    route_id='itest.current',
                    wrapper_fields={'action', 'value'} if action == 'set' else {'action'},
                )
                if blocked is not None:
                    return blocked
                device = api.DeviceManager.get_device(device_name)

                # For set action, validate limits first
                if action == 'set' and value is not None:
                    try:
                        limits_array = device.read_attribute('current_limits').value
                        if limits_array and len(limits_array) >= 2:
                            min_limit = float(limits_array[0])
                            max_limit = float(limits_array[1])

                            if value < min_limit or value > max_limit:
                                return api.jsonify({
                                    'error': f'Current value {value}A is outside limits [{min_limit}, {max_limit}]A',
                                    'limits': {'min': min_limit, 'max': max_limit},
                                    'success': False
                                }), 400
                    except Exception as e:
                        # If we can't read limits, log but continue (fallback behavior)
                        print(f"Warning: Could not read current limits for {device_name}: {e}")

                if action == 'set':
                    device.write_attribute('CurrentSetpoint', value)
                elif action == 'inc_fine':
                    device.command_inout('IncCurrentFine')
                elif action == 'dec_fine':
                    device.command_inout('DecCurrentFine')
                elif action == 'inc_coarse':
                    device.command_inout('IncCurrentCoarse')
                elif action == 'dec_coarse':
                    device.command_inout('DecCurrentCoarse')
                else:
                    return api.jsonify({'error': 'Unknown action', 'success': False}), 400

                # Read back current value
                setpoint = device.read_attribute('CurrentSetpoint').value
                return api.jsonify({'current_setpoint': setpoint, 'success': True})

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    handle_itest_current.__module__ = api.__name__
    handle_itest_current.__qualname__ = "handle_itest_current"

    def handle_itest_slot_current(device_name, slot_id):
        """Handle iTest PSU current operations for specific slot with proper limits"""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                # Read multi-slot arrays
                ids = [int(x) for x in device.read_attribute('ids').value]
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                currents_meas = list(device.read_attribute('currents_meas').value)

                # Try to read voltage (may not be available on all devices)
                voltage = 0.0
                try:
                    voltages = list(device.read_attribute('voltages_meas').value)
                    array_idx = ids.index(slot_id)
                    voltage = api.make_json_safe(voltages[array_idx]) if array_idx < len(voltages) else 0.0
                except:
                    voltage = 0.0  # Default if voltage not available

                # Find array index for this slot
                try:
                    array_idx = ids.index(slot_id)
                except ValueError:
                    return api.jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404

                # Get current values for this slot
                current_setpoint = api.make_json_safe(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                measured_current = api.make_json_safe(currents_meas[array_idx]) if array_idx < len(currents_meas) else 0.0

                # Get current limits for this slot
                limits = {'min': -5.0, 'max': 15.0}  # Default
                try:
                    limits_array = list(device.read_attribute('current_limits').value)
                    if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                        # Limits are stored as [min1, max1, min2, max2, ...]
                        limits_idx = array_idx * 2
                        limits = {
                            'min': float(limits_array[limits_idx]),
                            'max': float(limits_array[limits_idx + 1])
                        }
                except Exception as e:
                    print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")

                return api.jsonify({
                    'slot_id': slot_id,
                    'current_setpoint': current_setpoint,
                    'measured_current': measured_current,
                    'measured_voltage': api.make_json_safe(voltage),
                    'current_limits': limits,
                    'success': True
                })

            elif api.request.method == 'POST':
                api._maybe_require_auth()
                data = api._mutation_payload()
                if data is None:
                    return api.jsonify({'error': 'action is required', 'success': False}), 400
                action = data.get('action')
                value = data.get('value')
                if value is None and data.get('current') is not None:
                    value = data.get('current')
                if action is None and value is not None:
                    action = 'set'
                if not isinstance(action, str) or action not in {'set', 'inc_fine', 'dec_fine', 'inc_coarse', 'dec_coarse'}:
                    return api.jsonify({'error': 'Unknown action', 'success': False}), 400
                if api.authorization_required() and action != 'set':
                    return api.jsonify({
                        'error': 'Hardware action is not authorized',
                        'success': False,
                        'code': 'hardware_not_authorized',
                    }), 403
                if action == 'set':
                    value = api._finite_number(value)
                    if value is None:
                        return api.jsonify({'error': 'value must be numeric', 'success': False}), 400
                allowed_fields = {'action', 'value', 'current'} if action == 'set' else {'action'}
                blocked = api.require_http_hardware(
                    action=action,
                    targets=[{'device': str(device_name), 'command': 'set_current'}],
                    args={'slot_id': int(slot_id), 'action': action, 'value': value},
                    route_id='itest.slot_current', wrapper_fields=allowed_fields,
                )
                if blocked is not None:
                    return blocked
                device = api.DeviceManager.get_device(device_name)

                # Get slot array index
                ids = [int(x) for x in device.read_attribute('ids').value]
                try:
                    array_idx = ids.index(slot_id)
                except ValueError:
                    return api.jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404

                # For set action, validate limits first
                if action == 'set' and value is not None:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        return api.jsonify({'error': 'value must be numeric', 'success': False}), 400
                    try:
                        limits_array = list(device.read_attribute('current_limits').value)
                        if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                            limits_idx = array_idx * 2
                            min_limit = float(limits_array[limits_idx])
                            max_limit = float(limits_array[limits_idx + 1])

                            if value < min_limit or value > max_limit:
                                return api.jsonify({
                                    'error': f'Current value {value}A is outside limits [{min_limit}, {max_limit}]A for slot {slot_id}',
                                    'limits': {'min': min_limit, 'max': max_limit},
                                    'slot_id': slot_id,
                                    'success': False
                                }), 400
                    except Exception as e:
                        print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")

                if action == 'set':
                    # Use set_current command with [slot_id, value]
                    device.command_inout('set_current', [float(slot_id), float(value)])
                elif action == 'inc_fine':
                    # Get current setpoint and increment by 0.01A
                    currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                    current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                    new_val = current_val + 0.01
                    device.command_inout('set_current', [float(slot_id), new_val])
                elif action == 'dec_fine':
                    # Get current setpoint and decrement by 0.01A
                    currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                    current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                    new_val = current_val - 0.01
                    device.command_inout('set_current', [float(slot_id), new_val])
                elif action == 'inc_coarse':
                    # Get current setpoint and increment by 0.1A
                    currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                    current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                    new_val = current_val + 0.1
                    device.command_inout('set_current', [float(slot_id), new_val])
                elif action == 'dec_coarse':
                    # Get current setpoint and decrement by 0.1A
                    currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                    current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                    new_val = current_val - 0.1
                    device.command_inout('set_current', [float(slot_id), new_val])
                else:
                    return api.jsonify({'error': 'Unknown action', 'success': False}), 400

                # Read back current value for this slot
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                current_setpoint = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0

                return api.jsonify({
                    'slot_id': slot_id,
                    'current_setpoint': current_setpoint,
                    'success': True
                })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    handle_itest_slot_current.__module__ = api.__name__
    handle_itest_slot_current.__qualname__ = "handle_itest_slot_current"

    def camera_capture(device_name):
        """Trigger camera capture"""
        try:
            api._maybe_require_auth()
            data = api._hardware_payload()
            if data is None or set(data) - {'exposure_time'}:
                return api.jsonify({'error': 'Invalid capture payload', 'success': False}), 400

            exposure_time = data.get('exposure_time', 1.0)
            if api._finite_number(exposure_time) is None:
                return api.jsonify({'error': 'exposure_time must be finite numeric', 'success': False}), 400
            exposure_time = api._finite_number(exposure_time)
            targets = []
            if 'exposure_time' in data:
                targets.append({'device': str(device_name), 'command': 'write_attribute'})
            targets.append({'device': str(device_name), 'command': 'StartAcquisition'})
            blocked = api.require_http_hardware(
                action='capture', targets=targets,
                args={'exposure_time': exposure_time, 'set_exposure_time': 'exposure_time' in data},
                route_id='camera.capture', wrapper_fields={'exposure_time'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            # Set exposure time if provided
            if 'exposure_time' in data:
                device.write_attribute('ExposureTime', exposure_time)

            # Trigger capture
            result = device.command_inout('StartAcquisition')

            return api.jsonify({
                'command': 'StartAcquisition',
                'exposure_time': exposure_time,
                'result': result,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    camera_capture.__module__ = api.__name__
    camera_capture.__qualname__ = "camera_capture"

    def list_daqmx_devices():
        """List DAQmx-related Tango devices (ZMQ reader and PSP supervision readers)."""
        try:
            db = api.tango_gateway.create_database()
            probe_state = api._query_bool('probe_state', True)
            devices = api._device_catalog_service.list_class_devices(
                db,
                api.DAQMX_DEVICE_CLASSES,
                probe_state,
                api._catalog_device_state,
                deduplicate=True,
            )
            return api.jsonify({'devices': devices, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    list_daqmx_devices.__module__ = api.__name__
    list_daqmx_devices.__qualname__ = "list_daqmx_devices"

    def list_psp_devices():
        """List DS_PSP devices available in Tango DB."""
        try:
            db = api.tango_gateway.create_database()
            probe_state = api._query_bool('probe_state', True)
            devices = api._device_catalog_service.list_class_devices(
                db,
                ('DS_PSP',),
                probe_state,
                api._catalog_device_state,
                deduplicate=False,
            )
            return api.jsonify({'devices': devices, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    list_psp_devices.__module__ = api.__name__
    list_psp_devices.__qualname__ = "list_psp_devices"

    def get_psp_group_history(device_name, group_name):
        """Read PSP FIFO history for one group and return graph-ready series."""
        try:
            device = api.DeviceManager.get_device(device_name)
            seconds = max(0.0, float(api.request.args.get('seconds', 1800.0)))
            limit = max(1, int(api.request.args.get('limit', 5000)))
            group = api._normalize_psp_group(group_name)

            history = api._read_psp_group_history(device, group, seconds, limit)
            series, latest = api._build_psp_series(history)

            return api.jsonify({
                'device': device_name,
                'group': group,
                'seconds': seconds,
                'limit': limit,
                'sample_count': len(history),
                'channel_count': len(series),
                'history': history,
                'series': series,
                'latest_by_channel': latest,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_psp_group_history.__module__ = api.__name__
    get_psp_group_history.__qualname__ = "get_psp_group_history"

    return {
        "get_ds_itest_psu_tab_config": get_ds_itest_psu_tab_config,
        "get_itest_all_slots": get_itest_all_slots,
        "set_itest_slot_output": set_itest_slot_output,
        "set_ds_itest_psu_current": set_ds_itest_psu_current,
        "set_ds_itest_psu_state": set_ds_itest_psu_state,
        "handle_itest_current": handle_itest_current,
        "handle_itest_slot_current": handle_itest_slot_current,
        "camera_capture": camera_capture,
        "list_daqmx_devices": list_daqmx_devices,
        "list_psp_devices": list_psp_devices,
        "get_psp_group_history": get_psp_group_history,
    }
