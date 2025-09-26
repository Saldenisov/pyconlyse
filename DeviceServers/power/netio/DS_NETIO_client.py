import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu
from gui.Panels import NetioPanel

# Device layouts matching the legacy system
layouts = {
    "V0": {
        "selection": ["manip/V0/PDU_VO", "manip/SD1/PDU_SD1", "manip/SD2/PDU_SD2"],
        "width": 1,
    },
    "VD2": {
        "selection": ["manip/VD2/PDU_VD2", "manip/SD2/PDU_SD2"], 
        "width": 1
    },
    "all": {
        "selection": [
            "manip/V0/PDU_VO",
            "manip/VD2/PDU_VD2",
            "manip/SD1/PDU_SD1",
            "manip/SD2/PDU_SD2",
            "manip/ELYSE/PDU_ELYSE",
        ],
        "width": 1,
    },
    "ELYSE": {
        "selection": [
            "manip/ELYSE/PDU_ELYSE",
        ],
        "width": 1,
    },
}


def start_netio_client(instance: Optional[str] = None, vis_type=None, standalone=True):
    """Start NETIO client programmatically
    
    Args:
        instance: Device selection ('V0', 'VD2', 'all')
        vis_type: Visualization type (VisType enum or None for FULL)
        standalone: Whether to run as standalone application
        
    Returns:
        Panel instance if not standalone, None otherwise
    """
    from DeviceServers.shared.DS_Widget import VisType
    
    if vis_type is None:
        vis_type = VisType.FULL
    
    return main(
        NetioPanel, 
        "NETIO", 
        Netio_pdu, 
        "bin/icons/NETIO.ico", 
        layouts, 
        instance=instance, 
        vis_type=vis_type, 
        standalone=standalone
    )


if __name__ == "__main__":
    main(NetioPanel, "NETIO", Netio_pdu, "bin/icons/NETIO.ico", layouts)