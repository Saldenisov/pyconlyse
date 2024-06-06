import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from gui.Panels import AVANTES_SPECTROPanel
from DeviceServers.SPECTROGRAPH.AVANTES_SPECTRO.DS_AVANTES_SPECTRO_Widget import AVANTES_SPECTRO
from bin.DS_General_Client import main


layouts = {'Gamma': {'selection': ['manip/cr/avantes_spectro1'], 'width': 2}
           }


if __name__ == '__main__':
    main(AVANTES_SPECTROPanel, 'AVANTES spectrograph', AVANTES_SPECTRO, 'icons//spectrometer.png', layouts)
