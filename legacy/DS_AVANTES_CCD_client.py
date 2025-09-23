import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.cameras.avantes.DS_AVANTES_CCD_Widget import AVANTES_CCD
from gui.Panels import AVANTES_CCDPanel

layouts = {
    "Spectrometer": {
        "selection": ["manip/CR/AVANTES_CCD1", "manip/CR/AVANTES_CCD2"],
        "width": 2,
    },
    "test": {
        "selection": ["manip/CR/AVANTES_CCD1", "manip/CR/AVANTES_CCD2"],
        "width": 2,
    },
}


if __name__ == "__main__":
    main(
        AVANTES_CCDPanel,
        "AVANTES_CCD spectrograph",
        AVANTES_CCD,
        "icons//AVANTES_CCD.svg",
        layouts,
    )
