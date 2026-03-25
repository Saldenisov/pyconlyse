#!/usr/bin/env python3
"""OWIS Client using general DS panel framework"""
import os
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from gui.Panels import OWISPanel
from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor

OWIS_DEVICE_IP = os.environ.get("OWIS_DEVICE_IP", "manip/general/DS_OWIS_PS90_IP")
OWIS_DEVICE_LEGACY = os.environ.get(
    "OWIS_DEVICE_LEGACY", "manip/general/DS_OWIS_PS90"
)


layouts = {
    # Current OWIS split:
    # - Ethernet controller (PS90_IP): axes 1,2,3
    # - Legacy controller (PS90): long stage axis 4
    # Requested mapping:
    # - V0: axis 1 + 3 (IP) and axis 4 (legacy)
    # - VDIV2/VD2: axis 2 (IP)
    # - all: axes 1/2/3 (IP) and axis 4 (legacy)
    "V0": {
        "selection": [(OWIS_DEVICE_IP, [1, 3]), (OWIS_DEVICE_LEGACY, [4])],
        "width": 1,
    },
    "VDIV2": {"selection": [(OWIS_DEVICE_IP, [2])], "width": 1},
    "VD2": {"selection": [(OWIS_DEVICE_IP, [2])], "width": 1},
    "all": {
        "selection": [(OWIS_DEVICE_IP, [1, 2, 3]), (OWIS_DEVICE_LEGACY, [4])],
        "width": 1,
    },
}


def start_owis_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        OWISPanel,
        "OWIS",
        OWIS_motor,
        "bin/icons/OWIS.png",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_owis_client())
