"""Tango configuration interface for the C13410 USB streak head."""

from tango import DevState
from tango.server import Device, command

from DeviceServers.cameras.hamamatsu_streak.c13410_usb import C13410Usb, configure_synchronized_sweep


class DS_HAMAMATSU_C13410(Device):
    """Open the HPK driver for a bounded sweep change and release it before Live."""

    def init_device(self):
        super().init_device()
        self.set_state(DevState.ON)

    @command(dtype_in=str, dtype_out=str)
    def ConfigureSweep(self, time_range):
        """Set and verify Operate and the requested calibrated time range."""
        head = C13410Usb()
        try:
            return configure_synchronized_sweep(head, time_range)
        finally:
            head.close()

    @command
    def Park(self):
        """Verify the shutter, gain and Focus before releasing the head."""
        head = C13410Usb()
        try:
            for register, safe in (("SHT", "SHT C"), ("MCP", "MCP 0"), ("OPE", "FCS")):
                if head.read(register) != safe:
                    head.write(safe)
                    if head.read(register) != safe:
                        raise RuntimeError(f"C13410 did not verify {safe}; power retained")
        finally:
            head.close()


if __name__ == "__main__":
    DS_HAMAMATSU_C13410.run_server()
