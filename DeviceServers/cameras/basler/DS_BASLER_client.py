#!/usr/bin/env python3
"""Basler Camera Client using general DS panel framework"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import BaslerPanel
from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera

# Layouts from legacy
layouts = {
    "V0": {"selection": ["manip/V0/Cam1_V0", "manip/V0/Cam2_V0"], "width": 2},
    "all": {
        "selection": [
            "manip/V0/Cam1_V0",
            "manip/V0/Cam2_V0",
            "manip/V0/Cam3_V0",
        ],
        "width": 3,
    },
    "test": {"selection": ["manip/V0/Cam2_V0"], "width": 1},
    "Cam1": {"selection": ["manip/V0/Cam1_V0"], "width": 1},
    "Cam2": {"selection": ["manip/V0/Cam2_V0"], "width": 1},
    "Cam3": {"selection": ["manip/V0/Cam3_V0"], "width": 1},
}


def start_basler_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        BaslerPanel,
        "BASLER",
        Basler_camera,
        "bin/icons/basler.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_basler_client())
