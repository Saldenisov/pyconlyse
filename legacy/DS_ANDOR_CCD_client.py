import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.cameras.andor.DS_ANDOR_CCD_Widget import ANDOR_CCD
from gui.Panels import ANDOR_CCDPanel

layouts = {"V0": {"selection": ["manip/CR/ANDOR_CCD1"], "width": 1}}


if __name__ == "__main__":
    main(ANDOR_CCDPanel, "ANDOR CCD", ANDOR_CCD, "icons//ANDOR_CCD.svg", layouts)
