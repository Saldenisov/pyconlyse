# websocket_handler.py - WebSocket support for real-time device monitoring
import ast
import logging
import math
import os
import threading
import time
from datetime import datetime

import tango
from flask import current_app, request
from flask_jwt_extended import decode_token
from flask_socketio import SocketIO, emit, join_room, leave_room

# Configure logging - reduced verbosity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _json_safe_number(value, default=0.0):
    try:
        numeric = float(value)
    except Exception:
        return default
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _device_auth_required():
    """Require cookie authentication by default in production."""
    if _env_bool("PYCONLYSE_PRODUCTION", False):
        return True
    return _env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH", False)


def _jwt_access_cookie_name():
    try:
        return current_app.config.get("JWT_ACCESS_COOKIE_NAME", "access_token_cookie")
    except RuntimeError:
        return "access_token_cookie"


def _socket_auth_allowed(_auth_payload=None):
    """Validate the JWT supplied by the Socket.IO request cookie."""
    if not _device_auth_required():
        return True
    try:
        token = request.cookies.get(_jwt_access_cookie_name())
        if not token:
            return False
        decode_token(str(token))
        return True
    except Exception:
        return False

# Global SocketIO instance - will be initialized in app.py
socketio = None

# Global monitoring state
monitoring_rooms = {}  # room_id -> {'devices': set(), 'thread': thread_obj, 'active': bool, 'generation': int}
device_subscriptions = {}  # device_name -> set of Socket.IO session IDs
client_subscriptions = {}  # Socket.IO session ID -> set of device names
subscription_lock = threading.RLock()
_monitoring_room_generation = 0


def _room_id(device_name):
    return f"device_{device_name}"


def _add_subscription(sid, device_name):
    """Record one client's device subscription and start its monitor once."""
    global _monitoring_room_generation
    room_id = _room_id(device_name)
    with subscription_lock:
        client_devices = client_subscriptions.setdefault(sid, set())
        if device_name in client_devices:
            return room_id, False

        client_devices.add(device_name)
        subscribers = device_subscriptions.setdefault(device_name, set())
        subscribers.add(sid)

        if room_id not in monitoring_rooms:
            _monitoring_room_generation += 1
            generation = _monitoring_room_generation
            monitoring_rooms[room_id] = {
                'devices': {device_name},
                'active': True,
                'thread': None,
                'generation': generation,
            }
            thread = threading.Thread(
                target=monitor.monitoring_loop,
                args=(room_id, generation),
                daemon=True
            )
            monitoring_rooms[room_id]['thread'] = thread
            try:
                thread.start()
            except Exception:
                del monitoring_rooms[room_id]
                subscribers.remove(sid)
                if not subscribers:
                    del device_subscriptions[device_name]
                client_devices.remove(device_name)
                if not client_devices:
                    del client_subscriptions[sid]
                raise

    return room_id, True


def _remove_subscription(sid, device_name):
    """Remove one client subscription and stop its monitor after the last client."""
    room_id = _room_id(device_name)
    with subscription_lock:
        client_devices = client_subscriptions.get(sid)
        if not client_devices or device_name not in client_devices:
            return room_id, False

        client_devices.remove(device_name)
        if not client_devices:
            del client_subscriptions[sid]

        subscribers = device_subscriptions.get(device_name)
        if subscribers is not None:
            subscribers.discard(sid)
            if not subscribers:
                del device_subscriptions[device_name]
                room = monitoring_rooms.get(room_id)
                if room is not None:
                    room['active'] = False
                    del monitoring_rooms[room_id]

    return room_id, True


def _remove_client_subscriptions(sid):
    """Disconnect cleanup for every device owned by one Socket.IO session."""
    with subscription_lock:
        devices = tuple(client_subscriptions.get(sid, ()))
    for device_name in devices:
        _remove_subscription(sid, device_name)


def _socket_cors_origins(app):
    """Use same-origin Socket.IO checks when no explicit origin is configured."""
    return getattr(app, 'config', {}).get('PYCONLYSE_CORS_ORIGINS') or None

class DeviceMonitor:
    """Real-time device monitoring with WebSocket support"""
    
    def __init__(self):
        self.device_cache = {}
        self.monitoring_active = False
    
    def get_device(self, device_name):
        """Get device proxy with caching"""
        if device_name not in self.device_cache:
            try:
                self.device_cache[device_name] = tango.DeviceProxy(device_name)
            except Exception as e:
                logger.error(f"Failed to connect to device {device_name}: {e}")
                raise
        return self.device_cache[device_name]
    
    def monitor_device(self, device_name, room_id):
        """Monitor a single device and emit updates to room"""
        try:
            device = self.get_device(device_name)
            
            # Read key attributes
            data = {
                'device': device_name,
                'timestamp': datetime.now().isoformat(),
                'state': str(device.state()),
                'status': device.status()
            }
            
            # Read specific attributes based on device type
            try:
                if 'itest' in device_name.lower() or 'psu' in device_name.lower():
                    # DS iTest PSU multi-slot attributes
                    try:
                        names = list(device.read_attribute('names').value)
                        states = list(device.read_attribute('states').value)
                        currents_meas = list(device.read_attribute('currents_meas').value)
                        currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                        ids = [int(x) for x in device.read_attribute('ids').value]  # Get actual slot IDs
                        
                        slots = []
                        for i in range(len(names)):
                            # Use actual slot ID instead of array index + 1
                            slot_id = ids[i] if i < len(ids) else i + 1
                            slots.append({
                                'id': slot_id,  # Real slot ID for element targeting
                                'index': i,     # Array index for reference
                                'name': names[i] if i < len(names) else f'Slot {slot_id}',
                                'state': bool(states[i]) if i < len(states) else False,
                                'current_measured': _json_safe_number(currents_meas[i]) if i < len(currents_meas) else 0.0,
                                'current_setpoint': _json_safe_number(currents_setpoint[i]) if i < len(currents_setpoint) else 0.0
                            })
                        
                        data['slots'] = slots
                        data['slot_count'] = len(names)
                    except Exception as e:
                        logger.error(f"Error reading DS iTest PSU attributes: {e}")
                        # Fallback to legacy single-slot attributes
                        try:
                            data['current_setpoint'] = _json_safe_number(device.read_attribute('CurrentSetpoint').value)
                            data['measured_current'] = _json_safe_number(device.read_attribute('MeasuredCurrent').value)
                            data['measured_voltage'] = _json_safe_number(device.read_attribute('MeasuredVoltage').value)
                        except:
                            pass
                
                elif 'camera' in device_name.lower() or 'basler' in device_name.lower():
                    # Camera attributes
                    try:
                        data['exposure_time'] = device.read_attribute('ExposureTime').value
                        data['acquisition_status'] = device.read_attribute('AcquisitionStatus').value
                    except:
                        pass
                
                elif 'netio' in device_name.lower() or 'pdu' in device_name.lower():
                    try:
                        ids = list(device.read_attribute('ids').value)
                    except Exception:
                        ids = []

                    try:
                        names = list(device.read_attribute('names').value)
                    except Exception:
                        names = []

                    try:
                        states = list(device.read_attribute('states').value)
                    except Exception:
                        try:
                            states = list(device.read_attribute('output_statuses').value)
                        except Exception:
                            states = []

                    output_count = max(len(ids), len(names), len(states), 4)
                    if not ids:
                        ids = list(range(1, output_count + 1))

                    outputs = []
                    for i, output_id in enumerate(ids):
                        try:
                            normalized_id = int(float(output_id))
                        except Exception:
                            normalized_id = i + 1
                        output_name = (
                            str(names[i])
                            if i < len(names) and names[i] not in (None, "")
                            else f"Output {normalized_id}"
                        )
                        raw_state = states[i] if i < len(states) else 0
                        try:
                            output_state = 1 if int(float(raw_state)) else 0
                        except Exception:
                            output_state = 1 if bool(raw_state) else 0
                        outputs.append({
                            'id': normalized_id,
                            'name': output_name,
                            'state': output_state,
                        })

                    data['outputs'] = outputs
                
                elif 'owis' in device_name.lower() or 'ps90' in device_name.lower():
                    # OWIS multi-axis controller attributes
                    try:
                        # These attributes return Python dict as string, need to parse them
                        states_str = device.read_attribute('states').value
                        positions_str = device.read_attribute('positions').value
                        
                        # Parse string dicts to Python dicts
                        # The string format is like: "{'1': <DevState.ON: 6>, '2': 0}"
                        import re
                        
                        def parse_python_dict_str(dict_str):
                            """Parse Python dict string to dict, handling DevState enums"""
                            if not dict_str:
                                return {}
                            try:
                                # Replace DevState enums with their numeric values
                                dict_str = re.sub(r'<DevState\.[A-Z]+: (\d+)>', r'\1', dict_str)
                                parsed = ast.literal_eval(dict_str)
                                return parsed if isinstance(parsed, dict) else {}
                            except Exception as e:
                                logger.warning(f"Failed to parse dict string: {dict_str}, error: {e}")
                                return {}
                        
                        states_dict = parse_python_dict_str(states_str)
                        positions_dict = parse_python_dict_str(positions_str)
                        
                        # Convert to proper format for frontend
                        data['states'] = {int(k): int(v) for k, v in states_dict.items()}
                        data['positions'] = {int(k): float(v) for k, v in positions_dict.items()}
                        
                    except Exception as e:
                        logger.error(f"Error reading OWIS attributes: {e}")
                
                elif 'motor' in device_name.lower() or 'standa' in device_name.lower():
                    # Motor attributes
                    try:
                        data['position'] = device.read_attribute('Position').value
                        data['velocity'] = device.read_attribute('Velocity').value
                        data['is_moving'] = device.read_attribute('IsMoving').value
                    except:
                        pass
                
            except Exception as e:
                data['attribute_error'] = str(e)
            
            # Emit update to room
            socketio.emit('device_update', data, room=room_id)
            
        except Exception as e:
            error_data = {
                'device': device_name,
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'connected': False
            }
            socketio.emit('device_error', error_data, room=room_id)
    
    def monitoring_loop(self, room_id, generation=None):
        """Main monitoring loop for a room"""
        logger.info(f"Starting monitoring loop for room {room_id}")
        
        while True:
            with subscription_lock:
                room = monitoring_rooms.get(room_id)
                if room is None or not room['active']:
                    break
                if generation is None:
                    generation = room.get('generation')
                elif room.get('generation') != generation:
                    break
                devices = room['devices'].copy()
            try:
                for device_name in devices:
                    with subscription_lock:
                        room = monitoring_rooms.get(room_id)
                        if (
                            room is None
                            or not room['active']
                            or room.get('generation') != generation
                        ):
                            break
                    self.monitor_device(device_name, room_id)
                
                time.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error in monitoring loop for room {room_id}: {e}")
                time.sleep(5)  # Wait longer on error
        
        logger.info(f"Monitoring loop ended for room {room_id}")

# Global monitor instance
monitor = DeviceMonitor()

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    global socketio
    socketio = SocketIO(
        app, 
        cors_allowed_origins=_socket_cors_origins(app),
        logger=False, 
        engineio_logger=False,
        async_mode='threading',  # Use threading mode explicitly
        ping_timeout=60,  # Increase ping timeout
        ping_interval=25  # Increase ping interval
    )
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Handle client connection"""
        if not _socket_auth_allowed(auth):
            return False
        logger.info("Client connected to WebSocket")
        emit('connected', {'status': 'Connected to PYCONLYSE WebSocket'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        _remove_client_subscriptions(request.sid)
        logger.info("Client disconnected from WebSocket")
    
    @socketio.on('subscribe_device')
    def handle_subscribe_device(data):
        """Subscribe to device monitoring"""
        try:
            device_name = data.get('device')
            
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            room_id, added = _add_subscription(request.sid, device_name)
            if added:
                join_room(room_id)
            
            emit('subscribed', {
                'device': device_name,
                'room': room_id,
                'status': 'Monitoring started'
            })
            
            logger.info(f"Client subscribed to device {device_name}")
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe_device')
    def handle_unsubscribe_device(data):
        """Unsubscribe from device monitoring"""
        try:
            device_name = data.get('device')
            
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            room_id, removed = _remove_subscription(request.sid, device_name)
            if removed:
                leave_room(room_id)
            
            emit('unsubscribed', {
                'device': device_name,
                'status': 'Monitoring stopped'
            })
            
            logger.info(f"Client unsubscribed from device {device_name}")
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('get_device_status')
    def handle_get_device_status(data):
        """Get immediate device status"""
        try:
            device_name = data.get('device')
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            # Get device status immediately
            monitor.monitor_device(device_name, "temp_status")
            
        except Exception as e:
            logger.error(f"Get status error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('execute_command')
    def handle_execute_command(data):
        """Execute device command via WebSocket"""
        try:
            device_name = data.get('device')
            command_name = data.get('command')
            args = data.get('args')
            
            if not device_name or not command_name:
                emit('error', {'message': 'Device name and command required'})
                return

            if not _socket_auth_allowed():
                raise PermissionError("Authentication required")
            
            device = monitor.get_device(device_name)
            
            if args is not None:
                result = device.command_inout(command_name, args)
            else:
                result = device.command_inout(command_name)
            
            emit('command_result', {
                'device': device_name,
                'command': command_name,
                'result': result,
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Client executed command {command_name} on {device_name}")
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            emit('command_error', {
                'device': device_name if 'device_name' in locals() else 'unknown',
                'command': command_name if 'command_name' in locals() else 'unknown',
                'error': str(e),
                'success': False
            })
    
    return socketio

def broadcast_device_alert(device_name, alert_type, message):
    """Broadcast device alert to all subscribers"""
    with subscription_lock:
        subscriber_count = len(device_subscriptions.get(device_name, ()))
        room_id = _room_id(device_name)

    if socketio and subscriber_count:
        alert_data = {
            'device': device_name,
            'alert_type': alert_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        socketio.emit('device_alert', alert_data, room=room_id)
