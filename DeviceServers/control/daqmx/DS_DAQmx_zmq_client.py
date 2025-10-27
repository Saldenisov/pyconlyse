"""
Client interface for DS_DAQmx_ZMQ Tango Device Server
"""

import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

import json
import tango

from gui.DS_General_Client import main
from gui.Panels import GeneralPanel
from DeviceServers.control.daqmx.DS_DAQmx_zmq_widget import DAQmxZMQ_Widget


class DAQmxZMQClient:
    """Client wrapper for DAQmx ZMQ Device Server."""

    def __init__(self, device_name: str):
        """
        Initialize DAQmx ZMQ client.

        Args:
            device_name: Full Tango device name (e.g., 'control/DAQ/DAQMX_ZMQ_1')
        """
        self.device = tango.DeviceProxy(device_name)

    # ===== State and Status =====
    
    def get_state(self):
        """Get device state."""
        return self.device.state()
    
    def turn_on(self):
        """Turn on the device."""
        self.device.turn_on()
    
    def turn_off(self):
        """Turn off the device."""
        self.device.turn_off()
    
    # ===== Data Retrieval Commands =====
    
    def get_latest_values_json(self) -> str:
        """Get latest DAQmx values as JSON string."""
        return self.device.get_latest_values_json()
    
    def get_latest_values(self) -> dict:
        """Get latest DAQmx values as Python dict."""
        json_str = self.device.get_latest_values_json()
        return json.loads(json_str)
    
    def get_history_json(self, seconds: float = 0) -> str:
        """
        Get historical data as JSON string.
        
        Args:
            seconds: Time window in seconds (0 = all data)
        """
        return self.device.get_history_json(seconds)
    
    def get_history(self, seconds: float = 0) -> list:
        """
        Get historical data as Python list.
        
        Args:
            seconds: Time window in seconds (0 = all data)
        """
        json_str = self.device.get_history_json(seconds)
        return json.loads(json_str)
    
    def get_statistics_json(self) -> str:
        """Get statistics as JSON string."""
        return self.device.get_statistics_json()
    
    def get_statistics(self) -> dict:
        """Get statistics as Python dict."""
        json_str = self.device.get_statistics_json()
        return json.loads(json_str)
    
    def get_channel_value(self, channel_path: str) -> dict:
        """
        Get value for a specific channel.
        
        Args:
            channel_path: Full path to channel (e.g., "elyse/sync/frequency/delay")
        
        Returns:
            Dict with channel, value, and timestamp
        """
        json_str = self.device.get_channel_value(channel_path)
        return json.loads(json_str)
    
    # ===== Attributes =====
    
    def get_zmq_status(self) -> str:
        """Get ZMQ connection status."""
        return self.device.zmq_status
    
    def get_messages_received(self) -> int:
        """Get total number of messages received."""
        return self.device.messages_received
    
    def get_last_message_timestamp(self) -> float:
        """Get timestamp of last received message."""
        return self.device.last_message_timestamp
    
    def get_sample_count(self) -> int:
        """Get number of samples in history."""
        return self.device.sample_count
    
    def get_channel_names(self) -> list:
        """Get list of all available channel names."""
        json_str = self.device.channel_names
        return json.loads(json_str)
    
    # ===== Convenience Methods =====
    
    def print_latest_values(self):
        """Print latest values in a readable format."""
        data = self.get_latest_values()
        
        print(f"\n{'='*70}")
        print(f"Latest DAQmx Values")
        print(f"{'='*70}")
        print(f"Timestamp: {data.get('timestamp')}")
        print(f"\nChannels:")
        
        for channel, value in sorted(data.get('data', {}).items()):
            print(f"  {channel:50s}: {value}")
    
    def print_statistics(self):
        """Print statistics in a readable format."""
        stats = self.get_statistics()
        
        print(f"\n{'='*70}")
        print(f"DAQmx Statistics")
        print(f"{'='*70}")
        print(f"Sample Count:  {stats.get('sample_count')}")
        print(f"Time Span:     {stats.get('time_span', 0):.2f} seconds")
        print(f"Update Rate:   {stats.get('rate', 0):.2f} Hz")
        
        if 'oldest_timestamp' in stats:
            print(f"Oldest Sample: {stats['oldest_timestamp']}")
            print(f"Newest Sample: {stats['newest_timestamp']}")


# Device layouts - single device configuration
layouts = {
    "DAQMX_ZMQ_1": {
        "selection": ["control/DAQ/DAQMX_ZMQ_1"],
        "width": 1,
    },
}


def start_daqmx_zmq_client(instance: Optional[str] = None, vis_type=None, standalone=True):
    """Start DAQmx ZMQ client programmatically
    
    Args:
        instance: Device selection (e.g., 'DAQMX_ZMQ_1')
        vis_type: Visualization type (VisType enum or None for FULL)
        standalone: Whether to run as standalone application
        
    Returns:
        Panel instance if not standalone, None otherwise
    """
    from DeviceServers.shared.DS_Widget import VisType
    
    if vis_type is None:
        vis_type = VisType.FULL
    
    return main(
        GeneralPanel, 
        "DAQmx ZMQ", 
        DAQmxZMQ_Widget, 
        "bin/icons/NETIO.ico", 
        layouts, 
        instance=instance, 
        vis_type=vis_type, 
        standalone=standalone
    )


if __name__ == "__main__":
    main(GeneralPanel, "DAQmx ZMQ", DAQmxZMQ_Widget, "bin/icons/NETIO.ico", layouts)
