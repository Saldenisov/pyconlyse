"""Client and GUI launcher for the direct DS_DAQmx Tango Device Server."""

import json
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
if str(app_folder) not in sys.path:
    sys.path.append(str(app_folder))

import tango

from DeviceServers.control.daqmx.DS_DAQmx_Widget import DAQmx_Widget
from gui.DS_General_Client import main
from gui.Panels import GeneralPanel


class DAQmxClient:
    """Client wrapper for the local direct DAQmx Device Server."""

    def __init__(self, device_name: str):
        """
        Initialize DAQmx client.

        Args:
            device_name: Full Tango device name, e.g. 'control/DAQ/DAQMX_1'.
        """
        self.device = tango.DeviceProxy(device_name)

    @property
    def names(self):
        return list(self.device.names)

    def read_channel(self, name: str) -> str:
        return self.device.read_channel(name)

    def write_channel(self, name: str, value) -> str:
        return self.device.write_channel([name, str(value)])

    def read_digital_input(self, name: str) -> int:
        return int(self.device.read_digital_input(name))

    def write_digital_output(self, name: str, value) -> str:
        return self.device.write_digital_output([name, str(value)])

    def read_analog(self, name: str) -> float:
        return float(self.device.read_analog(name))

    def read_counter(self, name: str) -> int:
        return int(self.device.read_counter(name))

    def reset_counter(self, name: str) -> str:
        return self.device.reset_counter(name)

    def snapshot_json(self) -> str:
        return self.device.snapshot_json

    def snapshot(self) -> dict:
        return json.loads(str(self.device.snapshot_json))

    def get_state(self):
        """Get device state."""
        return self.device.state()

    def turn_on(self):
        """Turn on the device."""
        self.device.turn_on()

    def turn_off(self):
        """Turn off the device."""
        self.device.turn_off()


layouts = {
    "DAQMX_1": {
        "selection": ["control/DAQ/DAQMX_1"],
        "width": 1,
    },
}


def start_daqmx_client(instance: Optional[str] = None, vis_type=None, standalone=True):
    """Start the direct DAQmx GUI client programmatically."""
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        GeneralPanel,
        "DAQmx",
        DAQmx_Widget,
        "bin/icons/NETIO.ico",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    main(GeneralPanel, "DAQmx", DAQmx_Widget, "bin/icons/NETIO.ico", layouts)
