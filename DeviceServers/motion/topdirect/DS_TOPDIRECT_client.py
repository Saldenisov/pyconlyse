#!/usr/bin/env python3
"""TopDirect Client using general DS panel framework"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import TopDirectPanel
from DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget import TopDirect_Motor

# Layouts from legacy
layouts = {
    "all": {"selection": ["elyse/motorized_devices/Lense260", "manip/V0/DL_SC1"], "width": 1},
    "VD2": {
        "selection": [
            "elyse/motorized_devices/mirror_vd2",
            "elyse/motorized_devices/emission_mirrors_vd2",
            "elyse/motorized_devices/filter_1_vd2",
            "elyse/motorized_devices/filter_2_vd2",
        ],
        "width": 1,
    },
}


def start_topdirect_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        TopDirectPanel,
        "TopDIRECT",
        TopDirect_Motor,
        "bin/icons/TopDirect.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_topdirect_client())


