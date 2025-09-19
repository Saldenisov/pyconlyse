import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget import TopDirect_Motor
from gui.Panels import TopDirectPanel

layouts = {
    "all": {
        "selection": ["elyse/motorized_devices/Lense260", "manip/V0/DL_SC1"],
        "width": 1,
    },
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


if __name__ == "__main__":
    main(TopDirectPanel, "TopDIRECT", TopDirect_Motor, "icons//TopDirect.svg", layouts)
