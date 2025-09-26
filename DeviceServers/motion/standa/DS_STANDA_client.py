#!/usr/bin/env python3
"""STANDA Client using general DS panel framework"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import StandaPanel
from DeviceServers.motion.standa.DS_STANDA_Widget import Standa_motor

# Layouts from legacy
layouts = {
    "ELYSE": {
        "selection": [
            "elyse/motorized_devices/de1",
            "manip/V0/F1",
            "elyse/motorized_devices/mme_x",
            "elyse/motorized_devices/mme_y",
            "elyse/motorized_devices/mm1_x",
            "elyse/motorized_devices/mm1_y",
            "elyse/motorized_devices/mm2_x",
            "elyse/motorized_devices/mm2_y",
        ],
        "width": 4,
    },
    "V0": {
        "selection": [
            "manip/V0/mm3_x",
            "manip/V0/mm3_y",
            "manip/V0/mm4_x",
            "manip/V0/mm4_y",
            "manip/V0/dv01",
            "manip/V0/dv02",
            "manip/V0/dv03",
            "manip/V0/dv04",
            "manip/V0/s1",
            "manip/V0/s2",
            "manip/V0/s3",
            "manip/V0/L-2_1",
            "manip/V0/opa_x",
            "manip/V0/opa_y",
            "manip/v0/ts_sc_m",
            "manip/v0/ts_opa_m",
        ],
        "width": 4,
    },
    "V0_short": {"selection": ["manip/V0/dv04", "manip/V0/L-2_1"], "width": 2},
    "alignment": {
        "selection": [
            "elyse/motorized_devices/de1",
            "elyse/motorized_devices/de2",
            "manip/V0/dv01",
            "manip/V0/dv02",
            "elyse/motorized_devices/mm1_x",
            "elyse/motorized_devices/mm1_y",
            "elyse/motorized_devices/mm2_x",
            "elyse/motorized_devices/mm2_y",
            "manip/V0/mm3_x",
            "manip/V0/mm3_y",
            "manip/V0/mm4_x",
            "manip/V0/mm4_y",
            "manip/V0/s1",
            "manip/V0/s2",
            "manip/V0/L-2_1",
            "manip/V0/dv03",
        ],
        "width": 4,
    },
    "OPA": {"selection": ["manip/v0/opa_x", "manip/v0/opa_y"], "width": 2},
    "test": {
        "selection": [
            "elyse/motorized_devices/mm1_x",
            "elyse/motorized_devices/mm1_y",
        ],
        "width": 4,
    },
}


def start_standa_client(instance: Optional[str] = None, vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        StandaPanel,
        "STANDA",
        Standa_motor,
        "bin/icons/STANDA.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_standa_client())
