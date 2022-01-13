import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from gui.Panels import OWISPanel
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor
from bin.DS_General_Client import main


layouts = {'V0': {'selection': [('manip/general/DS_OWIS_PS90', [2, 3, 4])], 'width': 1},
           'VD2': {'selection': [('manip/general/DS_OWIS_PS90', [1])], 'width': 1},
           'all': {'selection': [('manip/general/DS_OWIS_PS90', [1, 2, 3, 4])], 'width': 1}
           }


if __name__ == '__main__':
    main(OWISPanel, 'OWIS', OWIS_motor, 'icons//OWIS.png', layouts)
