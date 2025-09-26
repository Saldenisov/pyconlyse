#!/usr/bin/env python3
"""ANDOR CCD Client using general DS panel framework"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import ANDOR_CCDPanel
from DeviceServers.cameras.andor.DS_ANDOR_CCD_Widget import ANDOR_CCD

# Layouts from legacy
layouts = {
    "V0": {"selection": ["manip/CR/ANDOR_CCD1"], "width": 1},
}


def start_andor_ccd_client(instance: str = "V0", vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        ANDOR_CCDPanel,
        "ANDOR CCD",
        ANDOR_CCD,
        "bin/icons/Andor_CCD.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_andor_ccd_client())
