#!/usr/bin/env python3
"""AVANTES Spectrograph Client using general DS panel framework"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import AVANTES_SPECTROPanel
from DeviceServers.spectrographs.avantes.DS_AVANTES_SPECTRO_Widget import AVANTES_SPECTRO

# Layouts from legacy
layouts = {
    "Gamma": {"selection": ["manip/cr/avantes_spectro1"], "width": 2},
}


def start_avantes_spectro_client(instance: str = "Gamma", vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        AVANTES_SPECTROPanel,
        "AVANTES spectrograph",
        AVANTES_SPECTRO,
        "bin/icons/spectrometer.png",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_avantes_spectro_client())
