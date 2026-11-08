"""Implementation for get_laser_pointing_snapshot and related operations."""


def _bind_device_api_parts_get_laser_pointing_snapshot(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_laser_pointing_snapshot(device_name):
        """Return one normalized snapshot for the composite LaserPointing client."""
        try:
            def read_snapshot():
                controller = api.DeviceManager.get_device(device_name)

                def read_value(attribute_name):
                    return controller.read_attribute(attribute_name).value

                def read_optional_json(attribute_name, default):
                    try:
                        return api.json.loads(str(read_value(attribute_name) or '{}'))
                    except Exception:
                        return default

                def read_optional_text(attribute_name, default):
                    try:
                        return str(read_value(attribute_name))
                    except Exception:
                        return default

                rules = api._parse_controller_mapping(read_value('get_rules'))
                device_map = api._parse_controller_mapping(read_value('get_ds_dict'))
                groups = api._parse_controller_mapping(read_value('get_groups'))
                commands = {str(name).lower() for name in controller.get_command_list()}
                automatic_supported = 'start_automatic_search' in commands
                pause_supported = 'pause_automatic_search' in commands
                resume_supported = 'resume_automatic_search' in commands
                cancel_keep_current_supported = (
                    'cancel_automatic_search' in commands
                )
                reference_acceptance_supported = (
                    'accept_alignment_reference' in commands
                )
                manual_reference_supported = (
                    'save_current_alignment_reference' in commands
                )
                point_supported = 'apply_controller_point' in commands
                manual_point_selection_supported = 'select_manual_point' in commands
                pair_initialization_supported = 'initialize_active_pair' in commands
                interlocked_motion_supported = 'move_active_actuator' in commands
                search_status = read_optional_text(
                    'automatic_search_status', 'server restart required'
                )
                search_progress = read_optional_json(
                    'automatic_search_progress',
                    {
                        'phase': 'upgrade_required',
                        'message': (
                            'Restart DS_LaserPointing to activate automatic search '
                            'and controller-owned point presets'
                        ),
                    },
                )
                search_config = read_optional_json(
                    'automatic_search_config',
                    {
                        'mode': 'sensitive',
                        'step_schedule': [10.0, 6.0, 2.0],
                        'radius': 30.0,
                        'tolerance_px': 2.0,
                        'roundness_tolerance_pct': 7.0,
                        'max_evaluations': 16,
                        'max_cycles': 2,
                        'samples': 3,
                        'adaptive_learning': True,
                        'adaptive_min_step': 0.125,
                        'adaptive_backoff': 0.5,
                        'adaptive_growth': 1.15,
                        'point_step_limits': {},
                        'point_probe_repetitions': {},
                        'aperture_sweep_enabled': True,
                        'aperture_sweep_positions': 4,
                        'aperture_cycle_count': 2,
                        'aperture_samples': 1,
                        'aperture_drift_weight': 0.5,
                        'group_plateau_probe_limit': 5,
                        'group_plateau_min_improvement_pct': 5.0,
                        'stagnation_pass_limit': 5,
                        'stagnation_min_improvement_pct': 5.0,
                    },
                )
                search_history = read_optional_json('automatic_search_history', [])
                if not isinstance(search_history, list):
                    search_history = []
                adaptive_search_model = read_optional_json(
                    'adaptive_search_model_json', {}
                )
                alignment_reference = read_optional_json(
                    'alignment_reference_json', {}
                )
                pending_alignment_reference = read_optional_json(
                    'alignment_pending_reference_json', {}
                )
                alignment_session_event = read_optional_json(
                    'alignment_session_event_json', {}
                )
                try:
                    alignment_reference_revision = int(
                        read_value('alignment_reference_revision')
                    )
                except Exception:
                    alignment_reference_revision = 0
                try:
                    alignment_session_event_count = int(
                        read_value('alignment_session_event_count')
                    )
                except Exception:
                    alignment_session_event_count = 0
                pair_initialization = read_optional_json(
                    'actuator_initialization_status',
                    {
                        'phase': 'upgrade_required',
                        'group': 0,
                        'message': 'Restart DS_LaserPointing to enable pair initialisation',
                    },
                )
                active_point = read_optional_text('active_point', '').strip()
                try:
                    active_actuator_group = int(read_value('active_actuator_group'))
                except Exception:
                    active_actuator_group = 0

                camera_name = device_map.get('Camera', '')
                camera = None
                camera_state = 'UNKNOWN'
                camera_grabbing = False
                centroid = None
                centroid_valid = False
                beam_visibility_status = 'unavailable'
                beam_visibility_message = ''
                ambient_light_high = False
                beam_background = None
                beam_contrast = None
                beam_foreground_fraction = None
                if camera_name:
                    camera = api.DeviceManager.get_device(str(camera_name))
                    try:
                        camera_state = str(camera.state())
                    except Exception:
                        camera_state = 'UNKNOWN'
                    camera_grabbing = api._read_camera_is_grabbing(camera)
                    try:
                        centroid = api.ast.literal_eval(str(camera.read_attribute('cg').value))
                    except Exception:
                        centroid = None
                    try:
                        centroid_valid = bool(camera.read_attribute('cg_valid').value)
                    except Exception:
                        centroid_valid = bool(centroid)
                    try:
                        beam_visibility_status = str(
                            camera.read_attribute('beam_visibility_status').value
                        )
                    except Exception:
                        beam_visibility_status = (
                            'beam_visible' if centroid_valid else 'beam_not_visible'
                        )
                    try:
                        beam_visibility_message = str(
                            camera.read_attribute('beam_visibility_message').value
                        )
                    except Exception:
                        beam_visibility_message = ''
                    try:
                        ambient_light_high = bool(
                            camera.read_attribute('ambient_light_high').value
                        )
                    except Exception:
                        ambient_light_high = False
                    for attribute_name, local_name in (
                        ('beam_background', 'background'),
                        ('beam_contrast', 'contrast'),
                        ('beam_foreground_fraction', 'foreground_fraction'),
                    ):
                        try:
                            value = float(camera.read_attribute(attribute_name).value)
                        except Exception:
                            value = None
                        if local_name == 'background':
                            beam_background = value
                        elif local_name == 'contrast':
                            beam_contrast = value
                        else:
                            beam_foreground_fraction = value

                actuators = []
                for role, specification in device_map.items():
                    if not str(role).lower().startswith('actuator'):
                        continue
                    child_name = specification
                    if isinstance(specification, (list, tuple)):
                        child_name = specification[0]
                    child = api.DeviceManager.get_device(str(child_name))
                    try:
                        position = api.make_json_safe(child.read_attribute('position').value)
                    except Exception:
                        position = None
                    try:
                        state = str(child.state())
                    except Exception:
                        state = 'UNKNOWN'
                    try:
                        child_commands = {
                            str(name).lower() for name in child.get_command_list()
                        }
                    except Exception:
                        child_commands = set()
                    lifecycle = {}
                    for attribute_name in (
                        'hardware_connection_state',
                        'initialization_state',
                        'hardware_lifecycle_status',
                    ):
                        try:
                            lifecycle[attribute_name] = str(
                                child.read_attribute(attribute_name).value
                            )
                        except Exception:
                            lifecycle[attribute_name] = ''
                    connection = lifecycle['hardware_connection_state'].upper()
                    initialization = lifecycle['initialization_state'].upper()
                    state_name = state.upper().rsplit('.', 1)[-1]
                    disconnected = connection in {
                        'DISCONNECTED',
                        'POWER_OFF',
                        'POWER_STATUS_UNAVAILABLE',
                    } or state_name in {'FAULT', 'OFF', 'UNKNOWN', 'UNREACHABLE'}
                    ready = not disconnected and (
                        initialization == 'SUCCEEDED'
                        or connection == 'READY'
                        or state_name in {'ON', 'MOVING', 'RUNNING'}
                    )
                    actuators.append({
                        'role': str(role),
                        'device': str(child_name),
                        'position': position,
                        'state': state,
                        **lifecycle,
                        'disconnected': disconnected,
                        'ready': ready,
                        'move_supported': 'move_axis_abs' in child_commands,
                    })

                other_devices = []
                for role, specification in device_map.items():
                    role_name = str(role)
                    role_lower = role_name.lower()
                    is_diaphragm = 'diaphragm' in role_lower
                    is_half_wave_plate = (
                        'halfwaveplate' in role_lower
                        or 'half_wave_plate' in role_lower
                        or 'lambda_2' in role_lower
                    )
                    is_flipper = api._is_owned_laser_flipper(role_name, camera_name)
                    if not is_diaphragm and not is_half_wave_plate and not is_flipper:
                        continue

                    child_name = specification
                    if isinstance(specification, (list, tuple)):
                        child_name = specification[0]
                    child = api.DeviceManager.get_device(str(child_name))
                    try:
                        position = api.make_json_safe(
                            child.read_attribute('position').value
                        )
                    except Exception:
                        position = None
                    commanded_flipper_state = None
                    if is_flipper:
                        try:
                            commanded_flipper_state = str(
                                child.read_attribute('commanded_flipper_state').value
                            )
                        except Exception:
                            commanded_flipper_state = 'UNKNOWN'
                    try:
                        child_state = str(child.state())
                    except Exception:
                        child_state = 'UNKNOWN'
                    try:
                        child_commands = {
                            str(name).lower() for name in child.get_command_list()
                        }
                    except Exception:
                        child_commands = set()

                    lifecycle = {}
                    for attribute_name in (
                        'hardware_connection_state',
                        'initialization_state',
                        'hardware_lifecycle_status',
                    ):
                        try:
                            lifecycle[attribute_name] = str(
                                child.read_attribute(attribute_name).value
                            )
                        except Exception:
                            lifecycle[attribute_name] = ''

                    unit = ''
                    minimum = None
                    maximum = None
                    try:
                        position_config = child.get_attribute_config('position')
                        unit = str(getattr(position_config, 'unit', '') or '')
                        for field_name, output_name in (
                            ('min_value', 'minimum'), ('max_value', 'maximum')
                        ):
                            raw_value = getattr(position_config, field_name, None)
                            try:
                                numeric_value = float(raw_value)
                            except (TypeError, ValueError):
                                numeric_value = None
                            if output_name == 'minimum':
                                minimum = numeric_value
                            else:
                                maximum = numeric_value
                    except Exception:
                        pass

                    properties = api._read_selected_device_properties(
                        str(child_name),
                        ('friendly_name', 'preset_pos', 'unit', 'limit_min', 'limit_max'),
                    )

                    def first_property(name, default=''):
                        values = properties.get(name, [])
                        if isinstance(values, (list, tuple)) and values:
                            return values[0]
                        return values if values not in (None, []) else default

                    friendly_name = str(first_property('friendly_name', '') or '')
                    if not unit:
                        unit = str(first_property('unit', '') or '')
                    if minimum is None:
                        try:
                            minimum = float(first_property('limit_min'))
                        except (TypeError, ValueError):
                            minimum = None
                    if maximum is None:
                        try:
                            maximum = float(first_property('limit_max'))
                        except (TypeError, ValueError):
                            maximum = None

                    preset_positions = []
                    raw_presets = properties.get('preset_pos', [])
                    if not isinstance(raw_presets, (list, tuple)):
                        raw_presets = [raw_presets]
                    for raw_preset in raw_presets:
                        try:
                            preset = float(raw_preset)
                        except (TypeError, ValueError):
                            continue
                        if preset not in preset_positions:
                            preset_positions.append(preset)

                    connection = lifecycle['hardware_connection_state'].upper()
                    initialization = lifecycle['initialization_state'].upper()
                    state_name = child_state.upper().rsplit('.', 1)[-1]
                    disconnected = connection in {
                        'DISCONNECTED',
                        'POWER_OFF',
                        'POWER_STATUS_UNAVAILABLE',
                    } or state_name in {'FAULT', 'OFF', 'UNKNOWN', 'UNREACHABLE'}
                    ready = not disconnected and (
                        initialization == 'SUCCEEDED'
                        or connection == 'READY'
                        or state_name in {'ON', 'MOVING', 'RUNNING'}
                    )
                    other_devices.append({
                        'role': role_name,
                        'control_type': (
                            'diaphragm'
                            if is_diaphragm
                            else ('half_wave_plate' if is_half_wave_plate else 'flipper')
                        ),
                        'friendly_name': friendly_name,
                        'device': str(child_name),
                        'position': position,
                        **(
                            {'commanded_flipper_state': commanded_flipper_state}
                            if is_flipper else {}
                        ),
                        'preset_positions': preset_positions,
                        'unit': unit,
                        'minimum': minimum,
                        'maximum': maximum,
                        'state': child_state,
                        'move_supported': 'move_axis_abs' in child_commands,
                        'stop_supported': 'stop_movement' in child_commands,
                        **lifecycle,
                        'disconnected': disconnected,
                        'ready': ready,
                    })

                manual_devices = []
                for role, specification in device_map.items():
                    role_name = str(role)
                    role_lower = role_name.lower()
                    if role_lower.startswith('actuator') or not any(
                        token in role_lower for token in ('translation', 'stage', 'owis')
                    ):
                        continue

                    child_name = specification
                    axes = []
                    if isinstance(specification, (list, tuple)):
                        child_name = specification[0]
                        if len(specification) > 1:
                            configured_axes = specification[1]
                            if isinstance(configured_axes, (list, tuple)):
                                axes = [int(axis) for axis in configured_axes]
                            else:
                                axes = [int(configured_axes)]

                    child = api.DeviceManager.get_device(str(child_name))
                    try:
                        child_state = str(child.state())
                    except Exception:
                        child_state = 'UNKNOWN'
                    try:
                        child_commands = {
                            str(name).lower() for name in child.get_command_list()
                        }
                    except Exception:
                        child_commands = set()

                    lifecycle = {}
                    for attribute_name in (
                        'hardware_connection_state',
                        'initialization_state',
                        'hardware_lifecycle_status',
                    ):
                        try:
                            lifecycle[attribute_name] = str(
                                child.read_attribute(attribute_name).value
                            )
                        except Exception:
                            lifecycle[attribute_name] = ''

                    axis_snapshots = []
                    for axis in axes:
                        position = None
                        for attribute_name in (f'pos{axis}', f'position_axis_{axis}'):
                            try:
                                position = api.make_json_safe(
                                    child.read_attribute(attribute_name).value
                                )
                                break
                            except Exception:
                                pass
                        axis_snapshots.append({
                            'axis': axis,
                            'position': position,
                        })

                    connection = lifecycle['hardware_connection_state'].upper()
                    initialization = lifecycle['initialization_state'].upper()
                    state_name = child_state.upper().rsplit('.', 1)[-1]
                    disconnected = connection in {
                        'DISCONNECTED',
                        'POWER_OFF',
                        'POWER_STATUS_UNAVAILABLE',
                    } or state_name in {'FAULT', 'OFF', 'UNKNOWN', 'UNREACHABLE'}
                    ready = not disconnected and (
                        initialization == 'SUCCEEDED'
                        or connection == 'READY'
                        or state_name in {'ON', 'MOVING', 'RUNNING'}
                    )
                    manual_devices.append({
                        'role': role_name,
                        'device': str(child_name),
                        'state': child_state,
                        'axes': axis_snapshots,
                        'move_supported': 'move_axis' in child_commands,
                        **lifecycle,
                        'disconnected': disconnected,
                        'ready': ready,
                    })

                return {
                    'device': device_name,
                    'state': str(controller.state()),
                    'rules': api.make_json_safe(rules),
                    'devices': api.make_json_safe(device_map),
                    'groups': api.make_json_safe(groups),
                    'automatic_search': {
                        'status': search_status,
                        'progress': api.make_json_safe(search_progress),
                        'config': api.make_json_safe(search_config),
                        'history': api.make_json_safe(search_history),
                        'adaptive_model': api.make_json_safe(adaptive_search_model),
                        'reference': api.make_json_safe(alignment_reference),
                        'reference_revision': alignment_reference_revision,
                        'pending_reference': api.make_json_safe(
                            pending_alignment_reference
                        ),
                        'last_session_event': api.make_json_safe(
                            alignment_session_event
                        ),
                        'session_event_count': alignment_session_event_count,
                    },
                    'pair_initialization': api.make_json_safe(pair_initialization),
                    'capabilities': {
                        'automatic_search': automatic_supported,
                        'pause_search': pause_supported,
                        'resume_search': resume_supported,
                        'cancel_search_keep_current': (
                            cancel_keep_current_supported
                        ),
                        'accept_alignment_reference': (
                            reference_acceptance_supported
                        ),
                        'save_current_alignment_reference': (
                            manual_reference_supported
                        ),
                        'apply_point': point_supported,
                        'manual_point_selection': manual_point_selection_supported,
                        'initialize_active_pair': pair_initialization_supported,
                        'interlocked_motion': interlocked_motion_supported,
                    },
                    'active_point': active_point,
                    'active_actuator_group': active_actuator_group,
                    'camera': {
                        'device': str(camera_name),
                        'state': camera_state,
                        'grabbing': camera_grabbing,
                        'centroid': api.make_json_safe(centroid),
                        'centroid_valid': centroid_valid,
                        'beam_visibility_status': beam_visibility_status,
                        'beam_visibility_message': beam_visibility_message,
                        'ambient_light_high': ambient_light_high,
                        'beam_background': beam_background,
                        'beam_contrast': beam_contrast,
                        'beam_foreground_fraction': beam_foreground_fraction,
                    },
                    'actuators': actuators,
                    'other_devices': other_devices,
                    # Compatibility for older clients that only render irises.
                    'diaphragms': [
                        item for item in other_devices
                        if item['control_type'] == 'diaphragm'
                    ],
                    'manual_devices': manual_devices,
                    'timestamp': api.datetime.now().isoformat(),
                }

            # Snapshot polling and controller commands share a cached DeviceProxy.
            # Keep them serial so a busy request thread cannot contend for Tango's
            # device serialization monitor, then retry monitor timeouts above.
            with api.DeviceManager.operation_lock(device_name):
                snapshot = api._with_tango_retry(read_snapshot)
            return api.jsonify({'snapshot': snapshot, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    get_laser_pointing_snapshot.__module__ = api.__name__
    get_laser_pointing_snapshot.__qualname__ = "get_laser_pointing_snapshot"

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

    get_pdu_outputs.__module__ = api.__name__
    get_pdu_outputs.__qualname__ = "get_pdu_outputs"

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

    get_ds_itest_psu_slots.__module__ = api.__name__
    get_ds_itest_psu_slots.__qualname__ = "get_ds_itest_psu_slots"

    return {
        "get_laser_pointing_snapshot": get_laser_pointing_snapshot,
        "get_pdu_outputs": get_pdu_outputs,
        "get_ds_itest_psu_slots": get_ds_itest_psu_slots,
    }
