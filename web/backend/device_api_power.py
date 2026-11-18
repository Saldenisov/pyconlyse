"""PDU status and iTest power supply endpoints."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def get_pdu_outputs(device_name):
        """Read NETIO/PDU output table using normalized output objects."""
        try:
            def read_outputs():
                device = api.DeviceManager.get_device(device_name)
                ids = api._read_optional_attr_sequence_strict(device, 'ids')
                names = api._read_optional_attr_sequence_strict(device, 'names')
                states = api._read_pdu_states_strict(device)
                return device, ids, names, states

            device, ids, names, states = api._with_device_retry(device_name, read_outputs)

            output_count = max(len(ids), len(names), len(states), 4)
            if not ids:
                ids = list(range(1, output_count + 1))

            outputs = []
            for idx in range(output_count):
                raw_id = ids[idx] if idx < len(ids) else idx + 1
                output_id = api._as_int(raw_id, idx + 1)
                output_name = (
                    str(names[idx])
                    if idx < len(names) and names[idx] not in (None, "")
                    else f"Output {output_id}"
                )
                raw_state = states[idx] if idx < len(states) else 0
                output_state = 1 if api._as_int(raw_state, 0) else 0
                outputs.append({
                    'id': output_id,
                    'name': output_name,
                    'state': output_state,
                })

            return api.jsonify({
                'device': device_name,
                'state': str(device.state()),
                'outputs': outputs,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    # Device-specific endpoints for common PYCONLYSE devices
    def get_ds_itest_psu_slots(device_name):
        """Get all DS iTest PSU slot information"""
        try:
            device = api.DeviceManager.get_device(device_name)

            # Read all slot data including real slot IDs
            names = list(device.read_attribute('names').value)
            states = list(device.read_attribute('states').value)
            currents_meas = list(device.read_attribute('currents_meas').value)
            currents_setpoint = list(device.read_attribute('currents_setpoint').value)
            ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int for JSON serialization

            slots = []
            for i in range(len(names)):
                # Use actual slot ID instead of counter
                slot_id = ids[i] if i < len(ids) else i + 1
                slots.append({
                    'id': slot_id,  # Real slot ID
                    'index': i,     # Array index for reference
                    'name': names[i] if i < len(names) else f'Slot {slot_id}',
                    'state': bool(states[i]) if i < len(states) else False,
                    'current_measured': api.make_json_safe(currents_meas[i]) if i < len(currents_meas) else 0.0,
                    'current_setpoint': api.make_json_safe(currents_setpoint[i]) if i < len(currents_setpoint) else 0.0
                })

            return api.jsonify({
                'slots': slots,
                'slot_count': len(names),
                'available_slot_ids': ids,
                'success': True
            })

        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


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

    api.get_pdu_outputs = get_pdu_outputs
    api.get_ds_itest_psu_slots = get_ds_itest_psu_slots
    api.get_ds_itest_psu_tab_config = get_ds_itest_psu_tab_config
    api.get_itest_all_slots = get_itest_all_slots
    api.set_itest_slot_output = set_itest_slot_output
    api.set_ds_itest_psu_current = set_ds_itest_psu_current
    api.set_ds_itest_psu_state = set_ds_itest_psu_state
    api.handle_itest_current = handle_itest_current
    api.handle_itest_slot_current = handle_itest_slot_current
