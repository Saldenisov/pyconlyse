# device_api.py - Enhanced Tango Device API for Browser Clients
from sys import modules as _refactor_modules

from device_api_parts_make_json_safe import _bind_device_api_parts_make_json_safe

from device_api_parts_build_psp_series import _bind_device_api_parts_build_psp_series

from device_api_parts_list_devices import _bind_device_api_parts_list_devices

from device_api_parts_get_laser_pointing_snapshot import _bind_device_api_parts_get_laser_pointing_snapshot

from device_api_parts_get_ds_itest_psu_tab_config import _bind_device_api_parts_get_ds_itest_psu_tab_config

from device_api_parts_get_psp_pending_commands import _bind_device_api_parts_get_psp_pending_commands

import ast
import json
import math
import os
import re
import threading
import time
import traceback
from datetime import datetime

import numpy as np
import tango
import tango_gateway
from device_snapshot_service import DeviceSnapshotService
from device_catalog_service import DeviceCatalogService
from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request
from hardware_authorization import (
    AuthorizationError,
    authorization_config_from_environment,
    authorization_required,
    load_policy,
    require_http_hardware,
    trusted_starter_for_server,
)
from mutation_auth import install_mutation_auth

device_api = Blueprint("device_api", __name__)
install_mutation_auth(device_api, protected_get_endpoints=("debug_monitor_device",))

# Helper function to convert numpy arrays to lists for JSON serialization
_device_api_parts_make_json_safe = _bind_device_api_parts_make_json_safe(_refactor_modules[__name__])
make_json_safe = _device_api_parts_make_json_safe["make_json_safe"]


_parse_controller_mapping = _device_api_parts_make_json_safe["_parse_controller_mapping"]


_read_selected_device_properties = _device_api_parts_make_json_safe["_read_selected_device_properties"]


_read_attr_sequence = _device_api_parts_make_json_safe["_read_attr_sequence"]


def _read_attr_sequence_strict(device, attr_name):
    """Read an attribute as a Python list, preserving Tango read errors for retry."""
    return _sequence_from_value(make_json_safe(device.read_attribute(attr_name).value))


_sequence_from_value = _device_api_parts_make_json_safe["_sequence_from_value"]


_as_int = _device_api_parts_make_json_safe["_as_int"]


_is_delayed_tango_reconnect = _device_api_parts_make_json_safe["_is_delayed_tango_reconnect"]


_is_transient_tango_read_failure = _device_api_parts_make_json_safe["_is_transient_tango_read_failure"]


_with_tango_retry = _device_api_parts_make_json_safe["_with_tango_retry"]


_with_device_retry = _device_api_parts_make_json_safe["_with_device_retry"]


_coerce_binary_state_args = _device_api_parts_make_json_safe["_coerce_binary_state_args"]


_read_pdu_states = _device_api_parts_make_json_safe["_read_pdu_states"]


_is_missing_attribute_error = _device_api_parts_make_json_safe["_is_missing_attribute_error"]


_read_optional_attr_sequence_strict = _device_api_parts_make_json_safe["_read_optional_attr_sequence_strict"]


_read_pdu_states_strict = _device_api_parts_make_json_safe["_read_pdu_states_strict"]


_wait_for_pdu_states = _device_api_parts_make_json_safe["_wait_for_pdu_states"]


_as_bool = _device_api_parts_make_json_safe["_as_bool"]


_read_camera_is_grabbing = _device_api_parts_make_json_safe["_read_camera_is_grabbing"]


_wait_for_camera_grabbing = _device_api_parts_make_json_safe["_wait_for_camera_grabbing"]


_resolve_command_name = _device_api_parts_make_json_safe["_resolve_command_name"]


DAQMX_DEVICE_CLASSES = (
    "DS_DAQmx",
    "DS_DAQmx_ZMQ",
    "DS_PSP_SUPERVISION",
    "DS_PSP_Supervision",
    "DS_PSP",
)

PSP_GROUPS = (
    "timestamp",
    "cooling",
    "hf",
    "ht",
    "modulator",
    "vacuum",
    "magnets",
    "other",
)


_safe_json_loads = _device_api_parts_make_json_safe["_safe_json_loads"]


_to_scalar_value = _device_api_parts_make_json_safe["_to_scalar_value"]


_list_device_commands_lower = _device_api_parts_make_json_safe["_list_device_commands_lower"]


_read_daqmx_latest_payload = _device_api_parts_make_json_safe["_read_daqmx_latest_payload"]


_normalize_daqmx_channels = _device_api_parts_make_json_safe["_normalize_daqmx_channels"]


_read_daqmx_device_info = _device_api_parts_make_json_safe["_read_daqmx_device_info"]


def _laser_camera_number(value):
    match = re.search(r'cam(?:era)?[_-]?(\d+)', str(value or ''), re.IGNORECASE)
    return int(match.group(1)) if match else None


_is_owned_laser_flipper = _device_api_parts_make_json_safe["_is_owned_laser_flipper"]


_to_float_or_none = _device_api_parts_make_json_safe["_to_float_or_none"]


_normalize_psp_group = _device_api_parts_make_json_safe["_normalize_psp_group"]


_parse_psp_payload = _device_api_parts_make_json_safe["_parse_psp_payload"]


_normalize_psp_entry = _device_api_parts_make_json_safe["_normalize_psp_entry"]
del _device_api_parts_make_json_safe


_device_api_parts_build_psp_series = _bind_device_api_parts_build_psp_series(_refactor_modules[__name__])
_build_psp_series = _device_api_parts_build_psp_series["_build_psp_series"]


_read_psp_group_history = _device_api_parts_build_psp_series["_read_psp_group_history"]


_write_daqmx_channel = _device_api_parts_build_psp_series["_write_daqmx_channel"]


_env_bool = _device_api_parts_build_psp_series["_env_bool"]


_query_bool = _device_api_parts_build_psp_series["_query_bool"]


_maybe_require_auth = _device_api_parts_build_psp_series["_maybe_require_auth"]


_hardware_payload = _device_api_parts_build_psp_series["_hardware_payload"]


def _invalid_hardware_payload():
    return jsonify({'error': 'JSON request body must be an object', 'success': False}), 400


def _authorization_error_response(exc):
    return jsonify({'error': exc.message, 'success': False, 'code': exc.code}), exc.status_code


_CAMERA_PARAMETER_NAMES = frozenset({
    'exposure_time', 'gain', 'width', 'height', 'offsetX', 'offsetY',
    'format_pixel', 'trigger_mode', 'trigger_delay', 'binning_horizontal',
    'binning_vertical', 'number_kinetics', 'center_gravity_threshold',
})
_SPECTROGRAPH_PARAMETER_NAMES = frozenset({
    'wavelength_nm', 'grating', 'pixel_number_attr', 'pixel_width_um_attr',
    'input_side_slit_um', 'output_side_slit_um', 'input_direct_slit_um',
    'output_direct_slit_um',
})
_CAMERA_GRAB_COMMANDS = {
    'start': ('start_grabbing', 'startgrabbing', 'StartGrabbing', 'start', 'on'),
    'stop': ('stop_grabbing', 'stopgrabbing', 'StopGrabbing', 'stop', 'off'),
}
_CAMERA_TRIGGER_COMMANDS = ('TriggerSoftware', 'Trigger')
_PSP_ACK_COMMANDS = ('acknowledge_command_json', 'AcknowledgeCommandJson')
_DAQMX_WRITE_COMMANDS = (
    'write_variable_json', 'set_variable_value_json', 'set_channel_value_json',
    'write_variable', 'set_variable_value', 'set_channel_value',
    'write_digital_output', 'write_channel',
)
_DAQMX_RESET_COMMANDS = ('reset_counter',)
_PSP_ACK_FIELDS = frozenset({
    'command', 'id', 'ok', 'status', 'error', 'message', 'timestamp',
    'command_variant',
})


_mutation_payload = _device_api_parts_build_psp_series["_mutation_payload"]


_finite_number = _device_api_parts_build_psp_series["_finite_number"]


_invalid_psp_acknowledgement = _device_api_parts_build_psp_series["_invalid_psp_acknowledgement"]


_command_variant = _device_api_parts_build_psp_series["_command_variant"]


_parameter_write_plan = _device_api_parts_build_psp_series["_parameter_write_plan"]

# Debug endpoint to test WebSocket monitoring
debug_monitor_device = (device_api.route('/api/debug/monitor/<path:device_name>', methods=['GET', 'POST']))(_device_api_parts_build_psp_series["debug_monitor_device"])

# Global device proxy cache and monitoring
device_cache = {}
device_cache_lock = threading.RLock()
device_operation_locks = {}
monitoring_threads = {}
monitoring_active = {}


_device_proxy_target = _device_api_parts_build_psp_series["_device_proxy_target"]

DeviceManager = _device_api_parts_build_psp_series["DeviceManager"]


_read_device_snapshot = _device_api_parts_build_psp_series["_read_device_snapshot"]


_device_snapshot_service = DeviceSnapshotService(
    lambda: tango_gateway.create_database(),
    _read_device_snapshot,
)
_device_catalog_service = DeviceCatalogService()


def _catalog_device_state(device_name):
    """Read state through the existing DeviceManager cache without retries."""
    return str(DeviceManager.get_device(device_name).state())


_get_starter_devices = _device_api_parts_build_psp_series["_get_starter_devices"]


_get_starter_server_lists = _device_api_parts_build_psp_series["_get_starter_server_lists"]


_wait_for_starter_server = _device_api_parts_build_psp_series["_wait_for_starter_server"]


_find_starter_for_server = _device_api_parts_build_psp_series["_find_starter_for_server"]


def _is_already_running_error(exc):
    text = str(exc).lower()
    return 'already_running' in text or 'already running' in text


_resolve_server_name = _device_api_parts_build_psp_series["_resolve_server_name"]


_tail_log_text = _device_api_parts_build_psp_series["_tail_log_text"]


_read_starter_log = _device_api_parts_build_psp_series["_read_starter_log"]


_read_device_diagnostics = _device_api_parts_build_psp_series["_read_device_diagnostics"]


get_server_diagnostics = (device_api.route('/api/server/<path:server_name>/diagnostics', methods=['GET']))(_device_api_parts_build_psp_series["get_server_diagnostics"])
del _device_api_parts_build_psp_series


def _collect_device_list(probe_state, include_dserver, include_admin):
    """Compatibility facade for the shared read-only snapshot collector."""
    return _device_snapshot_service.collect(probe_state, include_dserver, include_admin)


def _refresh_device_list_cache(cache_key):
    """Compatibility facade for a shared snapshot cache refresh."""
    return _device_snapshot_service.refresh(cache_key)


def _schedule_device_list_refresh(cache_key):
    """Compatibility facade for one-flight shared snapshot refreshes."""
    return _device_snapshot_service.schedule_refresh(cache_key)


def start_device_snapshot_monitor(interval_s=10.0):
    """Keep the dashboard snapshot warm while the web backend is running."""
    return _device_snapshot_service.start_monitor(interval_s)

_device_api_parts_list_devices = _bind_device_api_parts_list_devices(_refactor_modules[__name__])
list_devices = (device_api.route('/api/devices', methods=['GET']))(_device_api_parts_list_devices["list_devices"])


control_server = (device_api.route('/api/server/control', methods=['POST']))(_device_api_parts_list_devices["control_server"])

get_device_info = (device_api.route('/api/device/<path:device_name>/info', methods=['GET']))(_device_api_parts_list_devices["get_device_info"])


get_device_summary = (device_api.route('/api/device/<path:device_name>/summary', methods=['GET']))(_device_api_parts_list_devices["get_device_summary"])


get_device_commands = (device_api.route('/api/device/<path:device_name>/commands', methods=['GET']))(_device_api_parts_list_devices["get_device_commands"])

get_device_attributes = (device_api.route('/api/device/<path:device_name>/attributes', methods=['GET']))(_device_api_parts_list_devices["get_device_attributes"])

handle_attribute = (device_api.route('/api/device/<path:device_name>/attribute/<attr_name>', methods=['GET', 'POST']))(_device_api_parts_list_devices["handle_attribute"])

execute_command = (device_api.route('/api/device/<path:device_name>/command/<command_name>', methods=['POST']))(_device_api_parts_list_devices["execute_command"])

get_device_state = (device_api.route('/api/device/<path:device_name>/state', methods=['GET']))(_device_api_parts_list_devices["get_device_state"])

get_device_properties = (device_api.route('/api/device/<path:device_name>/properties', methods=['GET']))(_device_api_parts_list_devices["get_device_properties"])
del _device_api_parts_list_devices


_device_api_parts_get_laser_pointing_snapshot = _bind_device_api_parts_get_laser_pointing_snapshot(_refactor_modules[__name__])
get_laser_pointing_snapshot = (device_api.route('/api/laser-pointing/<path:device_name>/snapshot', methods=['GET']))(_device_api_parts_get_laser_pointing_snapshot["get_laser_pointing_snapshot"])


get_pdu_outputs = (device_api.route('/api/device/<path:device_name>/pdu/outputs', methods=['GET']))(_device_api_parts_get_laser_pointing_snapshot["get_pdu_outputs"])

# Device-specific endpoints for common PYCONLYSE devices
get_ds_itest_psu_slots = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slots', methods=['GET']))(_device_api_parts_get_laser_pointing_snapshot["get_ds_itest_psu_slots"])
del _device_api_parts_get_laser_pointing_snapshot

_device_api_parts_get_ds_itest_psu_tab_config = _bind_device_api_parts_get_ds_itest_psu_tab_config(_refactor_modules[__name__])
get_ds_itest_psu_tab_config = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/tab_config', methods=['GET']))(_device_api_parts_get_ds_itest_psu_tab_config["get_ds_itest_psu_tab_config"])

get_itest_all_slots = (device_api.route('/api/device/itest/<path:device_name>/all_slots', methods=['GET']))(_device_api_parts_get_ds_itest_psu_tab_config["get_itest_all_slots"])

set_itest_slot_output = (device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/output', methods=['POST']))(_device_api_parts_get_ds_itest_psu_tab_config["set_itest_slot_output"])

set_ds_itest_psu_current = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/current', methods=['POST']))(_device_api_parts_get_ds_itest_psu_tab_config["set_ds_itest_psu_current"])

set_ds_itest_psu_state = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/state', methods=['POST']))(_device_api_parts_get_ds_itest_psu_tab_config["set_ds_itest_psu_state"])

handle_itest_current = (device_api.route('/api/device/itest/<path:device_name>/current', methods=['GET', 'POST']))(_device_api_parts_get_ds_itest_psu_tab_config["handle_itest_current"])

handle_itest_slot_current = (device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/current', methods=['GET', 'POST']))(_device_api_parts_get_ds_itest_psu_tab_config["handle_itest_slot_current"])

camera_capture = (device_api.route('/api/device/camera/<path:device_name>/capture', methods=['POST']))(_device_api_parts_get_ds_itest_psu_tab_config["camera_capture"])

# DAQmx / Supervision endpoints
list_daqmx_devices = (device_api.route('/api/daqmx/devices', methods=['GET']))(_device_api_parts_get_ds_itest_psu_tab_config["list_daqmx_devices"])


list_psp_devices = (device_api.route('/api/psp/devices', methods=['GET']))(_device_api_parts_get_ds_itest_psu_tab_config["list_psp_devices"])


get_psp_group_history = (device_api.route('/api/psp/device/<path:device_name>/group/<group_name>/history', methods=['GET']))(_device_api_parts_get_ds_itest_psu_tab_config["get_psp_group_history"])
del _device_api_parts_get_ds_itest_psu_tab_config


_device_api_parts_get_psp_pending_commands = _bind_device_api_parts_get_psp_pending_commands(_refactor_modules[__name__])
get_psp_pending_commands = (device_api.route('/api/psp/device/<path:device_name>/commands/pending', methods=['GET']))(_device_api_parts_get_psp_pending_commands["get_psp_pending_commands"])


acknowledge_psp_command = (device_api.route('/api/psp/device/<path:device_name>/commands/ack', methods=['POST']))(_device_api_parts_get_psp_pending_commands["acknowledge_psp_command"])


get_daqmx_latest = (device_api.route('/api/daqmx/device/<path:device_name>/latest', methods=['GET']))(_device_api_parts_get_psp_pending_commands["get_daqmx_latest"])


get_daqmx_history = (device_api.route('/api/daqmx/device/<path:device_name>/history', methods=['GET']))(_device_api_parts_get_psp_pending_commands["get_daqmx_history"])


write_daqmx_channel = (device_api.route('/api/daqmx/device/<path:device_name>/write', methods=['POST']))(_device_api_parts_get_psp_pending_commands["write_daqmx_channel"])


reset_daqmx_counter = (device_api.route('/api/daqmx/device/<path:device_name>/counter/reset', methods=['POST']))(_device_api_parts_get_psp_pending_commands["reset_daqmx_counter"])

# Camera-specific endpoints
list_cameras = (device_api.route('/api/cameras', methods=['GET']))(_device_api_parts_get_psp_pending_commands["list_cameras"])

get_camera_info = (device_api.route('/api/camera/<path:device_name>/info', methods=['GET']))(_device_api_parts_get_psp_pending_commands["get_camera_info"])

handle_camera_parameters = (device_api.route('/api/camera/<path:device_name>/parameters', methods=['GET', 'POST']))((device_api.route('/api/device/camera/<path:device_name>/parameters', methods=['GET', 'POST']))(_device_api_parts_get_psp_pending_commands["handle_camera_parameters"]))

handle_camera_grabbing = (device_api.route('/api/camera/<path:device_name>/grabbing', methods=['GET', 'POST']))(_device_api_parts_get_psp_pending_commands["handle_camera_grabbing"])
del _device_api_parts_get_psp_pending_commands

@device_api.route('/api/camera/<path:device_name>/image', methods=['GET'])
def get_camera_image(device_name):
    """Get the last captured image from camera"""
    try:
        include_contours = str(request.args.get('contours', '')).lower() in (
            '1', 'true', 'yes', 'on'
        )
        contour_settings = None
        with DeviceManager.operation_lock(device_name):
            device = DeviceManager.get_device(device_name)
            # DS_CAMERA_CCD.image starts grabbing when acquisition is stopped.
            # A passive browser preview must never turn the camera back on.
            if not _read_camera_is_grabbing(device):
                return jsonify({
                    'error': 'Camera acquisition is stopped',
                    'grabbing': False,
                    'success': False,
                }), 409

            image_attr = device.read_attribute('image')
            image_data = image_attr.value

            if image_data is None:
                return jsonify({'error': 'No image available', 'success': False}), 404

            # Get center of gravity if available
            cg_position = None
            try:
                cg_str = str(device.read_attribute('cg').value)
                cg_position = ast.literal_eval(cg_str)
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
        
        return jsonify({
            'image': make_json_safe(image_data),
            'cg_position': cg_position,
            'contours': make_json_safe(contours),
            'contour_profile': make_json_safe(contour_profile),
            'contour_error': contour_error,
            'timestamp': image_attr.time.tv_sec if hasattr(image_attr, 'time') else None,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrographs', methods=['GET'])
def list_spectrographs():
    """Get list of Andor spectrograph devices directly from Tango DB."""
    try:
        db = tango_gateway.create_database()
        spectro_classes = ['DS_ANDOR_SPECTROGRAPH']
        spectrograph_list = []

        for dev_class in spectro_classes:
            try:
                device_list = db.get_device_name('*', dev_class)
                for device_name in device_list:
                    try:
                        device = tango_gateway.create_device_proxy(device_name)
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

        return jsonify({'spectrographs': spectrograph_list, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrograph/<path:device_name>/info', methods=['GET'])
def get_spectrograph_info(device_name):
    """Get detailed spectrograph information."""
    try:
        device = DeviceManager.get_device(device_name)
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
                info[attr_name] = make_json_safe(attr.value)
            except Exception:
                pass

        return jsonify({'spectrograph_info': info, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrograph/<path:device_name>/parameters', methods=['GET', 'POST'])
def handle_spectrograph_parameters(device_name):
    """Get or set spectrograph parameters."""
    try:
        if request.method == 'GET':
            device = DeviceManager.get_device(device_name)
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
                    parameters[attr_name] = make_json_safe(attr.value)
                except Exception:
                    pass
            return jsonify({'parameters': parameters, 'success': True})

        _maybe_require_auth()
        data = _mutation_payload()
        if data is None or set(data) - _SPECTROGRAPH_PARAMETER_NAMES:
            return jsonify({'error': 'Spectrograph parameter batch is empty or contains unsupported attributes', 'success': False}), 400
        writes, parameter_names = _parameter_write_plan(data)
        blocked = require_http_hardware(
            action='write_parameters',
            targets=[{'device': str(device_name), 'command': 'write_attribute'} for _ in parameter_names],
            args={'writes': writes}, route_id='spectrograph.parameters', wrapper_fields=_SPECTROGRAPH_PARAMETER_NAMES,
        )
        if blocked is not None:
            return blocked
        device = DeviceManager.get_device(device_name)
        results = {}
        for param_name in parameter_names:
            param_value = data[param_name]
            try:
                device.write_attribute(param_name, param_value)
                attr = device.read_attribute(param_name)
                results[param_name] = {'success': True, 'value': make_json_safe(attr.value)}
            except Exception as exc:
                results[param_name] = {'success': False, 'error': str(exc)}

        return jsonify({'results': results, 'success': True})
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/trigger', methods=['POST'])
def trigger_camera(device_name):
    """Trigger camera software trigger"""
    try:
        _maybe_require_auth()
        data = _hardware_payload()
        if data is None or set(data) - {'command_variant'}:
            return jsonify({'error': 'Trigger accepts no payload', 'success': False}), 400
        command_variant = _command_variant(data, _CAMERA_TRIGGER_COMMANDS)
        if authorization_required() and command_variant is None:
            return jsonify({'error': 'command_variant is required', 'success': False}), 400
        if command_variant is None and data.get('command_variant') is not None:
            return jsonify({'error': 'command_variant is invalid', 'success': False}), 400
        blocked = require_http_hardware(
            action='trigger',
            targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in _CAMERA_TRIGGER_COMMANDS],
            args={'command_variant': command_variant or 'legacy_autodetect'},
            route_id='camera.trigger', wrapper_fields={'command_variant'},
        )
        if blocked is not None:
            return blocked
        device = DeviceManager.get_device(device_name)
        
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
        
        return jsonify({
            'message': message,
            'success': True
        })
    
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Error handling
@device_api.errorhandler(Exception)
def handle_device_error(error):
    """Global error handler for device API"""
    return jsonify({
        'error': str(error),
        'traceback': traceback.format_exc(),
        'success': False
    }), 500
