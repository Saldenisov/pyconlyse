# device_api.py - Enhanced Tango Device API for Browser Clients
import sys as _sys
from device_api_readback import bind as _bind_readback
from device_api_acquisition import bind as _bind_acquisition
from device_api_request import bind as _bind_request
from device_api_servers import bind as _bind_servers
from device_api_attributes import bind as _bind_attributes
from device_api_laser_pointing import bind as _bind_laser_pointing
from device_api_power import bind as _bind_power
from device_api_optics import bind as _bind_optics

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

_bind_readback(_sys.modules[__name__])


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


_bind_acquisition(_sys.modules[__name__])


_bind_laser_pointing(_sys.modules[__name__])


_bind_request(_sys.modules[__name__])


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


# Debug endpoint to test WebSocket monitoring
@device_api.route('/api/debug/monitor/<path:device_name>', methods=['GET', 'POST'])
def debug_monitor_device(device_name):
    """Expose a passive GET status and explicitly start monitoring by POST."""
    try:
        if request.method == 'GET':
            return jsonify({
                'device': device_name,
                'monitoring': False,
                'message': 'Use POST to start debug monitoring',
                'success': True,
            })
        from websocket_handler import monitor
        monitor.monitor_device(device_name, "debug_room")
        return jsonify({
            'message': f'Manual monitoring triggered for {device_name}',
            'success': True
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

# Global device proxy cache and monitoring
device_cache = {}
device_cache_lock = threading.RLock()
device_operation_locks = {}
monitoring_threads = {}
monitoring_active = {}


def _device_proxy_target(device_name):
    name = str(device_name)
    if name.startswith("tango://"):
        return name
    tango_host = os.environ.get("TANGO_HOST", "").strip()
    return f"tango://{tango_host}/{name}" if tango_host else name

class DeviceManager:
    """Manages Tango device connections and operations"""

    @staticmethod
    def get_device(device_name):
        """Get or create device proxy with caching"""
        with device_cache_lock:
            if device_name not in device_cache:
                try:
                    device_cache[device_name] = tango_gateway.create_device_proxy(
                        _device_proxy_target(device_name)
                    )
                except Exception as e:
                    raise Exception(f"Could not connect to device {device_name}: {str(e)}")
            return device_cache[device_name]

    @staticmethod
    def discard_device(device_name):
        """Forget a proxy whose CORBA connection became stale."""
        with device_cache_lock:
            device_cache.pop(device_name, None)

    @staticmethod
    def operation_lock(device_name):
        """Serialize calls for one Tango proxy; DeviceProxy is not request-thread safe."""
        with device_cache_lock:
            return device_operation_locks.setdefault(device_name, threading.RLock())

    @staticmethod
    def get_device_summary(device_name):
        device = DeviceManager.get_device(device_name)
        device_info = device.info()
        return {
            'name': device_name,
            'state': str(device.state()),
            'status': device.status(),
            'info': getattr(device_info, 'dev_class', ''),
            'server': getattr(device_info, 'server_id', ''),
            'connected': True,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def get_device_properties(device_name):
        properties = {}
        db = tango_gateway.create_database()
        prop_list = db.get_device_property_list(device_name, '*')
        for prop_name in prop_list:
            try:
                prop_values = db.get_device_property(device_name, prop_name)
                properties[prop_name] = make_json_safe(prop_values.get(prop_name, []))
            except Exception as e:
                properties[prop_name] = {'error': str(e)}
        return properties

    @staticmethod
    def get_device_attributes(device):
        attributes = {}
        attr_list = device.get_attribute_list()
        for attr_name in attr_list:
            try:
                attr = device.read_attribute(attr_name)
                attr_config = device.get_attribute_config(attr_name)
                value = attr.value if hasattr(attr, 'value') else None
                attributes[attr_name] = {
                    'value': make_json_safe(value),
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                    'writable': attr_config.writable != tango.AttrWriteType.READ,
                    'data_type': str(attr_config.data_type),
                    'unit': attr_config.unit if hasattr(attr_config, 'unit') else '',
                    'description': attr_config.description if hasattr(attr_config, 'description') else ''
                }
            except Exception as e:
                attributes[attr_name] = {'error': str(e)}
        return attributes

    @staticmethod
    def get_device_commands(device):
        commands = {}
        cmd_list = device.get_command_list()
        for cmd_name in cmd_list:
            try:
                cmd_config = device.get_command_config(cmd_name)
                commands[cmd_name] = {
                    'in_type': str(cmd_config.in_type),
                    'out_type': str(cmd_config.out_type),
                    'in_type_desc': cmd_config.in_type_desc,
                    'out_type_desc': cmd_config.out_type_desc
                }
            except Exception as e:
                commands[cmd_name] = {'error': str(e)}
        return commands


def _read_device_snapshot(device_name, server_name, dev_class):
    """Read one device through the existing cache and reconnect retry contract."""
    def read_state_and_info():
        device = DeviceManager.get_device(device_name)
        current_state = str(device.state())
        current_server = server_name
        current_class = dev_class
        if not current_server or not current_class:
            info = device.info()
            current_server = current_server or getattr(info, "server_id", None)
            current_class = current_class or getattr(info, "dev_class", None)
        return current_state, current_server, current_class

    return _with_device_retry(device_name, read_state_and_info)


_device_snapshot_service = DeviceSnapshotService(
    lambda: tango_gateway.create_database(),
    _read_device_snapshot,
)
_device_catalog_service = DeviceCatalogService()


_bind_servers(_sys.modules[__name__])


get_server_diagnostics = (device_api.route('/api/server/<path:server_name>/diagnostics', methods=['GET']))(get_server_diagnostics)


list_devices = (device_api.route('/api/devices', methods=['GET']))(list_devices)


control_server = (device_api.route('/api/server/control', methods=['POST']))(control_server)

_bind_attributes(_sys.modules[__name__])
get_device_info = (device_api.route('/api/device/<path:device_name>/info', methods=['GET']))(get_device_info)


get_device_summary = (device_api.route('/api/device/<path:device_name>/summary', methods=['GET']))(get_device_summary)


get_device_commands = (device_api.route('/api/device/<path:device_name>/commands', methods=['GET']))(get_device_commands)

get_device_attributes = (device_api.route('/api/device/<path:device_name>/attributes', methods=['GET']))(get_device_attributes)

handle_attribute = (device_api.route('/api/device/<path:device_name>/attribute/<attr_name>', methods=['GET', 'POST']))(handle_attribute)

execute_command = (device_api.route('/api/device/<path:device_name>/command/<command_name>', methods=['POST']))(execute_command)

get_device_state = (device_api.route('/api/device/<path:device_name>/state', methods=['GET']))(get_device_state)

get_device_properties = (device_api.route('/api/device/<path:device_name>/properties', methods=['GET']))(get_device_properties)


get_laser_pointing_snapshot = (device_api.route('/api/laser-pointing/<path:device_name>/snapshot', methods=['GET']))(get_laser_pointing_snapshot)


_bind_power(_sys.modules[__name__])
get_pdu_outputs = (device_api.route('/api/device/<path:device_name>/pdu/outputs', methods=['GET']))(get_pdu_outputs)

get_ds_itest_psu_slots = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slots', methods=['GET']))(get_ds_itest_psu_slots)

get_ds_itest_psu_tab_config = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/tab_config', methods=['GET']))(get_ds_itest_psu_tab_config)

get_itest_all_slots = (device_api.route('/api/device/itest/<path:device_name>/all_slots', methods=['GET']))(get_itest_all_slots)

set_itest_slot_output = (device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/output', methods=['POST']))(set_itest_slot_output)

set_ds_itest_psu_current = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/current', methods=['POST']))(set_ds_itest_psu_current)

set_ds_itest_psu_state = (device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/state', methods=['POST']))(set_ds_itest_psu_state)

handle_itest_current = (device_api.route('/api/device/itest/<path:device_name>/current', methods=['GET', 'POST']))(handle_itest_current)

handle_itest_slot_current = (device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/current', methods=['GET', 'POST']))(handle_itest_slot_current)

_bind_optics(_sys.modules[__name__])
camera_capture = (device_api.route('/api/device/camera/<path:device_name>/capture', methods=['POST']))(camera_capture)

list_daqmx_devices = (device_api.route('/api/daqmx/devices', methods=['GET']))(list_daqmx_devices)


list_psp_devices = (device_api.route('/api/psp/devices', methods=['GET']))(list_psp_devices)


get_psp_group_history = (device_api.route('/api/psp/device/<path:device_name>/group/<group_name>/history', methods=['GET']))(get_psp_group_history)


get_psp_pending_commands = (device_api.route('/api/psp/device/<path:device_name>/commands/pending', methods=['GET']))(get_psp_pending_commands)


acknowledge_psp_command = (device_api.route('/api/psp/device/<path:device_name>/commands/ack', methods=['POST']))(acknowledge_psp_command)


get_daqmx_latest = (device_api.route('/api/daqmx/device/<path:device_name>/latest', methods=['GET']))(get_daqmx_latest)


get_daqmx_history = (device_api.route('/api/daqmx/device/<path:device_name>/history', methods=['GET']))(get_daqmx_history)


write_daqmx_channel = (device_api.route('/api/daqmx/device/<path:device_name>/write', methods=['POST']))(write_daqmx_channel)


reset_daqmx_counter = (device_api.route('/api/daqmx/device/<path:device_name>/counter/reset', methods=['POST']))(reset_daqmx_counter)

list_cameras = (device_api.route('/api/cameras', methods=['GET']))(list_cameras)

get_camera_info = (device_api.route('/api/camera/<path:device_name>/info', methods=['GET']))(get_camera_info)

handle_camera_parameters = (device_api.route('/api/camera/<path:device_name>/parameters', methods=['GET', 'POST']))((device_api.route('/api/device/camera/<path:device_name>/parameters', methods=['GET', 'POST']))(handle_camera_parameters))

handle_camera_grabbing = (device_api.route('/api/camera/<path:device_name>/grabbing', methods=['GET', 'POST']))(handle_camera_grabbing)

get_camera_image = (device_api.route('/api/camera/<path:device_name>/image', methods=['GET']))(get_camera_image)

list_spectrographs = (device_api.route('/api/spectrographs', methods=['GET']))(list_spectrographs)

get_spectrograph_info = (device_api.route('/api/spectrograph/<path:device_name>/info', methods=['GET']))(get_spectrograph_info)

handle_spectrograph_parameters = (device_api.route('/api/spectrograph/<path:device_name>/parameters', methods=['GET', 'POST']))(handle_spectrograph_parameters)

trigger_camera = (device_api.route('/api/camera/<path:device_name>/trigger', methods=['POST']))(trigger_camera)

# Error handling
@device_api.errorhandler(Exception)
def handle_device_error(error):
    """Global error handler for device API"""
    return jsonify({
        'error': str(error),
        'traceback': traceback.format_exc(),
        'success': False
    }), 500
