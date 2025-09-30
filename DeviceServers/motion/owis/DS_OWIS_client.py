#!/usr/bin/env python3
"""OWIS Client using general DS panel framework"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from gui.Panels import OWISPanel
from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor

# Layouts from legacy
layouts = {
    "V0": {"selection": [("manip/general/DS_OWIS_PS90", [2, 3, 4])], "width": 1},
    "VD2": {"selection": [("manip/general/DS_OWIS_PS90", [1])], "width": 1},
    "all": {"selection": [("manip/general/DS_OWIS_PS90", [1, 2, 3, 4])], "width": 1},
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
