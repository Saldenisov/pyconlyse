# websocket_handler.py - WebSocket support for real-time device monitoring
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import time
import tango
from datetime import datetime
import json
import logging

# Configure logging - reduced verbosity
logging.basicConfig(level=logging.WARNING)
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
                    # DS iTest PSU multi-slot attributes
                    try:
                        names = list(device.read_attribute('names').value)
                        states = list(device.read_attribute('states').value)
                        currents_meas = list(device.read_attribute('currents_meas').value)
                        currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                        
                        slots = []
                        for i in range(len(names)):
                            slots.append({
                                'index': i + 1,
                                'name': names[i] if i < len(names) else f'Slot {i+1}',
                                'state': bool(states[i]) if i < len(states) else False,
                                'current_measured': float(currents_meas[i]) if i < len(currents_meas) else 0.0,
                                'current_setpoint': float(currents_setpoint[i]) if i < len(currents_setpoint) else 0.0
                            })
                        
                        data['slots'] = slots
                        data['slot_count'] = len(names)
                    except Exception as e:
                        logger.error(f"Error reading DS iTest PSU attributes: {e}")
                        # Fallback to legacy single-slot attributes
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
                
                elif 'owis' in device_name.lower() or 'ps90' in device_name.lower():
                    # OWIS multi-axis controller attributes
                    try:
                        print(f"[OWIS] Reading attributes for {device_name}")
                        # These attributes return Python dict as string, need to parse them
                        states_str = device.read_attribute('states').value
                        positions_str = device.read_attribute('positions').value
                        print(f"[OWIS] Raw states: {states_str}")
                        print(f"[OWIS] Raw positions: {positions_str}")
                        
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
                                # Use eval to parse the dict (safe since it's from Tango attribute)
                                return eval(dict_str)
                            except Exception as e:
                                print(f"[OWIS] Parse error: {e}")
                                logger.warning(f"Failed to parse dict string: {dict_str}, error: {e}")
                                return {}
                        
                        states_dict = parse_python_dict_str(states_str)
                        positions_dict = parse_python_dict_str(positions_str)
                        print(f"[OWIS] Parsed states: {states_dict}")
                        print(f"[OWIS] Parsed positions: {positions_dict}")
                        
                        # Convert to proper format for frontend
                        data['states'] = {int(k): int(v) for k, v in states_dict.items()}
                        data['positions'] = {int(k): float(v) for k, v in positions_dict.items()}
                        print(f"[OWIS] Final data['states']: {data['states']}")
                        print(f"[OWIS] Final data['positions']: {data['positions']}")
                        
                    except Exception as e:
                        print(f"[OWIS] ERROR: {e}")
                        import traceback
                        traceback.print_exc()
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
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*", 
        logger=False, 
        engineio_logger=False,
        async_mode='threading',  # Use threading mode explicitly
        ping_timeout=60,  # Increase ping timeout
        ping_interval=25  # Increase ping interval
    )
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info("Client connected to WebSocket")
        emit('connected', {'status': 'Connected to PYCONLYSE WebSocket'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        logger.info("Client disconnected from WebSocket")
    
    @socketio.on('subscribe_device')
    def handle_subscribe_device(data):
        """Subscribe to device monitoring"""
        try:
            device_name = data.get('device')
            room_id = f"device_{device_name}"
            
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
            
            logger.info(f"Client subscribed to device {device_name}")
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe_device')
    def handle_unsubscribe_device(data):
        """Unsubscribe from device monitoring"""
        try:
            device_name = data.get('device')
            room_id = f"device_{device_name}"
            
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
    if socketio and device_name in device_subscriptions:
        alert_data = {
            'device': device_name,
            'alert_type': alert_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        for room_id in device_subscriptions[device_name]:
            socketio.emit('device_alert', alert_data, room=room_id)