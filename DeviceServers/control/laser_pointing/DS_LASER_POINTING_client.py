#!/usr/bin/env python3
"""Laser Pointing Client using general DS panel framework"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from gui.Panels import LaserPointingPanel
from DeviceServers.control.laser_pointing.DS_LaserPointing_Widget import LaserPointing

# Layouts from legacy
layouts = {
    "V0": {"selection": ["manip/v0/laserpointing-cam1", "manip/v0/laserpointing-cam2"], "width": 2},
    "3P": {
        "selection": [
            "manip/v0/laserpointing-cam1",
            "manip/v0/laserpointing-cam2",
            "manip/v0/laserpointing-cam3",
        ],
        "width": 3,
    },
    "Cam1": {"selection": ["manip/v0/laserpointing-cam1"], "width": 1},
    "Cam2": {"selection": ["manip/v0/laserpointing-cam2"], "width": 1},
    "Cam3": {"selection": ["manip/v0/laserpointing-cam3"], "width": 1},
}


def start_laser_pointing_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        LaserPointingPanel,
        "LaserPointing",
        LaserPointing,
        "bin/icons/laser_pointing.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_laser_pointing_client())
