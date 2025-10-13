# device_api.py - Enhanced Tango Device API for Browser Clients
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import tango
import json
import traceback
from datetime import datetime
import threading
import time

device_api = Blueprint("device_api", __name__)

# Global device proxy cache and monitoring
device_cache = {}
monitoring_threads = {}
monitoring_active = {}

class DeviceManager:
    """Manages Tango device connections and operations"""
    
    @staticmethod
    def get_device(device_name):
        """Get or create device proxy with caching"""
        if device_name not in device_cache:
            try:
                device_cache[device_name] = tango.DeviceProxy(device_name)
            except Exception as e:
                raise Exception(f"Could not connect to device {device_name}: {str(e)}")
        return device_cache[device_name]
    
    @staticmethod
    def get_device_info(device_name):
        """Get comprehensive device information"""
        try:
            device = DeviceManager.get_device(device_name)
            
            # Get basic device info
            info = {
                'name': device_name,
                'state': str(device.state()),
                'status': device.status(),
                'info': device.info().dev_class,
                'server': device.info().server_id,
                'connected': True,
                'timestamp': datetime.now().isoformat()
            }
            
            # Get attributes
            attributes = {}
            try:
                attr_list = device.get_attribute_list()
                for attr_name in attr_list:
                    try:
                        attr = device.read_attribute(attr_name)
                        attr_config = device.get_attribute_config(attr_name)
                        
                        attributes[attr_name] = {
                            'value': attr.value if hasattr(attr, 'value') else None,
                            'quality': str(attr.quality),
                            'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                            'writable': attr_config.writable != tango.AttrWriteType.READ,
                            'data_type': str(attr_config.data_type),
                            'unit': attr_config.unit if hasattr(attr_config, 'unit') else '',
                            'description': attr_config.description if hasattr(attr_config, 'description') else ''
                        }
                    except Exception as e:
                        attributes[attr_name] = {'error': str(e)}
            except Exception as e:
                info['attributes_error'] = str(e)
            
            info['attributes'] = attributes
            
            # Get commands
            commands = {}
            try:
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
            except Exception as e:
                info['commands_error'] = str(e)
            
            info['commands'] = commands
            return info
            
        except Exception as e:
            return {
                'name': device_name,
                'connected': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

@device_api.route('/api/devices', methods=['GET'])
@jwt_required()
def list_devices():
    """Get list of all available devices"""
    try:
        db = tango.Database()
        devices = db.get_device_exported("*")
        
        device_list = []
        for device_name in devices:
            try:
                # Quick state check
                device = tango.DeviceProxy(device_name)
                state = str(device.state())
                server = device.info().server_id
                dev_class = device.info().dev_class
                
                device_list.append({
                    'name': device_name,
                    'state': state,
                    'server': server,
                    'class': dev_class,
                    'available': True
                })
            except Exception:
                device_list.append({
                    'name': device_name,
                    'available': False
                })
        
        return jsonify({'devices': device_list, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<device_name>/info', methods=['GET'])
@jwt_required()
def get_device_info(device_name):
    """Get detailed device information"""
    try:
        info = DeviceManager.get_device_info(device_name)
        return jsonify({'device_info': info, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<device_name>/attributes', methods=['GET'])
@jwt_required()
def get_device_attributes(device_name):
    """Get all device attributes"""
    try:
        device = DeviceManager.get_device(device_name)
        attributes = {}
        
        attr_list = device.get_attribute_list()
        for attr_name in attr_list:
            try:
                attr = device.read_attribute(attr_name)
                attributes[attr_name] = {
                    'value': attr.value if hasattr(attr, 'value') else None,
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None
                }
            except Exception as e:
                attributes[attr_name] = {'error': str(e)}
        
        return jsonify({'attributes': attributes, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<device_name>/attribute/<attr_name>', methods=['GET', 'POST'])
@jwt_required()
def handle_attribute(device_name, attr_name):
    """Read or write a specific attribute"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            attr = device.read_attribute(attr_name)
            return jsonify({
                'attribute': attr_name,
                'value': attr.value if hasattr(attr, 'value') else None,
                'quality': str(attr.quality),
                'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                'success': True
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            value = data.get('value')
            
            if value is None:
                return jsonify({'error': 'No value provided', 'success': False}), 400
            
            device.write_attribute(attr_name, value)
            # Read back the attribute to confirm
            attr = device.read_attribute(attr_name)
            
            return jsonify({
                'attribute': attr_name,
                'value': attr.value if hasattr(attr, 'value') else None,
                'quality': str(attr.quality),
                'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                'success': True
            })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<device_name>/command/<command_name>', methods=['POST'])
@jwt_required()
def execute_command(device_name, command_name):
    """Execute a device command"""
    try:
        device = DeviceManager.get_device(device_name)
        data = request.get_json() or {}
        args = data.get('args')
        
        if args is not None:
            result = device.command_inout(command_name, args)
        else:
            result = device.command_inout(command_name)
        
        return jsonify({
            'command': command_name,
            'result': result,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<device_name>/state', methods=['GET'])
@jwt_required()
def get_device_state(device_name):
    """Get device state and status"""
    try:
        device = DeviceManager.get_device(device_name)
        return jsonify({
            'device': device_name,
            'state': str(device.state()),
            'status': device.status(),
            'timestamp': datetime.now().isoformat(),
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Device-specific endpoints for common PYCONLYSE devices
@device_api.route('/api/device/itest/<device_name>/current', methods=['GET', 'POST'])
@jwt_required()
def handle_itest_current(device_name):
    """Handle iTest PSU current operations"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            setpoint = device.read_attribute('CurrentSetpoint').value
            measured = device.read_attribute('MeasuredCurrent').value
            voltage = device.read_attribute('MeasuredVoltage').value
            
            return jsonify({
                'current_setpoint': setpoint,
                'measured_current': measured,
                'measured_voltage': voltage,
                'success': True
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            action = data.get('action')
            value = data.get('value')
            
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
                return jsonify({'error': 'Unknown action', 'success': False}), 400
            
            # Read back current value
            setpoint = device.read_attribute('CurrentSetpoint').value
            return jsonify({'current_setpoint': setpoint, 'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/camera/<device_name>/capture', methods=['POST'])
@jwt_required()
def camera_capture(device_name):
    """Trigger camera capture"""
    try:
        device = DeviceManager.get_device(device_name)
        data = request.get_json() or {}
        
        exposure_time = data.get('exposure_time', 1.0)
        
        # Set exposure time if provided
        if 'exposure_time' in data:
            device.write_attribute('ExposureTime', exposure_time)
        
        # Trigger capture
        result = device.command_inout('StartAcquisition')
        
        return jsonify({
            'command': 'StartAcquisition',
            'exposure_time': exposure_time,
            'result': result,
            'success': True
        })
    
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