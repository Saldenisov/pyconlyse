"""Configured web topology, not discovery or a second Acquisition transport."""

XP_HOST = "10.20.30.10"
TANGO_DEVICE = "elyse/acquisition/telemetry"
DEVICE = "tango://10.20.30.202:10000/" + TANGO_DEVICE
SOURCE_MODES = ("LABVIEW_BRIDGE", "PYTHON_NATIVE", "TRANSITION_OR_FAULT")


def topology():
    return dict(xp_host=XP_HOST, tango_device=TANGO_DEVICE,
                telemetry_and_commands_same_device=True,
                remote_initialization_enabled=False)
