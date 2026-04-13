#!/usr/bin/env python3
"""ANDOR spectrograph client using general DS panel framework"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from DeviceServers.shared.DS_Widget import VisType
from DeviceServers.spectrographs.andor.DS_ANDOR_SPECTROGRAPH_Widget import (
    ANDOR_SPECTROGRAPH,
)
from gui.DS_General_Client import main
from gui.Panels import ANDOR_SPECTROGRAPHPanel

layouts = {
    "V0": {
        "selection": ["manip/CR/ANDOR_SHAMROCK1", "manip/CR/ANDOR_KYMERA1"],
        "width": 1,
    }
}


def start_andor_spectrograph_client(
    instance: str = "V0",
    vis_type=None,
    standalone: bool = True,
):
    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        ANDOR_SPECTROGRAPHPanel,
        "ANDOR Spectrographs",
        ANDOR_SPECTROGRAPH,
        "bin/icons/spectrometer.png",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_andor_spectrograph_client())
