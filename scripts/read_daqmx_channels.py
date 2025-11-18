"""
Direct DAQmx Card Reader - PCIe-6320
Reads all analog and digital channels directly from hardware

No PSP variables needed - direct hardware access!
"""

import nidaqmx
from nidaqmx.constants import TerminalConfiguration
import json
from datetime import datetime

class DAQmxReader:
    """Direct reader for NI DAQmx cards"""
    
    def __init__(self, device_name="TRANCON-DAQ"):
        self.device_name = device_name
        self.device = nidaqmx.system.Device(device_name)
        
    def get_device_info(self):
        """Get device information"""
        return {
            'name': self.device.name,
            'product': self.device.product_type,
            'serial': self.device.serial_num,
            'analog_inputs': len(self.device.ai_physical_chans),
            'analog_outputs': len(self.device.ao_physical_chans),
            'digital_inputs': len(self.device.di_lines),
            'digital_outputs': len(self.device.do_lines)
        }
    
    def read_all_analog_inputs(self):
        """Read all analog input channels"""
        results = {}
        
        with nidaqmx.Task() as task:
            # Add all AI channels
            for chan in self.device.ai_physical_chans:
                task.ai_channels.add_ai_voltage_chan(
                    chan.name,
                    terminal_config=TerminalConfiguration.RSE
                )
            
            # Read all channels at once
            values = task.read()
            
            # Map to channel names
            for i, chan in enumerate(self.device.ai_physical_chans):
                results[chan.name] = values[i]
        
        return results
    
    def read_single_analog_channel(self, channel_number):
        """Read a single analog channel (0-15)"""
        chan_name = f"{self.device_name}/ai{channel_number}"
        
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(chan_name)
            value = task.read()
        
        return value
    
    def read_all_digital_inputs(self):
        """Read all digital input lines"""
        results = {}
        
        # Read port by port (port0 and port1)
        for port_num in range(2):  # PCIe-6320 has 2 ports (0 and 1)
            port_name = f"{self.device_name}/port{port_num}"
            
            try:
                with nidaqmx.Task() as task:
                    task.di_channels.add_di_chan(port_name)
                    values = task.read()
                    results[port_name] = values
            except:
                pass
        
        return results
    
    def continuous_monitor(self, channels=None, interval=1.0):
        """
        Continuously monitor channels
        
        Args:
            channels: List of channel numbers to monitor (None = all)
            interval: Seconds between reads
        """
        import time
        
        if channels is None:
            # Monitor all analog channels
            channels = list(range(len(self.device.ai_physical_chans)))
        
        print(f"Monitoring {len(channels)} analog channels")
        print(f"Device: {self.device_name}")
        print(f"Interval: {interval}s")
        print("Press Ctrl+C to stop\n")
        print("-" * 80)
        
        try:
            while True:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"\n[{timestamp}]")
                
                for ch in channels:
                    value = self.read_single_analog_channel(ch)
                    print(f"  AI{ch:2d}: {value:8.4f} V")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped")
    
    def save_snapshot(self, filename="daqmx_snapshot.json"):
        """Save current values to JSON file"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'device': self.get_device_info(),
            'analog_inputs': self.read_all_analog_inputs(),
            'digital_inputs': self.read_all_digital_inputs()
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Snapshot saved to {filename}")
        return data


def main():
    print("="*70)
    print("Direct DAQmx Card Reader")
    print("="*70)
    
    try:
        reader = DAQmxReader("TRANCON-DAQ")
        
        # Show device info
        info = reader.get_device_info()
        print(f"\nDevice: {info['name']}")
        print(f"Product: {info['product']}")
        print(f"Serial: {info['serial']}")
        print(f"Analog Inputs: {info['analog_inputs']}")
        print(f"Digital I/O Lines: {info['digital_inputs']}")
        
        # Read all analog channels
        print("\n" + "="*70)
        print("Reading All Analog Input Channels")
        print("="*70)
        
        analog_values = reader.read_all_analog_inputs()
        
        for chan_name, value in analog_values.items():
            print(f"{chan_name:25s}: {value:8.4f} V")
        
        # Read digital inputs
        print("\n" + "="*70)
        print("Reading Digital Inputs")
        print("="*70)
        
        digital_values = reader.read_all_digital_inputs()
        
        for port_name, value in digital_values.items():
            print(f"{port_name:25s}: {value}")
        
        # Save snapshot
        print("\n" + "="*70)
        reader.save_snapshot()
        
        # Offer continuous monitoring
        print("\n" + "="*70)
        choice = input("\nStart continuous monitoring? (y/n): ").strip().lower()
        if choice == 'y':
            interval = float(input("Interval (seconds, default 1.0): ") or "1.0")
            reader.continuous_monitor(interval=interval)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
