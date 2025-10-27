#!/usr/bin/env python
"""
DAQmx Device Server with ZMQ PULL Socket
Receives data from external ZMQ PUSH source and maintains state history
"""

import sys
import json
import time
from pathlib import Path
from typing import Union, Dict, List
from collections import deque
from threading import Thread, Lock

# Add the pyconlyse directory to Python path
_PYCONLYSE_ROOT = Path(__file__).parent.parent.parent.parent
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))

import zmq
from tango import DevState, AttrWriteType
from tango.server import attribute, command, device_property

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    from DeviceServers.base.general import DS_General


class DAQmxState:
    """Maintains state history for DAQmx card values"""
    
    def __init__(self, retention_time=100):
        """
        Args:
            retention_time: How long to keep state in seconds (default 100s)
        """
        self.retention_time = retention_time
        self.data_history = deque(maxlen=1000)  # Store up to 1000 samples
        self.current_state = {}
        self.lock = Lock()
        self.last_update = None
        
    def add_data(self, data: Dict):
        """Add new data sample with timestamp"""
        timestamp = time.time()
        with self.lock:
            self.data_history.append({
                'timestamp': timestamp,
                'data': data
            })
            self.current_state = data.copy()
            self.last_update = timestamp
            self._cleanup_old_data()
    
    def _cleanup_old_data(self):
        """Remove data older than retention_time"""
        if not self.data_history:
            return
        
        cutoff_time = time.time() - self.retention_time
        
        # Remove old entries from the left side
        while self.data_history and self.data_history[0]['timestamp'] < cutoff_time:
            self.data_history.popleft()
    
    def get_latest_values(self) -> Dict:
        """Get the most recent values"""
        with self.lock:
            return {
                'timestamp': self.last_update,
                'data': self.current_state.copy() if self.current_state else {}
            }
    
    def get_history(self, seconds: float = None) -> List[Dict]:
        """Get historical data for the specified time period"""
        with self.lock:
            if seconds is None:
                return list(self.data_history)
            
            cutoff_time = time.time() - seconds
            return [
                entry for entry in self.data_history 
                if entry['timestamp'] >= cutoff_time
            ]
    
    def get_statistics(self) -> Dict:
        """Get statistics about the stored data"""
        with self.lock:
            if not self.data_history:
                return {
                    'sample_count': 0,
                    'time_span': 0,
                    'rate': 0
                }
            
            oldest = self.data_history[0]['timestamp']
            newest = self.data_history[-1]['timestamp']
            time_span = newest - oldest
            
            return {
                'sample_count': len(self.data_history),
                'time_span': time_span,
                'rate': len(self.data_history) / time_span if time_span > 0 else 0,
                'oldest_timestamp': oldest,
                'newest_timestamp': newest
            }


class DS_DAQmx_ZMQ(DS_General):
    """Device Server for DAQmx using ZMQ PULL socket for data acquisition"""

    _version_ = "1.0"
    _model_ = "DAQmx ZMQ Reader"
    polling = 500

    # Device properties
    zmq_host = device_property(dtype=str, default_value="*")
    zmq_port = device_property(dtype=int, default_value=6050)
    retention_time = device_property(dtype=int, default_value=100)
    device_name = device_property(dtype=str, default_value="Dev1")
    
    def init_device(self):
        super().init_device()
        
        # ZMQ socket
        self.zmq_context = None
        self.zmq_socket = None
        self.zmq_thread = None
        self.zmq_running = False
        
        # State storage for DAQmx values
        self.daqmx_state = DAQmxState(retention_time=self.retention_time)
        
        # Statistics
        self._messages_received = 0
        self._last_message_time = None
        self._zmq_status = "Not initialized"
        
        self.info(f"Initialized DAQmx ZMQ Device Server", True)
        self.turn_on()

    def find_device(self):
        """Setup ZMQ connection"""
        self.info(f"Setting up ZMQ connection on {self.zmq_host}:{self.zmq_port}", True)
        
        try:
            # Create ZMQ context and PULL socket
            self.zmq_context = zmq.Context()
            self.zmq_socket = self.zmq_context.socket(zmq.PULL)
            
            # Bind to receive data from PUSH source
            zmq_address = f"tcp://{self.zmq_host}:{self.zmq_port}"
            self.zmq_socket.bind(zmq_address)
            self.zmq_socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout
            
            self._zmq_status = f"Connected to {zmq_address}"
            self._device_id_internal = 1
            self._uri = zmq_address
            
            self.info(f"ZMQ socket bound to {zmq_address}", True)
            return 1, zmq_address
            
        except Exception as e:
            self._zmq_status = f"Error: {str(e)}"
            self._device_id_internal = -1
            self.error(f"Failed to setup ZMQ: {e}")
            return -1, str(e)

    def turn_on_local(self) -> Union[int, str]:
        """Start ZMQ listener thread"""
        if self._device_id_internal == -1 or not self.zmq_socket:
            result = self.find_device()
            if result[0] == -1:
                self.set_state(DevState.FAULT)
                return "Could not initialize ZMQ connection"
        
        # Verify socket is ready before starting thread
        if not self.zmq_socket:
            self.set_state(DevState.FAULT)
            return "ZMQ socket not initialized"
        
        # Start ZMQ receiver thread
        if not self.zmq_running:
            self.zmq_running = True
            self.zmq_thread = Thread(target=self._zmq_receiver_loop, daemon=True)
            self.zmq_thread.start()
            self.info("ZMQ receiver thread started", True)
        
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        """Stop ZMQ listener and cleanup"""
        # Stop receiver thread
        if self.zmq_running:
            self.zmq_running = False
            if self.zmq_thread:
                self.zmq_thread.join(timeout=2)
        
        # Close ZMQ socket
        if self.zmq_socket:
            self.zmq_socket.close()
            self.zmq_socket = None
        
        if self.zmq_context:
            self.zmq_context.term()
            self.zmq_context = None
        
        self._zmq_status = "Disconnected"
        self.set_state(DevState.OFF)
        self.info("ZMQ connection closed", True)
        return 0

    def _zmq_receiver_loop(self):
        """Background thread that receives ZMQ messages"""
        self.info("ZMQ receiver loop started", True)
        
        while self.zmq_running:
            try:
                # Check if socket is still valid
                if not self.zmq_socket:
                    self.warn("ZMQ socket is None, stopping receiver loop")
                    break
                
                # Receive message with timeout
                message = self.zmq_socket.recv_string()
                
                # Parse and store data
                self._process_message(message)
                
                self._messages_received += 1
                self._last_message_time = time.time()
                
            except zmq.Again:
                # Timeout - no message received
                continue
            except AttributeError as e:
                # Socket was closed
                self.warn(f"Socket closed: {e}")
                break
            except Exception as e:
                self.error(f"Error in ZMQ receiver: {e}")
                time.sleep(1)
        
        self.info("ZMQ receiver loop stopped", True)

    def _process_message(self, message: str):
        """Process received ZMQ message and update state"""
        try:
            # Try to parse as JSON
            data = json.loads(message)
            
            # Convert nested array structure to flat dict
            parsed_data = self._parse_daqmx_data(data)
            
            # Store in state manager
            self.daqmx_state.add_data(parsed_data)
            
        except json.JSONDecodeError as e:
            self.error(f"Failed to parse message as JSON: {e}")
        except Exception as e:
            self.error(f"Error processing message: {e}")

    def _parse_daqmx_data(self, data) -> Dict:
        """
        Parse DAQmx data structure into flat dictionary
        Expected format: list of lists with "path/value" strings
        """
        parsed = {}
        
        if isinstance(data, list):
            for group in data:
                if isinstance(group, list):
                    for item in group:
                        if isinstance(item, str) and item:
                            # Parse "path/value" format
                            parts = item.rsplit('/', 1)
                            if len(parts) == 2:
                                path, value_str = parts
                                try:
                                    value = float(value_str)
                                    parsed[path] = value
                                except ValueError:
                                    parsed[path] = value_str
        
        return parsed

    def get_controller_status_local(self) -> Union[int, str]:
        """Check ZMQ connection status"""
        if self.zmq_socket and self.zmq_running:
            return 0
        return "ZMQ not running"

    # ===== Tango Commands =====
    
    @command(dtype_out=str)
    def get_latest_values_json(self) -> str:
        """Get latest DAQmx values as JSON string"""
        latest = self.daqmx_state.get_latest_values()
        return json.dumps(latest, indent=2)
    
    @command(dtype_in=float, dtype_out=str)
    def get_history_json(self, seconds: float) -> str:
        """
        Get historical data as JSON string
        
        Args:
            seconds: Time window to retrieve (0 = all data)
        """
        history = self.daqmx_state.get_history(seconds if seconds > 0 else None)
        return json.dumps(history, indent=2)
    
    @command(dtype_out=str)
    def get_statistics_json(self) -> str:
        """Get statistics about stored data as JSON"""
        stats = self.daqmx_state.get_statistics()
        return json.dumps(stats, indent=2)
    
    @command(dtype_in=str, dtype_out=str)
    def get_channel_value(self, channel_path: str) -> str:
        """
        Get value for a specific channel path
        
        Args:
            channel_path: Full path to the channel (e.g., "elyse/sync/frequency/delay")
        """
        latest = self.daqmx_state.get_latest_values()
        data = latest.get('data', {})
        
        if channel_path in data:
            return json.dumps({
                'channel': channel_path,
                'value': data[channel_path],
                'timestamp': latest['timestamp']
            })
        else:
            return json.dumps({
                'error': f'Channel not found: {channel_path}',
                'available_channels': list(data.keys())[:10]  # Show first 10
            })

    # ===== Tango Attributes =====
    
    @attribute(dtype=str, label="ZMQ Status")
    def zmq_status(self):
        """Current ZMQ connection status"""
        return self._zmq_status
    
    @attribute(dtype=int, label="Messages Received")
    def messages_received(self):
        """Total number of messages received"""
        return self._messages_received
    
    @attribute(dtype=float, label="Last Message Time")
    def last_message_timestamp(self):
        """Timestamp of last received message"""
        return self._last_message_time if self._last_message_time else 0.0
    
    @attribute(dtype=int, label="Samples in History")
    def sample_count(self):
        """Number of samples currently stored"""
        stats = self.daqmx_state.get_statistics()
        return stats['sample_count']
    
    @attribute(dtype=str, label="Latest Values JSON")
    def latest_values_json(self):
        """Latest values as JSON attribute"""
        return self.get_latest_values_json()
    
    @attribute(dtype=str, label="All Channel Names")
    def channel_names(self):
        """List of all available channel names as JSON"""
        latest = self.daqmx_state.get_latest_values()
        channels = list(latest.get('data', {}).keys())
        return json.dumps(channels, indent=2)

    def register_variables_for_archive(self):
        """Register variables for archiving"""
        super().register_variables_for_archive()
        # Can register specific channels here if needed


if __name__ == "__main__":
    DS_DAQmx_ZMQ.run_server()
