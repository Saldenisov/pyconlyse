"""DeviceServers Module - Reorganized Structure

This module contains all device server implementations organized by category:
- base/: Base classes for device servers
- cameras/: Camera and CCD devices (Andor, Basler, Avantes)
- motion/: Motion control devices (OWIS, STANDA, TopDirect)
- power/: Power and GPIO control devices (NETIO, NUMATO, RPI)
- spectrographs/: Spectrograph devices
- data/: Data acquisition and archiving devices
- control/: Control and synchronization devices
- testing/: Test devices
- shared/: Shared utilities and widgets
- executables/: Compiled executables

Imports are now explicit in each module to avoid circular dependencies.
Use specific imports like: from DeviceServers.cameras.basler.DS_Basler_camera import DS_Basler_camera
"""


# Define class matches for widgets - loaded dynamically when needed
def get_class_match():
    """Lazy loading of class matches to avoid import issues"""
    try:
        from DeviceServers.cameras.basler.DS_Basler_camera import DS_Basler_camera
        from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera
        from DeviceServers.motion.owis.DS_OWIS_Aggregator import DS_OWIS_Aggregator
        from DeviceServers.motion.owis.DS_OWIS_PS90 import DS_OWIS_PS90
        from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor
        from DeviceServers.motion.standa.DS_Standa_Motor import DS_Standa_Motor
        from DeviceServers.motion.standa.DS_STANDA_Widget import Standa_motor
        from DeviceServers.motion.topdirect.DS_TopDirect_Motor import DS_TopDirect_Motor
        from DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget import TopDirect_Motor
        from DeviceServers.power.netio.DS_Netio_pdu import DS_Netio_pdu
        from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu
        from DeviceServers.instruments.keysight.DS_KEYSIGHT_33509B import (
            DS_KEYSIGHT_33509B,
        )
        from DeviceServers.instruments.keysight.DS_KEYSIGHT_33509B_Widget import (
            Keysight_33509B,
        )

        return {
            DS_Basler_camera.__name__: Basler_camera,
            DS_Netio_pdu.__name__: Netio_pdu,
            DS_OWIS_PS90.__name__: OWIS_motor,
            DS_OWIS_Aggregator.__name__: OWIS_motor,
            DS_Standa_Motor.__name__: Standa_motor,
            DS_TopDirect_Motor.__name__: TopDirect_Motor,
            DS_KEYSIGHT_33509B.__name__: Keysight_33509B,
        }
    except ImportError as e:
        print(f"Warning: Some device classes not available: {e}")
        return {}


# For backward compatibility
class_match = None  # Loaded on demand
