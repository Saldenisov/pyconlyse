"""Import-inert construction boundary for Tango client objects.

Importing this module does not open a Tango database or device connection.
Consumers must explicitly request a client through one of the factories below.
"""

import tango


def create_database():
    """Create a Tango database client on explicit demand."""
    return tango.Database()


def create_device_proxy(device_name):
    """Create a Tango device proxy on explicit demand."""
    return tango.DeviceProxy(device_name)


def is_healthy_state(state):
    """Return the existing starter-health predicate for a Tango state."""
    return state in (tango.DevState.ON, tango.DevState.MOVING, tango.DevState.STANDBY)
