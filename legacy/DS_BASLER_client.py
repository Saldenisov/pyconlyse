import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera
from gui.Panels import BaslerPanel

layouts = {
    "V0": {"selection": ["manip/V0/Cam1_V0", "manip/V0/Cam2_V0"], "width": 2},
    "all": {
        "selection": ["manip/V0/Cam1_V0", "manip/V0/Cam2_V0", "manip/V0/Cam3_V0"],
        "width": 3,
    },
    "test": {"selection": ["manip/V0/Cam2_V0"], "width": 1},
    "Cam1": {"selection": ["manip/V0/Cam1_V0"], "width": 1},
    "Cam2": {"selection": ["manip/V0/Cam2_V0"], "width": 1},
    "Cam3": {"selection": ["manip/V0/Cam3_V0"], "width": 1},
}


if __name__ == "__main__":
    main(BaslerPanel, "BASLER", Basler_camera, "icons//basler.svg", layouts)
