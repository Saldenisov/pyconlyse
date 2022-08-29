import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from gui.Panels import AVANTES_CCDPanel
from DeviceServers.AVANTES_CCD.DS_AVANTES_CCD_Widget import AVANTES_CCD
from bin.DS_General_Client import main


layouts = {'spectrometer': {'selection': ['manip/CR/AVANTES_CCD1', 'manip/CR/AVANTES_CCD2'], 'width': 2},
           'test': {'selection': ['manip/CR/AVANTES_CCD1'], 'width': 1}
           }


if __name__ == '__main__':
    main(AVANTES_CCDPanel, 'AVANTES_CCD spectrograph', AVANTES_CCD, 'icons//AVANTES_CCD.svg', layouts)
