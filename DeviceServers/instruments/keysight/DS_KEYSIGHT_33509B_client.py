#!/usr/bin/env python3
"""Client app for Keysight 33509B using the generic DS client framework."""
import sys
from pathlib import Path
from typing import Optional

# Ensure repo root on path
app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from gui.Panels import GeneralPanel
from DeviceServers.instruments.keysight.DS_KEYSIGHT_33509B_Widget import Keysight_33509B

# Layouts: predefined selections
layouts = {
    "laser": {"selection": ["manip/awg/keysight33509b_laser"], "width": 1},
    "single": {"selection": ["manip/awg/keysight33509b_laser"], "width": 1},
}


def start_keysight_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        GeneralPanel,
        "KEYSIGHT 33509B",
        Keysight_33509B,
        "bin/icons/NETIO.ico",  # reuse an existing icon; customize later if desired
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_keysight_client())
