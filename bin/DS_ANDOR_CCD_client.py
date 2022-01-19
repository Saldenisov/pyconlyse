import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from gui.Panels import BaslerPanel
from DeviceServers.BASLER.DS_BASLER_Widget import Basler_camera
from bin.DS_General_Client import main


layouts = {'V0': {'selection': ['manip/V0/Cam1_V0', 'manip/V0/Cam2_V0'], 'width': 1}
           }


if __name__ == '__main__':
    main(BaslerPanel, 'ANDOR CCD', Basler_camera, 'icons//ANDOR_CCD.svg', layouts)
