import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.SPECTROGRAPH.AVANTES_SPECTRO.DS_AVANTES_SPECTRO_Widget import (
    AVANTES_SPECTRO,
)
from gui.Panels import AVANTES_SPECTROPanel

layouts = {"Gamma": {"selection": ["manip/cr/avantes_spectro1"], "width": 2}}


if __name__ == "__main__":
    main(
        AVANTES_SPECTROPanel,
        "AVANTES spectrograph",
        AVANTES_SPECTRO,
        "icons//spectrometer.png",
        layouts,
    )
