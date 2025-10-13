# websocket_handler.py - WebSocket support for real-time device monitoring
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
import threading
import time
import tango
from datetime import datetime
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global SocketIO instance - will be initialized in app.py
socketio = None

# Global monitoring state
monitoring_rooms = {}  # room_id -> {'devices': set(), 'thread': thread_obj, 'active': bool}
device_subscriptions = {}  # device_name -> set of room_ids

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
                    # Power supply attributes
                    try:
                        data['current_setpoint'] = device.read_attribute('CurrentSetpoint').value
                        data['measured_current'] = device.read_attribute('MeasuredCurrent').value
                        data['measured_voltage'] = device.read_attribute('MeasuredVoltage').value
                    except:
                        pass
                
                elif 'camera' in device_name.lower() or 'basler' in device_name.lower():
                    # Camera attributes
                    try:
                        data['exposure_time'] = device.read_attribute('ExposureTime').value
                        data['acquisition_status'] = device.read_attribute('AcquisitionStatus').value
                    except:
                        pass
                
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
    
    def monitoring_loop(self, room_id):
        """Main monitoring loop for a room"""
        logger.info(f"Starting monitoring loop for room {room_id}")
        
        while room_id in monitoring_rooms and monitoring_rooms[room_id]['active']:
            try:
                devices = monitoring_rooms[room_id]['devices'].copy()
                
                for device_name in devices:
                    if not monitoring_rooms[room_id]['active']:
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
    socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        try:
            # Verify JWT token for WebSocket connection
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            logger.info(f"Client connected: {user_id}")
            emit('connected', {'status': 'Connected to PYCONLYSE WebSocket'})
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            emit('error', {'message': 'Authentication failed'})
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        try:
            user_id = get_jwt_identity()
            logger.info(f"Client disconnected: {user_id}")
        except:
            logger.info("Anonymous client disconnected")
    
    @socketio.on('subscribe_device')
    def handle_subscribe_device(data):
        """Subscribe to device monitoring"""
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            device_name = data.get('device')
            room_id = f"device_{device_name}_{user_id}"
            
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            # Join room for this device
            join_room(room_id)
            
            # Initialize monitoring room if needed
            if room_id not in monitoring_rooms:
                monitoring_rooms[room_id] = {
                    'devices': {device_name},
                    'active': True,
                    'thread': None
                }
                
                # Start monitoring thread
                thread = threading.Thread(
                    target=monitor.monitoring_loop, 
                    args=(room_id,),
                    daemon=True
                )
                thread.start()
                monitoring_rooms[room_id]['thread'] = thread
                
            else:
                monitoring_rooms[room_id]['devices'].add(device_name)
            
            # Track device subscriptions
            if device_name not in device_subscriptions:
                device_subscriptions[device_name] = set()
            device_subscriptions[device_name].add(room_id)
            
            emit('subscribed', {
                'device': device_name,
                'room': room_id,
                'status': 'Monitoring started'
            })
            
            logger.info(f"User {user_id} subscribed to device {device_name}")
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe_device')
    def handle_unsubscribe_device(data):
        """Unsubscribe from device monitoring"""
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            device_name = data.get('device')
            room_id = f"device_{device_name}_{user_id}"
            
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            # Leave room
            leave_room(room_id)
            
            # Remove from monitoring
            if room_id in monitoring_rooms:
                monitoring_rooms[room_id]['devices'].discard(device_name)
                
                # If no devices left in room, stop monitoring
                if not monitoring_rooms[room_id]['devices']:
                    monitoring_rooms[room_id]['active'] = False
                    del monitoring_rooms[room_id]
            
            # Update device subscriptions
            if device_name in device_subscriptions:
                device_subscriptions[device_name].discard(room_id)
                if not device_subscriptions[device_name]:
                    del device_subscriptions[device_name]
            
            emit('unsubscribed', {
                'device': device_name,
                'status': 'Monitoring stopped'
            })
            
            logger.info(f"User {user_id} unsubscribed from device {device_name}")
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('get_device_status')
    def handle_get_device_status(data):
        """Get immediate device status"""
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            device_name = data.get('device')
            if not device_name:
                emit('error', {'message': 'Device name required'})
                return
            
            # Get device status immediately
            monitor.monitor_device(device_name, f"temp_{user_id}")
            
        except Exception as e:
            logger.error(f"Get status error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('execute_command')
    def handle_execute_command(data):
        """Execute device command via WebSocket"""
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            device_name = data.get('device')
            command_name = data.get('command')
            args = data.get('args')
            
            if not device_name or not command_name:
                emit('error', {'message': 'Device name and command required'})
                return
            
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
            
            logger.info(f"User {user_id} executed command {command_name} on {device_name}")
            
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
    if socketio and device_name in device_subscriptions:
        alert_data = {
            'device': device_name,
            'alert_type': alert_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        for room_id in device_subscriptions[device_name]:
            socketio.emit('device_alert', alert_data, room=room_id)