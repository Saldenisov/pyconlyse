"""
Client interface for DS_DAQmx Tango Device Server
"""

import tango


class DAQmxClient:
    """Client wrapper for DAQmx Device Server."""

    def __init__(self, device_name: str):
        """
        Initialize DAQmx client.

        Args:
            device_name: Full Tango device name (e.g., 'control/DAQ/DAQMX_1')
        """
        self.device = tango.DeviceProxy(device_name)

    def acquire_to_psp(self):
        """Trigger acquisition from DAQmx to PSP variables."""
        self.device.acquire_to_psp()

    def write_from_psp(self):
        """Write control signals from PSP variables to DAQmx."""
        self.device.write_from_psp()

    def get_state(self):
        """Get device state."""
        return self.device.state()

    def turn_on(self):
        """Turn on the device."""
        self.device.turn_on()

    def turn_off(self):
        """Turn off the device."""
        self.device.turn_off()


if __name__ == "__main__":
    # Example usage
    client = DAQmxClient("control/DAQ/DAQMX_1")
    print(f"Device state: {client.get_state()}")
