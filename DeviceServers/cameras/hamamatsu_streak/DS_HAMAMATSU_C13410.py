"""Tango configuration interface for the C13410 USB streak head."""

from tango import DevState
from tango.server import Device, command

from DeviceServers.cameras.hamamatsu_streak.c13410_usb import (
    C13410Usb,
    configure_synchronized_sweep,
    set_mcp_gain,
    set_streak_shutter,
)


class DS_HAMAMATSU_C13410(Device):
    """Open the HPK driver for a bounded sweep change and release it before Live."""

    def init_device(self):
        super().init_device()
        self.set_state(DevState.ON)

    @command(dtype_out=str)
    def ReadMode(self):
        head = C13410Usb()
        try:
            head.read("ALL")
            return {"FCS": "Focus", "OPE": "Operate"}[head.read("OPE")]
        finally:
            head.close()

    @command(dtype_in=str, dtype_out=str)
    def ConfigureSweep(self, time_range):
        """Set and verify Operate and the requested calibrated time range."""
        head = C13410Usb()
        try:
            return configure_synchronized_sweep(head, time_range, accept_open=True)
        finally:
            head.close()

    @command(dtype_in=str, dtype_out=str)
    def SetShutter(self, value):
        head = C13410Usb()
        try:
            head.read("ALL")
            return set_streak_shutter(head, value)
        finally:
            head.close()

    @command
    def Park(self):
        """Verify the shutter, gain and Focus before releasing the head."""
        head = C13410Usb()
        try:
            head.read("ALL")
            set_streak_shutter(head, "Closed")
            set_mcp_gain(head, 0)
            if head.read("OPE") != "FCS":
                head.write("FCS")
                if head.read("OPE") != "FCS":
                    raise RuntimeError("C13410 did not verify Focus; power retained")
        finally:
            head.close()


if __name__ == "__main__":
    DS_HAMAMATSU_C13410.run_server()
