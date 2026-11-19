"""device api optics operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
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


    # Camera-specific endpoints
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


    def get_camera_image(device_name):
        """Get the last captured image from camera"""
        try:
            include_contours = str(api.request.args.get('contours', '')).lower() in (
                '1', 'true', 'yes', 'on'
            )
            contour_settings = None
            with api.DeviceManager.operation_lock(device_name):
                device = api.DeviceManager.get_device(device_name)
                # DS_CAMERA_CCD.image starts grabbing when acquisition is stopped.
                # A passive browser preview must never turn the camera back on.
                if not api._read_camera_is_grabbing(device):
                    return api.jsonify({
                        'error': 'Camera acquisition is stopped',
                        'grabbing': False,
                        'success': False,
                    }), 409

                image_attr = device.read_attribute('image')
                image_data = image_attr.value

                if image_data is None:
                    return api.jsonify({'error': 'No image available', 'success': False}), 404

                # Get center of gravity if available
                cg_position = None
                try:
                    cg_str = str(device.read_attribute('cg').value)
                    cg_position = api.ast.literal_eval(cg_str)
                except Exception:
                    pass

                if include_contours:
                    contour_settings = {
                        'threshold': float(
                            device.read_attribute('center_gravity_threshold').value
                        ),
                        'width': int(device.read_attribute('width').value),
                        'height': int(device.read_attribute('height').value),
                    }

            contours = []
            contour_error = ''
            contour_profile = None
            if include_contours and contour_settings:
                try:
                    from DeviceServers.control.laser_pointing.beam_metrics import (
                        beam_threshold_contours,
                        camera_contour_profile,
                    )

                    contour_profile = camera_contour_profile(
                        device_name, contour_settings['threshold']
                    )
                    fitted = beam_threshold_contours(
                        image_data,
                        **contour_profile,
                        width=contour_settings['width'],
                        height=contour_settings['height'],
                    )
                    contours = [
                        {
                            key: value
                            for key, value in contour.items()
                            if key != 'points'
                        }
                        for contour in fitted
                    ]
                except Exception as error:
                    contour_error = str(error)

            return api.jsonify({
                'image': api.make_json_safe(image_data),
                'cg_position': cg_position,
                'contours': api.make_json_safe(contours),
                'contour_profile': api.make_json_safe(contour_profile),
                'contour_error': contour_error,
                'timestamp': image_attr.time.tv_sec if hasattr(image_attr, 'time') else None,
                'success': True
            })

        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def list_spectrographs():
        """Get list of Andor spectrograph devices directly from Tango DB."""
        try:
            db = api.tango_gateway.create_database()
            spectro_classes = ['DS_ANDOR_SPECTROGRAPH']
            spectrograph_list = []

            for dev_class in spectro_classes:
                try:
                    device_list = db.get_device_name('*', dev_class)
                    for device_name in device_list:
                        try:
                            device = api.tango_gateway.create_device_proxy(device_name)
                            info = {
                                'name': device_name,
                                'state': str(device.state()),
                                'class': dev_class,
                                'available': True,
                            }
                            try:
                                info['friendly_name'] = str(device.read_attribute('device_friendly_name').value)
                            except Exception:
                                pass
                            try:
                                info['serial_number'] = str(device.read_attribute('serial_number').value)
                            except Exception:
                                pass
                            spectrograph_list.append(info)
                        except Exception as exc:
                            spectrograph_list.append({
                                'name': device_name,
                                'state': 'UNKNOWN',
                                'class': dev_class,
                                'available': False,
                                'error': str(exc),
                            })
                except Exception as exc:
                    print(f"No devices found for class {dev_class}: {exc}")

            return api.jsonify({'spectrographs': spectrograph_list, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_spectrograph_info(device_name):
        """Get detailed spectrograph information."""
        try:
            device = api.DeviceManager.get_device(device_name)
            info = {
                'name': device_name,
                'state': str(device.state()),
                'status': device.status(),
            }

            attr_names = [
                'device_friendly_name', 'serial_number', 'wavelength_nm',
                'grating', 'gratings_number', 'pixel_number_attr',
                'pixel_width_um_attr', 'input_side_slit_um',
                'output_side_slit_um', 'input_direct_slit_um',
                'output_direct_slit_um', 'calibration',
                'lines_per_mm', 'blaze_wavelength_nm',
            ]
            for attr_name in attr_names:
                try:
                    attr = device.read_attribute(attr_name)
                    info[attr_name] = api.make_json_safe(attr.value)
                except Exception:
                    pass

            return api.jsonify({'spectrograph_info': info, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def handle_spectrograph_parameters(device_name):
        """Get or set spectrograph parameters."""
        try:
            if api.request.method == 'GET':
                device = api.DeviceManager.get_device(device_name)
                parameters = {}
                attr_names = [
                    'wavelength_nm', 'grating', 'pixel_number_attr',
                    'pixel_width_um_attr', 'input_side_slit_um',
                    'output_side_slit_um', 'input_direct_slit_um',
                    'output_direct_slit_um',
                ]
                for attr_name in attr_names:
                    try:
                        attr = device.read_attribute(attr_name)
                        parameters[attr_name] = api.make_json_safe(attr.value)
                    except Exception:
                        pass
                return api.jsonify({'parameters': parameters, 'success': True})

            api._maybe_require_auth()
            data = api._mutation_payload()
            if data is None or set(data) - api._SPECTROGRAPH_PARAMETER_NAMES:
                return api.jsonify({'error': 'Spectrograph parameter batch is empty or contains unsupported attributes', 'success': False}), 400
            writes, parameter_names = api._parameter_write_plan(data)
            blocked = api.require_http_hardware(
                action='write_parameters',
                targets=[{'device': str(device_name), 'command': 'write_attribute'} for _ in parameter_names],
                args={'writes': writes}, route_id='spectrograph.parameters', wrapper_fields=api._SPECTROGRAPH_PARAMETER_NAMES,
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)
            results = {}
            for param_name in parameter_names:
                param_value = data[param_name]
                try:
                    device.write_attribute(param_name, param_value)
                    attr = device.read_attribute(param_name)
                    results[param_name] = {'success': True, 'value': api.make_json_safe(attr.value)}
                except Exception as exc:
                    results[param_name] = {'success': False, 'error': str(exc)}

            return api.jsonify({'results': results, 'success': True})
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def trigger_camera(device_name):
        """Trigger camera software trigger"""
        try:
            api._maybe_require_auth()
            data = api._hardware_payload()
            if data is None or set(data) - {'command_variant'}:
                return api.jsonify({'error': 'Trigger accepts no payload', 'success': False}), 400
            command_variant = api._command_variant(data, api._CAMERA_TRIGGER_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            blocked = api.require_http_hardware(
                action='trigger',
                targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in api._CAMERA_TRIGGER_COMMANDS],
                args={'command_variant': command_variant or 'legacy_autodetect'},
                route_id='camera.trigger', wrapper_fields={'command_variant'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            if command_variant is not None:
                device.command_inout(command_variant)
                message = 'Software trigger executed' if command_variant == 'TriggerSoftware' else 'Trigger executed'
            else:
                # Local opt-out retains legacy fallback behavior.
                try:
                    device.command_inout('TriggerSoftware')
                    message = 'Software trigger executed'
                except:
                    device.command_inout('Trigger')
                    message = 'Trigger executed'

            return api.jsonify({
                'message': message,
                'success': True
            })

        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    api.camera_capture = camera_capture
    api.list_cameras = list_cameras
    api.get_camera_info = get_camera_info
    api.handle_camera_parameters = handle_camera_parameters
    api.handle_camera_grabbing = handle_camera_grabbing
    api.get_camera_image = get_camera_image
    api.list_spectrographs = list_spectrographs
    api.get_spectrograph_info = get_spectrograph_info
    api.handle_spectrograph_parameters = handle_spectrograph_parameters
    api.trigger_camera = trigger_camera
